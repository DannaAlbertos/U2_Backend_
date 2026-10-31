"""Prepara datos para las evidencias de la Parte 3 (B06, B07, B08, B15 y generalBalance).

Uso (desde Actividad07/, con el entorno virtual activo y JWT_SECRET definido):
    python preparar_parte3.py

Es re-ejecutable: borra y recrea SOLO las dos empresas de este script.
Antes, levanta el servidor una vez (uvicorn app.main:app) para que existan
los roles y permisos.

Empresa Parte3 Referencia  -> Banco, Caja y Ahorro con movimientos del 25 al 29 de oct.
                              Con el rango 2026-10-26..2026-10-30 produce:
                              1000.00 / 3500.00 / 2900.00 / 600.00 / 1600.00, 1 cuenta en rojo.
                              (Datos SINTÉTICOS: sustituir por los del PDF/seed oficial si difieren.)
Empresa Parte3 Vacia       -> una cuenta sin movimientos, para B06 y B15.
"""
from datetime import datetime
from decimal import Decimal

import bcrypt

from app.database import Base, SessionLocal, engine
import app.models as models

PASSWORD = "Admin123!"
EMPRESAS = {
    "Empresa Parte3 Referencia": ("Admin Referencia", "parte3.ref@example.com"),
    "Empresa Parte3 Vacia": ("Admin Vacia", "parte3.vacia@example.com"),
}
# (cuenta, tipo, monto, día de octubre 2026)
MOVIMIENTOS = [
    ("Banco", "INCOME", "1000.00", 25),   # saldo inicial del periodo 26-30
    ("Banco", "INCOME", "1800.00", 26),
    ("Banco", "EXPENSE", "1000.00", 28),  # profit -1000.00, cierre 1800.00 (B02)
    ("Caja", "INCOME", "500.00", 27),
    ("Caja", "EXPENSE", "1500.00", 29),   # termina en -1000.00 -> cuenta en rojo
    ("Ahorro", "INCOME", "1200.00", 27),
    ("Ahorro", "EXPENSE", "400.00", 29),
]
TIPOS = {"Banco": models.AccountTypeEnum.DEBIT, "Caja": models.AccountTypeEnum.CASH,
         "Ahorro": models.AccountTypeEnum.SAVINGS}


def limpiar(db):
    for emp in db.query(models.Company).filter(models.Company.name.in_(list(EMPRESAS))).all():
        ids = [a.id for a in db.query(models.Account).filter_by(company_id=emp.id)]
        cids = [c.id for c in db.query(models.Concept).filter_by(company_id=emp.id)]
        if ids:
            db.query(models.Transaction).filter(models.Transaction.account_id.in_(ids)).delete(synchronize_session=False)
            db.query(models.AccountConcept).filter(models.AccountConcept.account_id.in_(ids)).delete(synchronize_session=False)
            db.query(models.Account).filter(models.Account.id.in_(ids)).delete(synchronize_session=False)
        if cids:
            db.query(models.Concept).filter(models.Concept.id.in_(cids)).delete(synchronize_session=False)
        for m in db.query(models.CompanyUser).filter_by(company_id=emp.id).all():
            db.query(models.CompanyUserRole).filter_by(company_user_id=m.id).delete(synchronize_session=False)
            db.delete(m)
        db.flush()
        db.delete(emp)
    db.query(models.User).filter(models.User.email.in_([e for _, e in EMPRESAS.values()])).delete(synchronize_session=False)
    db.commit()


def crear_empresa(db, nombre, rol_admin):
    empresa = models.Company(name=nombre)
    db.add(empresa)
    db.flush()
    nom, email = EMPRESAS[nombre]
    user = models.User(name=nom, email=email, is_active=True,
                       hashed_password=bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode())
    db.add(user)
    db.flush()
    cu = models.CompanyUser(company_id=empresa.id, user_id=user.id, is_admin=True, is_active=True)
    db.add(cu)
    db.flush()
    db.add(models.CompanyUserRole(company_user_id=cu.id, role_id=rol_admin.id, is_active=True))
    ing = models.Concept(company_id=empresa.id, name="Ingreso general", concept_type=models.ConceptTypeEnum.INCOME)
    egr = models.Concept(company_id=empresa.id, name="Egreso general", concept_type=models.ConceptTypeEnum.EXPENSE)
    db.add_all([ing, egr])
    db.flush()
    return empresa, user, {"INCOME": ing, "EXPENSE": egr}


def crear_cuenta(db, empresa, nombre, tipo, conceptos):
    cuenta = models.Account(company_id=empresa.id, name=nombre, account_type=tipo)
    db.add(cuenta)
    db.flush()
    for c in conceptos.values():
        db.add(models.AccountConcept(account_id=cuenta.id, concept_id=c.id, is_active=True))
    return cuenta


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        rol_admin = db.query(models.Role).filter_by(code="ADMINISTRADOR").first()
        if rol_admin is None:
            raise SystemExit("No existe el rol ADMINISTRADOR. Levanta el servidor una vez "
                             "(uvicorn app.main:app) y vuelve a ejecutar este script.")
        limpiar(db)

        ref, user_ref, conc_ref = crear_empresa(db, "Empresa Parte3 Referencia", rol_admin)
        cuentas = {n: crear_cuenta(db, ref, n, t, conc_ref) for n, t in TIPOS.items()}
        for nombre, tipo, monto, dia in MOVIMIENTOS:
            db.add(models.Transaction(
                account_id=cuentas[nombre].id, concept_id=conc_ref[tipo].id,
                transaction_type=models.TransactionTypeEnum[tipo], amount=Decimal(monto),
                transaction_date=datetime(2026, 10, dia, 12, 0, 0), captured_by=user_ref.id,
                short_description=f"{tipo} {nombre} día {dia}"))

        vac, _, conc_vac = crear_empresa(db, "Empresa Parte3 Vacia", rol_admin)
        cuenta_vac = crear_cuenta(db, vac, "Cuenta vacia", models.AccountTypeEnum.DEBIT, conc_vac)
        db.commit()

        print("Datos de la Parte 3 listos.\n")
        print(f"[Referencia] empresa id={ref.id}  login: {EMPRESAS[ref.name][1]} / {PASSWORD}")
        for n, c in cuentas.items():
            print(f"   cuenta {n:<7} id={c.id}")
        print(f"   conceptId INCOME={conc_ref['INCOME'].id}  EXPENSE={conc_ref['EXPENSE'].id}")
        print(f"\n[Vacia] empresa id={vac.id}  login: {EMPRESAS[vac.name][1]} / {PASSWORD}")
        print(f"   cuenta 'Cuenta vacia' id={cuenta_vac.id}")
        print(f"   conceptId INCOME={conc_vac['INCOME'].id}  EXPENSE={conc_vac['EXPENSE'].id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
