"""Pruebas de integración de la Parte 3 contra una BD SQLite en memoria.

Cubren generalBalance, isInRed/accountsInRed, precisión decimal (B06),
anulación de movimiento (B07), cuenta desactivada (B08) y saldo negativo (B15)
ejecutando las consultas reales del esquema GraphQL.

Los datos de `datos_referencia` son SINTÉTICOS: reproducen los totales esperados
(1000.00 / 3500.00 / 2900.00 / 600.00 / 1600.00, 1 cuenta en rojo) para validar
la lógica de consolidación. Los datos oficiales los define el seed del equipo.
"""
import os
from datetime import datetime
from decimal import Decimal

import pytest

os.environ.setdefault("JWT_SECRET", "secreto-solo-para-pruebas")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.main import schema
from app.seguridad import crear_token

PERMISOS = ["accounts.read", "accounts.write", "concepts.read", "concepts.write",
            "transactions.read", "transactions.write"]
RANGO = {"fromDate": "2026-10-26", "toDate": "2026-10-30"}

Q_GENERAL = """
query($fromDate: Date!, $toDate: Date!) {
  generalBalance(fromDate: $fromDate, toDate: $toDate) {
    companyId openingBalance totalIncome totalExpense profit closingBalance
    isInRed accountsInRed
    accounts { accountId accountName isActive openingBalance totalIncome
               totalExpense profit closingBalance isInRed }
  }
}"""
Q_CUENTA = """
query($accountId: ID!, $fromDate: Date!, $toDate: Date!) {
  accountBalance(accountId: $accountId, fromDate: $fromDate, toDate: $toDate) {
    accountId openingBalance totalIncome totalExpense profit closingBalance isInRed
  }
}"""
M_CREAR = """
mutation($input: CreateTransactionInput!) {
  createTransaction(input: $input) { id amount transactionType isActive }
}"""
M_ANULAR = "mutation($id: ID!) { deleteTransaction(id: $id) { id isActive amount } }"
M_DESACTIVAR = "mutation($id: ID!) { deactivateAccount(id: $id) { id isActive } }"


class _Request:
    def __init__(self, token):
        self.headers = {"Authorization": f"Bearer {token}"}


class Entorno:
    """Sesión de BD + helper para ejecutar GraphQL como el admin de una empresa."""

    def __init__(self, db, company_id, company_user_id, user_id):
        self.db, self.company_id, self.user_id = db, company_id, user_id
        self.token = crear_token(company_user_id, company_id)

    def gql(self, query, variables=None):
        ctx = {"db": self.db, "request": _Request(self.token)}
        return schema.execute_sync(query, variable_values=variables, context_value=ctx)

    def ok(self, query, variables=None):
        r = self.gql(query, variables)
        assert r.errors is None, r.errors
        return r.data

    def cuenta(self, nombre, tipo=models.AccountTypeEnum.DEBIT):
        a = models.Account(company_id=self.company_id, name=nombre, account_type=tipo)
        self.db.add(a)
        self.db.commit()
        return a

    def mov(self, cuenta, tipo, monto, dia):
        t = models.Transaction(
            account_id=cuenta.id, concept_id=self.conceptos[tipo].id,
            transaction_type=models.TransactionTypeEnum[tipo], amount=Decimal(monto),
            transaction_date=datetime(2026, 10, dia, 12, 0, 0),
            captured_by=self.user_id,
        )
        self.db.add(t)
        self.db.commit()
        return t

    def vincular(self, cuenta):
        for c in self.conceptos.values():
            self.db.add(models.AccountConcept(account_id=cuenta.id, concept_id=c.id))
        self.db.commit()


def _crear_entorno(db, nombre_empresa, email, rol, permisos_rol):
    empresa = models.Company(name=nombre_empresa)
    user = models.User(name=nombre_empresa, email=email, hashed_password="x", is_active=True)
    db.add_all([empresa, user])
    db.flush()
    membresia = models.CompanyUser(company_id=empresa.id, user_id=user.id, is_active=True)
    db.add(membresia)
    db.flush()
    db.add(models.CompanyUserRole(company_user_id=membresia.id, role_id=rol.id, is_active=True))
    db.commit()
    env = Entorno(db, empresa.id, membresia.id, user.id)
    env.conceptos = {
        "INCOME": models.Concept(company_id=empresa.id, name="Ingreso",
                                 concept_type=models.ConceptTypeEnum.INCOME),
        "EXPENSE": models.Concept(company_id=empresa.id, name="Egreso",
                                  concept_type=models.ConceptTypeEnum.EXPENSE),
    }
    db.add_all(env.conceptos.values())
    db.commit()
    return env


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sesion = sessionmaker(bind=engine, autoflush=False)()
    rol = models.Role(code="ADMINISTRADOR", name="Administrador", is_active=True)
    sesion.add(rol)
    permisos = [models.Permission(code=c, name=c, is_active=True) for c in PERMISOS]
    sesion.add_all(permisos)
    sesion.flush()
    for p in permisos:
        sesion.add(models.RolePermission(role_id=rol.id, permission_id=p.id, is_active=True))
    sesion.commit()
    sesion.rol = rol
    yield sesion
    sesion.close()


