"""Parte 4 - Seguridad, aislamiento por empresa y pruebas automatizadas (Actividad 7).

Cubre B01, B04, B06, B11, B12, B13 y B14 contra una BD SQLite en memoria.
Los resultados esperados están escritos A MANO a partir de los datos de entrada
de la actividad; nunca se calculan con app.balances.

Ejecutar desde Actividad07/:
    pytest -v tests/test_seguridad_balances.py
"""
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import jwt
import pytest

os.environ.setdefault("JWT_SECRET", "secreto-solo-para-pruebas")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base, get_db
from app.main import app, schema
from app.seguridad import ALGORITMO, SECRETO, crear_token

RANGO = {"fromDate": "2026-10-26", "toDate": "2026-10-30"}
LECTURA = ["accounts.read", "concepts.read", "transactions.read"]
TODOS = LECTURA + ["accounts.write", "concepts.write", "transactions.write"]

Q_CUENTA = """
query($accountId: ID!, $fromDate: Date!, $toDate: Date!) {
  accountBalance(accountId: $accountId, fromDate: $fromDate, toDate: $toDate) {
    accountId accountName isActive openingBalance totalIncome totalExpense
    profit closingBalance isInRed
  }
}"""
Q_GENERAL = """
query($fromDate: Date!, $toDate: Date!) {
  generalBalance(fromDate: $fromDate, toDate: $toDate) {
    companyId currency fromDate toDate openingBalance totalIncome totalExpense
    profit closingBalance isInRed accountsInRed
    accounts { accountId accountName isActive openingBalance totalIncome
               totalExpense profit closingBalance isInRed }
  }
}"""
M_CREAR = """
mutation($input: CreateTransactionInput!) {
  createTransaction(input: $input) { id amount transactionDate }
}"""


class _Request:
    def __init__(self, token=None, header=None):
        if header is not None:
            self.headers = {"Authorization": header}
        elif token is not None:
            self.headers = {"Authorization": f"Bearer {token}"}
        else:
            self.headers = {}


class Entorno:
    """Una empresa con un usuario, su token y helpers para ejecutar GraphQL."""

    def __init__(self, db, empresa, usuario, membresia):
        self.db, self.empresa, self.usuario, self.membresia = db, empresa, usuario, membresia
        self.token = crear_token(membresia.id, empresa.id)
        self.conceptos = {}

    def gql(self, query, variables=None, token="__propio__", header=None):
        tk = self.token if token == "__propio__" else token
        req = _Request(token=tk, header=header)
        ctx = {"db": self.db, "request": req}
        return schema.execute_sync(query, variable_values=variables, context_value=ctx)

    def ok(self, query, variables=None, **kw):
        r = self.gql(query, variables, **kw)
        assert r.errors is None, r.errors
        return r.data

    def cuenta(self, nombre, tipo=models.AccountTypeEnum.DEBIT):
        a = models.Account(company_id=self.empresa.id, name=nombre, account_type=tipo)
        self.db.add(a)
        self.db.commit()
        for c in self.conceptos.values():
            self.db.add(models.AccountConcept(account_id=a.id, concept_id=c.id, is_active=True))
        self.db.commit()
        return a

    def mov(self, cuenta, tipo, monto, dia, hora=12, activo=True):
        """Inserta directo en la BD (sin pasar por el servicio de balances)."""
        t = models.Transaction(
            account_id=cuenta.id, concept_id=self.conceptos[tipo].id,
            transaction_type=models.TransactionTypeEnum[tipo], amount=Decimal(monto),
            transaction_date=datetime(2026, 10, dia, hora, 0, 0),
            captured_by=self.usuario.id, is_active=activo,
        )
        self.db.add(t)
        self.db.commit()
        return t

    def total_movimientos(self):
        return self.db.query(models.Transaction).count()


def _crear_empresa(db, nombre, email, rol):
    empresa = models.Company(name=nombre)
    usuario = models.User(name=nombre, email=email, hashed_password="x", is_active=True)
    db.add_all([empresa, usuario])
    db.flush()
    membresia = models.CompanyUser(company_id=empresa.id, user_id=usuario.id, is_active=True)
    db.add(membresia)
    db.flush()
    db.add(models.CompanyUserRole(company_user_id=membresia.id, role_id=rol.id, is_active=True))
    db.commit()
    env = Entorno(db, empresa, usuario, membresia)
    env.conceptos = {
        "INCOME": models.Concept(company_id=empresa.id, name="Ingreso",
                                 concept_type=models.ConceptTypeEnum.INCOME),
        "EXPENSE": models.Concept(company_id=empresa.id, name="Egreso",
                                  concept_type=models.ConceptTypeEnum.EXPENSE),
    }
    db.add_all(env.conceptos.values())
    db.commit()
    return env


