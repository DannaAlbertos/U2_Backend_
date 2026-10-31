"""Seed reproducible de la Actividad 7.

Uso (desde Actividad07/, con el entorno virtual activo y JWT_SECRET definido):
    1) uvicorn app.main:app      (una vez, para que se carguen roles y permisos; Ctrl+C)
    2) python -m app.seed        (re-ejecutable: borra y recrea SOLO sus empresas)

Crea:
  - "Empresa de prueba": Banco, Caja y Ahorro con el dataset oficial, conceptos
    de ingreso/egreso asignados a las 3 cuentas, un ADMINISTRADOR y un usuario CONSULTA.
  - "Empresa sin cuentas": para el caso B03.
  - "Empresa ajena": una cuenta con movimientos, para el caso B12 (aislamiento).
"""
from datetime import datetime
from decimal import Decimal

import bcrypt

from app.database import SessionLocal, engine, Base
import app.models as models

NOMBRE_EMPRESA = "Empresa de prueba"
NOMBRE_EMPRESA_VACIA = "Empresa sin cuentas"   # caso B03
NOMBRE_EMPRESA_AJENA = "Empresa ajena"         # caso B12
PASSWORD = "Admin123!"

# empresa -> (nombre del admin, correo del admin)
ADMINS = {
    NOMBRE_EMPRESA: ("Admin Prueba", "admin.prueba@example.com"),
    NOMBRE_EMPRESA_VACIA: ("Admin Vacía", "admin.vacia@example.com"),
    NOMBRE_EMPRESA_AJENA: ("Admin Ajena", "admin.ajena@example.com"),
}
CONSULTA = ("Usuario Consulta", "consulta.prueba@example.com")   # B13 y B14

# Dataset oficial de la actividad (todos a las 12:00:00Z de octubre 2026)
# (cuenta, tipo, monto, día, descripción)
MOVIMIENTOS = [
    ("Banco", "INCOME",  "1000.00", 25, "Ingreso de apertura anterior al periodo"),
    ("Banco", "INCOME",  "3000.00", 26, "Cobro de servicios"),
    ("Banco", "EXPENSE", "1200.00", 27, "Pago de renta"),
    ("Banco", "EXPENSE", "1000.00", 28, "Compra de materiales"),
    ("Caja",  "INCOME",   "500.00", 26, "Venta de contado"),
    ("Caja",  "EXPENSE",  "700.00", 29, "Pago de insumos"),
    # Ahorro: sin movimientos
]

CUENTAS = [
    ("Banco",  models.AccountTypeEnum.DEBIT),
    ("Caja",   models.AccountTypeEnum.CASH),
    ("Ahorro", models.AccountTypeEnum.SAVINGS),
]


def _correos():
    return [e for _, e in ADMINS.values()] + [CONSULTA[1]]


def limpiar(db):
    """Borra lo creado por este seed para poder re-ejecutarlo."""
    nombres = [NOMBRE_EMPRESA, NOMBRE_EMPRESA_VACIA, NOMBRE_EMPRESA_AJENA]
    for emp in db.query(models.Company).filter(models.Company.name.in_(nombres)).all():
        ids = [a.id for a in db.query(models.Account).filter_by(company_id=emp.id)]
        if ids:
            db.query(models.Transaction).filter(
                models.Transaction.account_id.in_(ids)
            ).delete(synchronize_session=False)
            db.query(models.AccountConcept).filter(
                models.AccountConcept.account_id.in_(ids)
            ).delete(synchronize_session=False)
            db.query(models.Account).filter(
                models.Account.id.in_(ids)
            ).delete(synchronize_session=False)
        db.query(models.Concept).filter_by(company_id=emp.id).delete(synchronize_session=False)
        for m in db.query(models.CompanyUser).filter_by(company_id=emp.id).all():
            db.query(models.CompanyUserRole).filter_by(
                company_user_id=m.id
            ).delete(synchronize_session=False)
            db.delete(m)
        db.flush()
        db.delete(emp)
    db.query(models.User).filter(
        models.User.email.in_(_correos())
    ).delete(synchronize_session=False)
    db.commit()


def crear_usuario(db, empresa, nombre, email, rol, es_admin):
    hashed = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()
    user = models.User(name=nombre, email=email, hashed_password=hashed, is_active=True)
    db.add(user)
    db.flush()
    cu = models.CompanyUser(
        company_id=empresa.id, user_id=user.id, is_admin=es_admin, is_active=True
    )
    db.add(cu)
    db.flush()
    db.add(models.CompanyUserRole(company_user_id=cu.id, role_id=rol.id, is_active=True))
    return user


