from datetime import datetime
from decimal import Decimal

import bcrypt

from app.database import SessionLocal, engine, Base
import app.models as models

NOMBRE_EMPRESA = "Empresa de prueba"
NOMBRE_EMPRESA_VACIA = "Empresa sin cuentas"  # caso B03
PASSWORD = "Admin123!"
ADMINS = {
    NOMBRE_EMPRESA: ("Admin Prueba", "admin.prueba@example.com"),
    NOMBRE_EMPRESA_VACIA: ("Admin Vacía", "admin.vacia@example.com"),
}

# ⚠️ PROVISIONAL: reemplazar con la tabla del PDF.
# (cuenta, tipo, monto, día de octubre 2026, descripción)
MOVIMIENTOS = [
    ("Banco", "INCOME",  "3000.00", 25, "Depósito inicial"),
    ("Banco", "EXPENSE",  "200.00", 26, "Gasto"),
    ("Banco", "EXPENSE", "1000.00", 28, "Gasto del día 28"),  # B02
    ("Caja",  "INCOME",   "500.00", 25, "Ingreso en caja"),
    ("Ahorro", "INCOME", "1000.00", 27, "Aportación"),
]

CUENTAS = [
    ("Banco",  models.AccountTypeEnum.DEBIT),
    ("Caja",   models.AccountTypeEnum.CASH),
    ("Ahorro", models.AccountTypeEnum.SAVINGS),
]


def limpiar(db):
    """Borra lo creado por este seed para poder re-ejecutarlo."""
    empresas = db.query(models.Company).filter(
        models.Company.name.in_([NOMBRE_EMPRESA, NOMBRE_EMPRESA_VACIA])
    ).all()
    for emp in empresas:
        ids = [a.id for a in db.query(models.Account).filter_by(company_id=emp.id)]
        if ids:
            db.query(models.Transaction).filter(
                models.Transaction.account_id.in_(ids)
            ).delete(synchronize_session=False)
            db.query(models.Account).filter(
                models.Account.id.in_(ids)
            ).delete(synchronize_session=False)
        for m in db.query(models.CompanyUser).filter_by(company_id=emp.id).all():
            db.query(models.CompanyUserRole).filter_by(
                company_user_id=m.id
            ).delete(synchronize_session=False)
            db.delete(m)
        db.flush()
        db.delete(emp)
    db.query(models.User).filter(
        models.User.email.in_([e for _, e in ADMINS.values()])
    ).delete(synchronize_session=False)
    db.commit()


def crear_admin(db, empresa, rol_admin):
    nombre, email = ADMINS[empresa.name]
    hashed = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()
    user = models.User(name=nombre, email=email, hashed_password=hashed, is_active=True)
    db.add(user)
    db.flush()
    cu = models.CompanyUser(
        company_id=empresa.id, user_id=user.id, is_admin=True, is_active=True
    )
    db.add(cu)
    db.flush()
    db.add(models.CompanyUserRole(
        company_user_id=cu.id, role_id=rol_admin.id, is_active=True
    ))


def run_seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        print("🌱 Iniciando carga de datos iniciales...")

        rol_admin = db.query(models.Role).filter_by(code="ADMINISTRADOR").first()
        if rol_admin is None:
            raise SystemExit(
                "❌ No existe el rol ADMINISTRADOR. Levanta el servidor una vez "
                "(uvicorn app.main:app) para que cargue roles y permisos, "
                "y vuelve a correr el seed."
            )

        limpiar(db)

        empresa = models.Company(name=NOMBRE_EMPRESA)
        vacia = models.Company(name=NOMBRE_EMPRESA_VACIA)
        db.add_all([empresa, vacia])
        db.commit()

        crear_admin(db, empresa, rol_admin)
        crear_admin(db, vacia, rol_admin)
        db.commit()

        cuentas = {}
        for nombre, tipo in CUENTAS:
            c = models.Account(company_id=empresa.id, name=nombre, account_type=tipo)
            db.add(c)
            cuentas[nombre] = c
        db.commit()

        for nombre, tipo, monto, dia, desc in MOVIMIENTOS:
            db.add(models.Transaction(
                account_id=cuentas[nombre].id,
                transaction_type=models.TransactionTypeEnum[tipo],
                amount=Decimal(monto),
                transaction_date=datetime(2026, 10, dia, 12, 0, 0),  # UTC naive
                short_description=desc,
            ))
        db.commit()

        print(f"✅ {NOMBRE_EMPRESA} (id={empresa.id}): "
              f"{len(cuentas)} cuentas, {len(MOVIMIENTOS)} movimientos")
        print(f"✅ {NOMBRE_EMPRESA_VACIA} (id={vacia.id}): sin cuentas (caso B03)")
        for nombre, (_, email) in ADMINS.items():
            print(f"🔑 {nombre}: {email} / {PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()