def _crear_empresa_con_dataset(db, nombre, email, rol):
    """Dataset oficial de la actividad (Parte 1): Banco, Caja y Ahorro."""
    env = _crear_empresa(db, nombre, email, rol)
    banco, caja, ahorro = env.cuenta("Banco"), env.cuenta("Caja"), env.cuenta("Ahorro")
    env.mov(banco, "INCOME", "1000.00", 25)    # apertura anterior al periodo
    env.mov(banco, "INCOME", "3000.00", 26)    # cobro de servicios
    env.mov(banco, "EXPENSE", "1200.00", 27)   # renta
    env.mov(banco, "EXPENSE", "1000.00", 28)   # materiales
    env.mov(caja, "INCOME", "500.00", 26)      # venta de contado
    env.mov(caja, "EXPENSE", "700.00", 29)     # insumos
    env.cuentas = {"Banco": banco, "Caja": caja, "Ahorro": ahorro}
    return env


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sesion = sessionmaker(bind=engine, autoflush=False)()
    permisos = {c: models.Permission(code=c, name=c, is_active=True) for c in TODOS}
    sesion.add_all(permisos.values())
    roles = {
        "ADMINISTRADOR": models.Role(code="ADMINISTRADOR", name="Administrador", is_active=True),
        "CONSULTA": models.Role(code="CONSULTA", name="Consulta", is_active=True),
    }
    sesion.add_all(roles.values())
    sesion.flush()
    for codigo, rol in roles.items():
        for p in (TODOS if codigo == "ADMINISTRADOR" else LECTURA):
            sesion.add(models.RolePermission(role_id=rol.id, permission_id=permisos[p].id,
                                             is_active=True))
    sesion.commit()
    sesion.roles, sesion.permisos = roles, permisos
    yield sesion
    sesion.close()


@pytest.fixture()
def empresa_a(db):
    return _crear_empresa_con_dataset(db, "Empresa A", "a@test.com", db.roles["ADMINISTRADOR"])


@pytest.fixture()
def empresa_b(db):
    env = _crear_empresa(db, "Empresa B", "b@test.com", db.roles["ADMINISTRADOR"])
    secreta = env.cuenta("Cuenta Secreta B")
    env.mov(secreta, "INCOME", "9999.00", 27)
    env.cuentas = {"Secreta": secreta}
    return env


def _consulta_en(env):
    """Segundo usuario de la misma empresa con rol CONSULTA."""
    usuario = models.User(name="Consulta", email=f"consulta@{env.empresa.id}.test",
                          hashed_password="x", is_active=True)
    env.db.add(usuario)
    env.db.flush()
    m = models.CompanyUser(company_id=env.empresa.id, user_id=usuario.id, is_active=True)
    env.db.add(m)
    env.db.flush()
    env.db.add(models.CompanyUserRole(company_user_id=m.id,
                                      role_id=env.db.roles["CONSULTA"].id, is_active=True))
    env.db.commit()
    return crear_token(m.id, env.empresa.id)


# ---------------------------------------------------------------- B01
def test_b01_banco_caja_ahorro_y_general_coinciden_con_la_tabla(empresa_a):
    env = empresa_a
    antes = env.total_movimientos()
    esperado = {
        "Banco":  ("1000.00", "3000.00", "2200.00", "800.00", "1800.00", False),
        "Caja":   ("0.00", "500.00", "700.00", "-200.00", "-200.00", True),
        "Ahorro": ("0.00", "0.00", "0.00", "0.00", "0.00", False),
    }
    for nombre, (ini, ing, egr, profit, fin, rojo) in esperado.items():
        b = env.ok(Q_CUENTA, {"accountId": str(env.cuentas[nombre].id), **RANGO})["accountBalance"]
        assert (b["openingBalance"], b["totalIncome"], b["totalExpense"],
                b["profit"], b["closingBalance"], b["isInRed"]) == (ini, ing, egr, profit, fin, rojo), nombre

    g = env.ok(Q_GENERAL, RANGO)["generalBalance"]
    assert g["currency"] == "MXN"
    assert (g["fromDate"], g["toDate"]) == ("2026-10-26", "2026-10-30")
    assert (g["openingBalance"], g["totalIncome"], g["totalExpense"],
            g["profit"], g["closingBalance"]) == ("1000.00", "3500.00", "2900.00", "600.00", "1600.00")
    assert g["isInRed"] is False and g["accountsInRed"] == 1
    assert [a["accountName"] for a in g["accounts"]] == ["Banco", "Caja", "Ahorro"]
    assert env.total_movimientos() == antes  # consultar no modifica filas