@pytest.fixture()
def vacia(db):
    """Empresa sin cuentas ni movimientos (B03 / B15)."""
    return _crear_entorno(db, "Empresa vacía", "vacia@test.com", db.rol, PERMISOS)


@pytest.fixture()
def datos_referencia(db):
    """Banco, Caja y Ahorro con movimientos del 25 al 29 de octubre (sintético)."""
    env = _crear_entorno(db, "Empresa referencia", "ref@test.com", db.rol, PERMISOS)
    banco, caja, ahorro = env.cuenta("Banco"), env.cuenta("Caja"), env.cuenta("Ahorro")
    for c in (banco, caja, ahorro):
        env.vincular(c)
    env.mov(banco, "INCOME", "1000.00", 25)   # saldo inicial del periodo
    env.mov(banco, "INCOME", "1800.00", 26)
    env.mov(banco, "EXPENSE", "1000.00", 28)  # B02: profit -1000, cierre 1800
    env.mov(caja, "INCOME", "500.00", 27)
    env.mov(caja, "EXPENSE", "1500.00", 29)   # Caja termina en -1000.00
    env.mov(ahorro, "INCOME", "1200.00", 27)
    env.mov(ahorro, "EXPENSE", "400.00", 29)
    env.cuentas = {"Banco": banco, "Caja": caja, "Ahorro": ahorro}
    return env


def test_general_balance_totales_consolidados(datos_referencia):
    g = datos_referencia.ok(Q_GENERAL, RANGO)["generalBalance"]
    assert Decimal(g["openingBalance"]) == Decimal("1000.00")
    assert Decimal(g["totalIncome"]) == Decimal("3500.00")
    assert Decimal(g["totalExpense"]) == Decimal("2900.00")
    assert Decimal(g["profit"]) == Decimal("600.00")
    assert Decimal(g["closingBalance"]) == Decimal("1600.00")
    assert g["accountsInRed"] == 1
    assert g["isInRed"] is False
    # Orden determinista por accountId ascendente
    ids = [int(c["accountId"]) for c in g["accounts"]]
    assert ids == sorted(ids)
    en_rojo = {c["accountName"] for c in g["accounts"] if c["isInRed"]}
    assert en_rojo == {"Caja"}


def test_saldo_final_es_inicial_mas_ingresos_menos_egresos(datos_referencia):
    g = datos_referencia.ok(Q_GENERAL, RANGO)["generalBalance"]
    for c in [g] + g["accounts"]:
        assert (Decimal(c["closingBalance"]) ==
                Decimal(c["openingBalance"]) + Decimal(c["totalIncome"]) - Decimal(c["totalExpense"]))


def test_is_in_red_depende_del_saldo_final_no_del_profit(datos_referencia):
    # Banco el día 28: pierde 1000 (profit < 0) pero cierra en 1800 -> NO está en rojo
    b = datos_referencia.ok(Q_CUENTA, {"accountId": str(datos_referencia.cuentas["Banco"].id),
                                       "fromDate": "2026-10-28", "toDate": "2026-10-28"})["accountBalance"]
    assert Decimal(b["profit"]) == Decimal("-1000.00")
    assert Decimal(b["closingBalance"]) == Decimal("1800.00")
    assert b["isInRed"] is False


def test_alias_company_balance_conserva_compatibilidad(datos_referencia):
    q = Q_GENERAL.replace("generalBalance", "companyBalance")
    nuevo = datos_referencia.ok(Q_GENERAL, RANGO)["generalBalance"]
    viejo = datos_referencia.ok(q, RANGO)["companyBalance"]
    assert nuevo == viejo


def test_b03_empresa_sin_cuentas_devuelve_ceros(vacia):
    g = vacia.ok(Q_GENERAL, RANGO)["generalBalance"]
    for campo in ("openingBalance", "totalIncome", "totalExpense", "profit", "closingBalance"):
        assert g[campo] == "0.00", campo
    assert g["accountsInRed"] == 0 and g["isInRed"] is False and g["accounts"] == []


def test_b06_precision_decimal_en_cuenta_vacia(vacia):
    cuenta = vacia.cuenta("Cuenta decimales")
    vacia.vincular(cuenta)
    for tipo, monto in (("INCOME", "0.10"), ("INCOME", "0.20"), ("EXPENSE", "0.30")):
        vacia.ok(M_CREAR, {"input": {"accountId": str(cuenta.id),
                                     "conceptId": str(vacia.conceptos[tipo].id),
                                     "transactionType": tipo, "amount": monto}})
    hoy = datetime.utcnow().date().isoformat()
    b = vacia.ok(Q_CUENTA, {"accountId": str(cuenta.id), "fromDate": hoy, "toDate": hoy})["accountBalance"]
    assert b["totalIncome"] == "0.30" and b["totalExpense"] == "0.30"
    assert b["closingBalance"] == "0.00"  # exacto, sin residuos como 5.55e-17
    assert b["isInRed"] is False