def crear_conceptos(db, empresa):
    ing = models.Concept(company_id=empresa.id, name="Ingreso general",
                         concept_type=models.ConceptTypeEnum.INCOME)
    egr = models.Concept(company_id=empresa.id, name="Egreso general",
                         concept_type=models.ConceptTypeEnum.EXPENSE)
    db.add_all([ing, egr])
    db.flush()
    return {"INCOME": ing, "EXPENSE": egr}


def crear_cuenta(db, empresa, nombre, tipo, conceptos):
    cuenta = models.Account(company_id=empresa.id, name=nombre, account_type=tipo)
    db.add(cuenta)
    db.flush()
    for c in conceptos.values():
        db.add(models.AccountConcept(account_id=cuenta.id, concept_id=c.id, is_active=True))
    return cuenta


def run_seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        print("🌱 Iniciando carga de datos iniciales...")

        rol_admin = db.query(models.Role).filter_by(code="ADMINISTRADOR").first()
        rol_consulta = db.query(models.Role).filter_by(code="CONSULTA").first()
        if rol_admin is None or rol_consulta is None:
            raise SystemExit(
                "❌ No existen los roles ADMINISTRADOR/CONSULTA. Levanta el servidor una "
                "vez (uvicorn app.main:app) para que cargue roles y permisos, "
                "y vuelve a correr el seed."
            )

        limpiar(db)

        empresa = models.Company(name=NOMBRE_EMPRESA)
        vacia = models.Company(name=NOMBRE_EMPRESA_VACIA)
        ajena = models.Company(name=NOMBRE_EMPRESA_AJENA)
        db.add_all([empresa, vacia, ajena])
        db.commit()

        admin = crear_usuario(db, empresa, *ADMINS[NOMBRE_EMPRESA], rol_admin, True)
        crear_usuario(db, empresa, CONSULTA[0], CONSULTA[1], rol_consulta, False)
        crear_usuario(db, vacia, *ADMINS[NOMBRE_EMPRESA_VACIA], rol_admin, True)
        admin_ajena = crear_usuario(db, ajena, *ADMINS[NOMBRE_EMPRESA_AJENA], rol_admin, True)
        db.commit()

        conceptos = crear_conceptos(db, empresa)
        cuentas = {n: crear_cuenta(db, empresa, n, t, conceptos) for n, t in CUENTAS}
        db.commit()

        for nombre, tipo, monto, dia, desc in MOVIMIENTOS:
            db.add(models.Transaction(
                account_id=cuentas[nombre].id,
                concept_id=conceptos[tipo].id,
                transaction_type=models.TransactionTypeEnum[tipo],
                amount=Decimal(monto),
                transaction_date=datetime(2026, 10, dia, 12, 0, 0),  # UTC naive
                captured_by=admin.id,
                short_description=desc,
            ))

        # Empresa ajena (B12): una cuenta con dinero que A no debe poder ver
        conc_ajena = crear_conceptos(db, ajena)
        cuenta_ajena = crear_cuenta(db, ajena, "Cuenta ajena", models.AccountTypeEnum.DEBIT,
                                    conc_ajena)
        db.flush()
        db.add(models.Transaction(
            account_id=cuenta_ajena.id, concept_id=conc_ajena["INCOME"].id,
            transaction_type=models.TransactionTypeEnum.INCOME, amount=Decimal("9999.00"),
            transaction_date=datetime(2026, 10, 27, 12, 0, 0),
            captured_by=admin_ajena.id, short_description="Dinero de otra empresa",
        ))
        db.commit()

        print(f"\n {NOMBRE_EMPRESA} (id={empresa.id}): "
              f"{len(cuentas)} cuentas, {len(MOVIMIENTOS)} movimientos")
        for nombre, c in cuentas.items():
            print(f"   cuenta {nombre:<7} id={c.id}")
        print(f"   conceptId INCOME={conceptos['INCOME'].id}  EXPENSE={conceptos['EXPENSE'].id}")
        print(f" admin:    {ADMINS[NOMBRE_EMPRESA][1]} / {PASSWORD}")
        print(f" consulta: {CONSULTA[1]} / {PASSWORD}   (rol CONSULTA: B13 y B14)")
        print(f"\n {NOMBRE_EMPRESA_VACIA} (id={vacia.id}): sin cuentas (caso B03)")
        print(f" admin:    {ADMINS[NOMBRE_EMPRESA_VACIA][1]} / {PASSWORD}")
        print(f"\n {NOMBRE_EMPRESA_AJENA} (id={ajena.id}): 'Cuenta ajena' id={cuenta_ajena.id} (caso B12)")
        print(f" admin:    {ADMINS[NOMBRE_EMPRESA_AJENA][1]} / {PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()