def test_b01_banco_solo_el_28_no_esta_en_rojo(empresa_a):  # B02, mismo dataset
    env = empresa_a
    b = env.ok(Q_CUENTA, {"accountId": str(env.cuentas["Banco"].id),
                          "fromDate": "2026-10-28", "toDate": "2026-10-28"})["accountBalance"]
    assert (b["openingBalance"], b["totalIncome"], b["totalExpense"], b["profit"],
            b["closingBalance"], b["isInRed"]) == ("2800.00", "0.00", "1000.00", "-1000.00",
                                                   "1800.00", False)


# ---------------------------------------------------------------- B04
def test_b04_fronteras_del_periodo(empresa_a):
    """Importes distintos (1, 2, 4, 8) para identificar qué movimiento entró dónde."""
    env = empresa_a
    cuenta = env.cuenta("Fronteras")
    fronteras = [("2026-10-25T23:59:59Z", "1.00"),   # justo antes del inicio -> saldo inicial
                 ("2026-10-26T00:00:00Z", "2.00"),   # en el inicio          -> periodo
                 ("2026-10-30T23:59:59Z", "4.00"),   # final del día 30      -> periodo
                 ("2026-10-31T00:00:00Z", "8.00")]   # medianoche del 31     -> fuera
    for fecha, monto in fronteras:
        env.ok(M_CREAR, {"input": {"accountId": str(cuenta.id),
                                   "conceptId": str(env.conceptos["INCOME"].id),
                                   "transactionType": "INCOME", "amount": monto,
                                   "transactionDate": fecha}})
    b = env.ok(Q_CUENTA, {"accountId": str(cuenta.id), **RANGO})["accountBalance"]
    assert b["openingBalance"] == "1.00"
    assert b["totalIncome"] == "6.00"        # 2 + 4; el 8 del día 31 no participa
    assert b["closingBalance"] == "7.00"


# ---------------------------------------------------------------- B06
def test_b06_precision_decimal_sin_residuos_de_float(empresa_a):
    env = empresa_a
    cuenta = env.cuenta("Decimales")
    dia = "2026-10-27T12:00:00Z"
    for tipo, monto in (("INCOME", "0.10"), ("INCOME", "0.20"), ("EXPENSE", "0.30")):
        env.ok(M_CREAR, {"input": {"accountId": str(cuenta.id),
                                   "conceptId": str(env.conceptos[tipo].id),
                                   "transactionType": tipo, "amount": monto,
                                   "transactionDate": dia}})
    b = env.ok(Q_CUENTA, {"accountId": str(cuenta.id),
                          "fromDate": "2026-10-27", "toDate": "2026-10-27"})["accountBalance"]
    assert b["totalIncome"] == "0.30" and b["totalExpense"] == "0.30"
    assert b["profit"] == "0.00" and b["closingBalance"] == "0.00"
    assert b["isInRed"] is False


# ---------------------------------------------------------------- B11
@pytest.mark.parametrize("query,vars_", [("cuenta", None), ("general", None)])
def test_b11_sin_token_se_rechaza(empresa_a, query, vars_):
    env = empresa_a
    if query == "cuenta":
        r = env.gql(Q_CUENTA, {"accountId": str(env.cuentas["Banco"].id), **RANGO}, token=None)
    else:
        r = env.gql(Q_GENERAL, RANGO, token=None)
    assert r.errors and r.data is None
    assert "Token no proporcionado" in r.errors[0].message