@pytest.mark.parametrize("monto", ["10.123", "0.001", "0", "-5.00"])
def test_rechaza_montos_invalidos_en_la_mutacion(vacia, monto):
    cuenta = vacia.cuenta("Cuenta")
    vacia.vincular(cuenta)
    r = vacia.gql(M_CREAR, {"input": {"accountId": str(cuenta.id),
                                      "conceptId": str(vacia.conceptos["INCOME"].id),
                                      "transactionType": "INCOME", "amount": monto}})
    assert r.errors
    assert db_sin_movimientos(vacia.db, cuenta)


def db_sin_movimientos(db, cuenta):
    return db.query(models.Transaction).filter_by(account_id=cuenta.id).count() == 0


@pytest.mark.parametrize("monto,esperado", [("10", "10.00"), ("10.5", "10.50"), ("10.50", "10.50")])
def test_acepta_hasta_dos_decimales_y_guarda_con_dos(vacia, monto, esperado):
    cuenta = vacia.cuenta("Cuenta")
    vacia.vincular(cuenta)
    d = vacia.ok(M_CREAR, {"input": {"accountId": str(cuenta.id),
                                     "conceptId": str(vacia.conceptos["INCOME"].id),
                                     "transactionType": "INCOME", "amount": monto}})
    assert d["createTransaction"]["amount"] == esperado


def test_b07_anular_movimiento_no_lo_borra_pero_no_cuenta(datos_referencia):
    env = datos_referencia
    banco = env.cuentas["Banco"]
    antes = env.ok(Q_GENERAL, RANGO)["generalBalance"]
    t = env.mov(banco, "INCOME", "250.00", 27)
    con = env.ok(Q_GENERAL, RANGO)["generalBalance"]
    assert Decimal(con["totalIncome"]) == Decimal(antes["totalIncome"]) + Decimal("250.00")
    r = env.ok(M_ANULAR, {"id": str(t.id)})["deleteTransaction"]
    assert r["isActive"] is False
    despues = env.ok(Q_GENERAL, RANGO)["generalBalance"]
    assert despues == antes                                   # ya no afecta importes
    env.db.expire_all()
    fila = env.db.get(models.Transaction, t.id)
    assert fila is not None and fila.is_active is False       # sigue en la BD


def test_b08_cuenta_desactivada_sale_del_balance_pero_conserva_historial(datos_referencia):
    env = datos_referencia
    caja = env.cuentas["Caja"]
    env.ok(M_DESACTIVAR, {"id": str(caja.id)})
    g = env.ok(Q_GENERAL, RANGO)["generalBalance"]
    assert "Caja" not in {c["accountName"] for c in g["accounts"]}
    assert g["accountsInRed"] == 0
    # Sin Caja: apertura 1000, ingresos 3000, egresos 1400, cierre 2600
    assert (g["openingBalance"], g["totalIncome"], g["totalExpense"], g["closingBalance"]) == \
           ("1000.00", "3000.00", "1400.00", "2600.00")
    env.db.expire_all()
    assert env.db.query(models.Transaction).filter_by(account_id=caja.id).count() == 2


def test_b08_no_se_puede_registrar_en_cuenta_desactivada(datos_referencia):
    env = datos_referencia
    caja = env.cuentas["Caja"]
    env.ok(M_DESACTIVAR, {"id": str(caja.id)})
    r = env.gql(M_CREAR, {"input": {"accountId": str(caja.id),
                                    "conceptId": str(env.conceptos["INCOME"].id),
                                    "transactionType": "INCOME", "amount": "1.00"}})
    assert r.errors


def test_b15_egreso_en_cuenta_vacia_deja_saldo_negativo(vacia):
    cuenta = vacia.cuenta("Cuenta vacía")
    vacia.vincular(cuenta)
    hoy = datetime.utcnow().date().isoformat()
    rango = {"fromDate": hoy, "toDate": hoy}
    inicial = vacia.ok(Q_GENERAL, rango)["generalBalance"]
    assert inicial["closingBalance"] == "0.00" and inicial["accountsInRed"] == 0
    vacia.ok(M_CREAR, {"input": {"accountId": str(cuenta.id),
                                 "conceptId": str(vacia.conceptos["EXPENSE"].id),
                                 "transactionType": "EXPENSE", "amount": "50.00"}})
    g = vacia.ok(Q_GENERAL, rango)["generalBalance"]
    assert g["closingBalance"] == "-50.00" and g["isInRed"] is True and g["accountsInRed"] == 1
    assert g["accounts"][0]["closingBalance"] == "-50.00" and g["accounts"][0]["isInRed"] is True
    b = vacia.ok(Q_CUENTA, {"accountId": str(cuenta.id), **rango})["accountBalance"]
    assert b["closingBalance"] == "-50.00" and b["isInRed"] is True


def test_rango_invalido_devuelve_error(datos_referencia):
    r = datos_referencia.gql(Q_GENERAL, {"fromDate": "2026-10-30", "toDate": "2026-10-26"})
    assert r.errors and "posterior" in r.errors[0].message