def test_b11_token_alterado_vencido_y_formato_invalido(empresa_a):
    env = empresa_a
    var = {"accountId": str(env.cuentas["Banco"].id), **RANGO}

    alterado = env.token[:-3] + ("AAA" if not env.token.endswith("AAA") else "BBB")
    assert env.gql(Q_CUENTA, var, token=alterado).errors
    assert env.gql(Q_GENERAL, RANGO, token=alterado).errors

    firmado_con_otra_llave = jwt.encode(
        {"companyUserId": env.membresia.id, "companyId": env.empresa.id,
         "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "otra-llave-distinta-de-32-bytes-minimo!!", algorithm=ALGORITMO)
    assert env.gql(Q_CUENTA, var, token=firmado_con_otra_llave).errors

    vencido = jwt.encode(
        {"companyUserId": env.membresia.id, "companyId": env.empresa.id,
         "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        SECRETO, algorithm=ALGORITMO)
    for q, v in ((Q_CUENTA, var), (Q_GENERAL, RANGO)):
        r = env.gql(q, v, token=vencido)
        assert r.errors and r.data is None and "expirado" in r.errors[0].message

    r = env.gql(Q_GENERAL, RANGO, token=None, header=f"Token {env.token}")  # no es Bearer
    assert r.errors


def test_b11_http_real_sin_token_y_con_token(db, empresa_a):
    """Extremo a extremo por HTTP: el encabezado Authorization llega al resolver."""
    app.dependency_overrides[get_db] = lambda: db
    try:
        cliente = TestClient(app)
        cuerpo = {"query": Q_GENERAL, "variables": RANGO}
        sin = cliente.post("/graphql", json=cuerpo).json()
        assert sin.get("errors") and sin["data"] is None

        con = cliente.post("/graphql", json=cuerpo,
                           headers={"Authorization": f"Bearer {empresa_a.token}"}).json()
        assert "errors" not in con
        assert con["data"]["generalBalance"]["closingBalance"] == "1600.00"
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------- B12
def test_b12_cuenta_de_otra_empresa_se_rechaza_sin_filtrar_datos(empresa_a, empresa_b):
    ajena = str(empresa_b.cuentas["Secreta"].id)
    r_ajena = empresa_a.gql(Q_CUENTA, {"accountId": ajena, **RANGO})
    r_inexistente = empresa_a.gql(Q_CUENTA, {"accountId": "999999", **RANGO})

    assert r_ajena.errors and r_ajena.data is None
    msg = r_ajena.errors[0].message
    assert msg == "Cuenta no disponible"
    assert msg == r_inexistente.errors[0].message        # ajena == inexistente
    for fuga in ("Secreta", "9999", "Empresa B"):
        assert fuga not in msg


def test_b12_general_de_a_solo_contiene_cuentas_de_a(empresa_a, empresa_b):
    g = empresa_a.ok(Q_GENERAL, RANGO)["generalBalance"]
    assert g["companyId"] == str(empresa_a.empresa.id)
    nombres = {c["accountName"] for c in g["accounts"]}
    assert nombres == {"Banco", "Caja", "Ahorro"}
    assert "Cuenta Secreta B" not in nombres
    assert g["closingBalance"] == "1600.00"              # sin los 9999.00 de B

    # y simétricamente: B no ve nada de A
    gb = empresa_b.ok(Q_GENERAL, RANGO)["generalBalance"]
    assert {c["accountName"] for c in gb["accounts"]} == {"Cuenta Secreta B"}
    assert gb["closingBalance"] == "9999.00"


# ---------------------------------------------------------------- B13
def test_b13_consulta_lee_balances_pero_no_puede_capturar(empresa_a):
    env = empresa_a
    token = _consulta_en(env)
    banco = env.cuentas["Banco"]

    g = env.ok(Q_GENERAL, RANGO, token=token)["generalBalance"]
    assert g["closingBalance"] == "1600.00"
    b = env.ok(Q_CUENTA, {"accountId": str(banco.id), **RANGO}, token=token)["accountBalance"]
    assert b["closingBalance"] == "1800.00"

    antes = env.total_movimientos()
    r = env.gql(M_CREAR, {"input": {"accountId": str(banco.id),
                                    "conceptId": str(env.conceptos["INCOME"].id),
                                    "transactionType": "INCOME", "amount": "10.00"}}, token=token)
    assert r.errors and "transactions.write" in r.errors[0].message
    assert env.total_movimientos() == antes              # no se creó ninguna fila


# ---------------------------------------------------------------- B14
def _desactivar_permiso(env, rol, codigo, activo):
    rp = env.db.query(models.RolePermission).filter_by(
        role_id=env.db.roles[rol].id, permission_id=env.db.permisos[codigo].id).one()
    rp.is_active = activo
    env.db.commit()


@pytest.mark.parametrize("permiso_retirado", ["transactions.read", "accounts.read"])
def test_b14_retirar_un_permiso_bloquea_ambas_consultas_con_el_mismo_token(empresa_a, permiso_retirado):
    env = empresa_a
    token = _consulta_en(env)
    var = {"accountId": str(env.cuentas["Banco"].id), **RANGO}
    assert env.gql(Q_CUENTA, var, token=token).errors is None      # antes: acceso

    _desactivar_permiso(env, "CONSULTA", permiso_retirado, False)
    try:
        for q, v in ((Q_CUENTA, var), (Q_GENERAL, RANGO)):
            r = env.gql(q, v, token=token)
            assert r.errors and r.data is None
            assert permiso_retirado in r.errors[0].message
    finally:
        _desactivar_permiso(env, "CONSULTA", permiso_retirado, True)  # restaurar

    assert env.gql(Q_GENERAL, RANGO, token=token).errors is None     # después: acceso