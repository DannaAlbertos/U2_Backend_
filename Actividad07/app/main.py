from fastapi import FastAPI, Depends, Request
import strawberry
from strawberry.fastapi import GraphQLRouter
from typing import Optional, List
from datetime import datetime, date
from sqlalchemy.orm import Session
import bcrypt
from decimal import Decimal

from app.database import engine, Base, get_db, SessionLocal
import app.models as models
from app.seguridad import leer_actor, crear_token
from app.fechas import (
    normalizar_datetime_utc,
    ahora_utc_naive,
    fecha_utc_para_respuesta,
)
from app.balances import calcular_balances_por_cuenta, calcular_balance_general
from app.moneda import validar_monto, esta_en_rojo


# --- SEGURIDAD ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


Base.metadata.create_all(bind=engine)

# --- DATOS INICIALES: roles y permisos ---
ROLES_INICIALES = [
    ("ADMINISTRADOR", "Administrador", "Administrador principal de la empresa"),
    ("CONTADOR", "Contador", "Arma cuentas y conceptos, también registra los movimientos"),
    ("CAPTURISTA", "Capturista", "Registra los movimientos"),
    ("CONSULTA", "Consulta", "Solo lee"),
]
PERMISOS_INICIALES = [
    ("company.users.read", "Ver usuarios", "Ver las membresías de la empresa"),
    ("company.users.write", "Administrar usuarios", "Crear usuarios y desactivar membresías"),
    ("accounts.read", "Consultar cuentas", "Consultar cuentas"),
    ("accounts.write", "Crear cuentas", "Crear cuentas"),
    ("concepts.read", "Consultar conceptos", "Consultar conceptos"),
    ("concepts.write", "Crear conceptos", "Crear conceptos y asignarlos a una cuenta"),
    ("transactions.read", "Consultar movimientos", "Consultar movimientos"),
    ("transactions.write", "Registrar movimientos", "Registrar un ingreso o un egreso"),
    ("roles.read", "Ver roles", "Ver roles y la matriz de permisos"),
    ("roles.write", "Administrar roles", "Asignar o quitar permisos de un rol y asignar un rol a una membresía"),
]

MATRIZ_PERMISOS = {
    "ADMINISTRADOR": [
        "company.users.read", "company.users.write",
        "accounts.read", "accounts.write",
        "concepts.read", "concepts.write",
        "transactions.read", "transactions.write",
        "roles.read", "roles.write",
    ],
    "CONTADOR": [
        "company.users.read",
        "accounts.read", "accounts.write",
        "concepts.read", "concepts.write",
        "transactions.read", "transactions.write",
        "roles.read",
    ],
    "CAPTURISTA": [
        "accounts.read", "concepts.read",
        "transactions.read", "transactions.write",
    ],
    "CONSULTA": [
        "company.users.read", "accounts.read",
        "concepts.read", "transactions.read",
    ],
}


def seed_role_permissions():
    db = SessionLocal()
    try:
        for role_code, permission_codes in MATRIZ_PERMISOS.items():
            role = db.query(models.Role).filter(models.Role.code == role_code).first()
            if role is None:
                continue
            existing = db.query(models.RolePermission).filter(
                models.RolePermission.role_id == role.id
            ).first()
            if existing:
                continue
            for permission_code in permission_codes:
                permission = db.query(models.Permission).filter(
                    models.Permission.code == permission_code
                ).first()
                if permission is None:
                    raise ValueError(f"No existe el permiso: {permission_code}")
                db.add(models.RolePermission(
                    role_id=role.id, permission_id=permission.id, is_active=True
                ))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def seed_roles_y_permisos():
    db = SessionLocal()
    try:
        if db.query(models.Role).count() == 0:
            for code, name, desc in ROLES_INICIALES:
                db.add(models.Role(code=code, name=name, description=desc))
        if db.query(models.Permission).count() == 0:
            for code, name, desc in PERMISOS_INICIALES:
                db.add(models.Permission(code=code, name=name, description=desc))
        db.commit()
    finally:
        db.close()


seed_roles_y_permisos()
seed_role_permissions()

# --- ENUMS ---
AccountType = strawberry.enum(models.AccountTypeEnum, name="AccountType")
ConceptType = strawberry.enum(models.ConceptTypeEnum, name="ConceptType")
TransactionType = strawberry.enum(models.TransactionTypeEnum, name="TransactionType")


# --- TIPOS ---
@strawberry.type
class Company:
    id: strawberry.ID
    name: str
    isActive: bool


@strawberry.type
class User:
    id: strawberry.ID
    name: str
    email: str


@strawberry.type
class CompanyUserType:
    id: strawberry.ID
    companyId: strawberry.ID
    userId: strawberry.ID
    isAdmin: bool
    isActive: bool


@strawberry.type
class Account:
    id: strawberry.ID
    companyId: strawberry.ID
    accountType: AccountType
    name: str
    bankName: Optional[str]
    accountNumber: Optional[str]
    clabe: Optional[str]
    cardLastDigits: Optional[str]
    shortDescription: Optional[str]
    longDescription: Optional[str]
    isActive: bool
    createdAt: datetime
    updatedAt: datetime
    company: Company


@strawberry.type
class Concept:
    id: strawberry.ID
    companyId: strawberry.ID
    conceptType: ConceptType
    name: str
    shortDescription: Optional[str]
    longDescription: Optional[str]
    isActive: bool
    createdAt: datetime
    updatedAt: datetime


@strawberry.type
class AccountConcept:
    id: strawberry.ID
    accountId: strawberry.ID
    conceptId: strawberry.ID
    isActive: bool
    createdAt: datetime
    account: Account
    concept: Concept


@strawberry.type
class Transaction:
    id: strawberry.ID
    accountId: strawberry.ID
    conceptId: strawberry.ID
    transactionType: TransactionType
    amount: Decimal
    transactionDate: datetime
    capturedAt: datetime
    capturedBy: strawberry.ID
    shortDescription: Optional[str]
    longDescription: Optional[str]
    isActive: bool
    createdAt: datetime
    updatedAt: datetime
    account: Account
    concept: Concept
    capturedByUser: User


@strawberry.type
class AuthPayload:
    token: str
    tokenType: str
    user: Optional[User]


@strawberry.type
class Role:
    id: strawberry.ID
    code: str
    name: str
    description: Optional[str]
    isActive: bool


@strawberry.type
class Permission:
    id: strawberry.ID
    code: str
    name: str
    description: Optional[str]
    isActive: bool


@strawberry.type
class RolePermissionType:
    id: strawberry.ID
    roleId: strawberry.ID
    permissionId: strawberry.ID
    isActive: bool
    createdAt: datetime
    role: Role
    permission: Permission


@strawberry.type
class AccountBalance:
    accountId: strawberry.ID
    accountName: str
    isActive: bool
    openingBalance: Decimal
    totalIncome: Decimal
    totalExpense: Decimal
    profit: Decimal
    closingBalance: Decimal
    isInRed: bool


@strawberry.type
class GeneralBalance:
    companyId: strawberry.ID
    currency: str
    fromDate: date
    toDate: date
    openingBalance: Decimal
    totalIncome: Decimal
    totalExpense: Decimal
    profit: Decimal
    closingBalance: Decimal
    isInRed: bool
    accountsInRed: int
    accounts: List[AccountBalance]


@strawberry.type
class RolePermissionUpdate:
    role: Role
    activated: List[Permission]
    deactivated: List[Permission]
    unchanged: List[Permission]
    finalCount: int
    changed: bool


# --- INPUTS ---
@strawberry.input
class CreateAccountInput:
    companyId: strawberry.ID
    accountType: AccountType
    name: str
    bankName: Optional[str] = None
    accountNumber: Optional[str] = None
    clabe: Optional[str] = None
    cardLastDigits: Optional[str] = None
    shortDescription: Optional[str] = None
    longDescription: Optional[str] = None


@strawberry.input
class CreateConceptInput:
    companyId: strawberry.ID
    conceptType: ConceptType
    name: str
    shortDescription: Optional[str] = None
    longDescription: Optional[str] = None


@strawberry.input
class AssignConceptToAccountInput:
    accountId: strawberry.ID
    conceptId: strawberry.ID


@strawberry.input
class CreateTransactionInput:
    accountId: strawberry.ID
    conceptId: strawberry.ID
    transactionType: TransactionType
    amount: Decimal
    transactionDate: Optional[datetime] = None
    shortDescription: Optional[str] = None
    longDescription: Optional[str] = None


@strawberry.input
class LoginInput:
    email: str
    password: str


@strawberry.input
class CreateRoleInput:
    code: str
    name: str
    description: Optional[str]


@strawberry.input
class CreatePermissionInput:
    code: str
    name: str
    description: Optional[str]


@strawberry.input
class SetRolePermissionsInput:
    roleId: strawberry.ID
    permissionIds: List[strawberry.ID]


# --- CONTEXTO ---
async def get_context(request: Request, db: Session = Depends(get_db)):
    return {"db": db, "request": request}


# --- CONVERTIDORES ---
def role_to_gql(r: models.Role) -> Role:
    return Role(id=r.id, code=r.code, name=r.name, description=r.description, isActive=r.is_active)


def permission_to_gql(p: models.Permission) -> Permission:
    return Permission(id=p.id, code=p.code, name=p.name, description=p.description, isActive=p.is_active)


def account_to_gql(a: models.Account) -> Account:
    return Account(
        id=a.id, companyId=a.company_id,
        accountType=AccountType(a.account_type.value),
        name=a.name, bankName=a.bank_name, accountNumber=a.account_number,
        clabe=a.clabe, cardLastDigits=a.card_last_digits,
        shortDescription=a.short_description, longDescription=a.long_description,
        isActive=a.is_active, createdAt=a.created_at, updatedAt=a.updated_at,
        company=Company(id=a.company.id, name=a.company.name, isActive=a.company.is_active),
    )


def concept_to_gql(c: models.Concept) -> Concept:
    return Concept(
        id=c.id, companyId=c.company_id,
        conceptType=ConceptType(c.concept_type.value),
        name=c.name, shortDescription=c.short_description,
        longDescription=c.long_description, isActive=c.is_active,
        createdAt=c.created_at, updatedAt=c.updated_at,
    )


def account_concept_to_gql(ac: models.AccountConcept) -> AccountConcept:
    return AccountConcept(
        id=ac.id, accountId=ac.account_id, conceptId=ac.concept_id,
        isActive=ac.is_active, createdAt=ac.created_at,
        account=account_to_gql(ac.account), concept=concept_to_gql(ac.concept),
    )


def transaction_to_gql(t: models.Transaction) -> Transaction:
    u = t.captured_by_user
    return Transaction(
        id=t.id, accountId=t.account_id, conceptId=t.concept_id,
        transactionType=TransactionType(t.transaction_type.value),
        amount=t.amount,
        transactionDate=fecha_utc_para_respuesta(t.transaction_date),
        capturedAt=fecha_utc_para_respuesta(t.captured_at),
        capturedBy=t.captured_by,
        shortDescription=t.short_description, longDescription=t.long_description,
        isActive=t.is_active, createdAt=t.created_at, updatedAt=t.updated_at,
        account=account_to_gql(t.account), concept=concept_to_gql(t.concept),
        capturedByUser=User(id=u.id, name=u.name, email=u.email),
    )


def balance_to_gql(f: dict) -> AccountBalance:
    return AccountBalance(
        accountId=str(f["accountId"]),
        accountName=f["accountName"],
        isActive=f["isActive"],
        openingBalance=f["openingBalance"],
        totalIncome=f["income"],
        totalExpense=f["expense"],
        profit=f["profit"],
        closingBalance=f["closingBalance"],
        isInRed=esta_en_rojo(f["closingBalance"]),
    )


def resolver_balance_general(info, fromDate: date, toDate: date) -> GeneralBalance:
    """Lógica común de generalBalance y de su alias companyBalance."""
    db = info.context["db"]
    actor = leer_actor(db, info)
    exigir_permisos_balance(db, actor["company_user"].id)
    try:
        r = calcular_balance_general(db, int(actor["company_id"]), fromDate, toDate)
    except ValueError as e:
        raise Exception(str(e))
    return GeneralBalance(
        companyId=str(r["companyId"]),
        currency="MXN",
        fromDate=fromDate,
        toDate=toDate,
        openingBalance=r["openingBalance"],
        totalIncome=r["income"],
        totalExpense=r["expense"],
        profit=r["profit"],
        closingBalance=r["closingBalance"],
        isInRed=r["isInRed"],
        accountsInRed=r["accountsInRed"],
        accounts=[balance_to_gql(c) for c in r["accounts"]],
    )


# --- PERMISOS ---
def exigir_permiso(db: Session, company_user_id: int, codigo: str) -> None:
    asignacion = (
        db.query(models.CompanyUserRole)
        .filter(
            models.CompanyUserRole.company_user_id == company_user_id,
            models.CompanyUserRole.is_active.is_(True),
        )
        .first()
    )
    if asignacion is None:
        raise Exception("La membresía no tiene un rol activo")
    permitido = (
        db.query(models.RolePermission)
        .join(models.Permission)
        .filter(
            models.RolePermission.role_id == asignacion.role_id,
            models.RolePermission.is_active.is_(True),
            models.Permission.code == codigo,
            models.Permission.is_active.is_(True),
        )
        .first()
    )
    if permitido is None:
        raise Exception(f"El rol no tiene el permiso {codigo}")

def exigir_permisos_balance(db: Session, company_user_id: int) -> None:
    """Los balances exigen AMBOS permisos de lectura (se consultan en cada petición)."""
    exigir_permiso(db, company_user_id, "accounts.read")
    exigir_permiso(db, company_user_id, "transactions.read")


def aplicar_permisos_rol(db: Session, role_id, permission_ids, antes_commit=None):
    """Operación completa y atómica de permisos de un rol."""
    try:
        ids = [int(value) for value in permission_ids]
        role_id = int(role_id)
        if role_id <= 0 or any(value <= 0 for value in ids):
            raise ValueError("Los IDs deben ser positivos")
        if len(ids) != len(set(ids)):
            raise ValueError("La lista de permisos contiene IDs duplicados")
        role = db.query(models.Role).filter(
            models.Role.id == role_id,
            models.Role.is_active.is_(True),
        ).first()
        if role is None:
            raise ValueError("El rol no existe o está inactivo")
        if role.code == "ADMINISTRADOR":
            raise ValueError("No se pueden modificar los permisos del rol ADMINISTRADOR")
        permisos = db.query(models.Permission).filter(
            models.Permission.id.in_(ids),
            models.Permission.is_active.is_(True),
        ).all() if ids else []
        if len(permisos) != len(ids):
            raise ValueError("Uno o más permisos no existen o están inactivos")
        relaciones = db.query(models.RolePermission).filter(
            models.RolePermission.role_id == role.id
        ).all()
        por_id = {r.permission_id: r for r in relaciones}
        deseados = set(ids)
        activated, deactivated, unchanged = [], [], []
        for permiso in permisos:
            relacion = por_id.get(permiso.id)
            if relacion is None:
                db.add(models.RolePermission(
                    role_id=role.id, permission_id=permiso.id, is_active=True
                ))
                activated.append(permiso)
            elif not relacion.is_active:
                relacion.is_active = True
                activated.append(permiso)
            else:
                unchanged.append(permiso)
        for relacion in relaciones:
            if relacion.is_active and relacion.permission_id not in deseados:
                relacion.is_active = False
                deactivated.append(relacion.permission)
        activated.sort(key=lambda p: p.code)
        deactivated.sort(key=lambda p: p.code)
        unchanged.sort(key=lambda p: p.code)
        changed = bool(activated or deactivated)
        db.flush()
        if antes_commit is not None:
            antes_commit()
        db.commit()
        return {
            "role": role, "activated": activated,
            "deactivated": deactivated, "unchanged": unchanged,
            "final_count": len(ids), "changed": changed,
        }
    except Exception:
        db.rollback()
        raise


# --- QUERIES ---
@strawberry.type
class Query:
    @strawberry.field
    def accounts(self, info: strawberry.Info, companyId: strawberry.ID,
                 accountType: Optional[AccountType] = None,
                 activeOnly: Optional[bool] = None) -> List[Account]:
        db = info.context["db"]
        actor = leer_actor(db, info)
        exigir_permiso(db, actor["company_user"].id, "accounts.read")
        if int(companyId) != int(actor["company_id"]):
            raise Exception("No puedes acceder a otra empresa")
        q = db.query(models.Account).filter(models.Account.company_id == companyId)
        if accountType:
            q = q.filter(models.Account.account_type == accountType.value)
        if activeOnly:
            q = q.filter(models.Account.is_active == True)
        return [account_to_gql(a) for a in q.all()]

    @strawberry.field
    def concepts(self, info: strawberry.Info, companyId: strawberry.ID,
                 conceptType: Optional[ConceptType] = None,
                 activeOnly: Optional[bool] = None) -> List[Concept]:
        db = info.context["db"]
        actor = leer_actor(db, info)
        exigir_permiso(db, actor["company_user"].id, "concepts.read")
        if int(companyId) != int(actor["company_id"]):
            raise Exception("No puedes acceder a otra empresa")
        q = db.query(models.Concept).filter(models.Concept.company_id == companyId)
        if conceptType:
            q = q.filter(models.Concept.concept_type == conceptType.value)
        if activeOnly:
            q = q.filter(models.Concept.is_active == True)
        return [concept_to_gql(c) for c in q.all()]

    @strawberry.field
    def accountConcepts(self, info: strawberry.Info, accountId: strawberry.ID) -> List[AccountConcept]:
        db = info.context["db"]
        actor = leer_actor(db, info)
        exigir_permiso(db, actor["company_user"].id, "concepts.read")
        cuenta = db.query(models.Account).filter(models.Account.id == accountId).first()
        if cuenta is None or int(cuenta.company_id) != int(actor["company_id"]):
            raise Exception("La cuenta no pertenece a tu empresa")
        q = db.query(models.AccountConcept).filter(
            models.AccountConcept.account_id == accountId,
            models.AccountConcept.is_active == True,
        )
        return [account_concept_to_gql(ac) for ac in q.all()]

    @strawberry.field
    def transactions(self, info: strawberry.Info, accountId: Optional[strawberry.ID] = None,
                     transactionType: Optional[TransactionType] = None,
                     limit: Optional[int] = 50, offset: Optional[int] = 0) -> List[Transaction]:
        db = info.context["db"]
        actor = leer_actor(db, info)
        exigir_permiso(db, actor["company_user"].id, "transactions.read")
        q = (
            db.query(models.Transaction)
            .join(models.Account, models.Transaction.account_id == models.Account.id)
            .filter(
                models.Transaction.is_active == True,
                models.Account.company_id == actor["company_id"],
            )
        )
        if accountId:
            q = q.filter(models.Transaction.account_id == accountId)
        if transactionType:
            q = q.filter(models.Transaction.transaction_type == transactionType.value)
        q = q.offset(offset).limit(limit)
        return [transaction_to_gql(t) for t in q.all()]

    @strawberry.field
    def roles(self, info: strawberry.Info, activeOnly: Optional[bool] = None) -> List[Role]:
        db = info.context["db"]
        actor = leer_actor(db, info)
        exigir_permiso(db, actor["company_user"].id, "roles.read")
        q = db.query(models.Role)
        if activeOnly:
            q = q.filter(models.Role.is_active == True)
        return [role_to_gql(r) for r in q.order_by(models.Role.id).all()]

    @strawberry.field
    def role(self, info: strawberry.Info, id: strawberry.ID) -> Optional[Role]:
        db = info.context["db"]
        actor = leer_actor(db, info)
        exigir_permiso(db, actor["company_user"].id, "roles.read")
        r = db.query(models.Role).filter(models.Role.id == id).first()
        return role_to_gql(r) if r else None

    @strawberry.field
    def permissions(self, info: strawberry.Info, activeOnly: Optional[bool] = None) -> List[Permission]:
        db = info.context["db"]
        actor = leer_actor(db, info)
        exigir_permiso(db, actor["company_user"].id, "roles.read")
        q = db.query(models.Permission)
        if activeOnly:
            q = q.filter(models.Permission.is_active == True)
        return [permission_to_gql(p) for p in q.order_by(models.Permission.id).all()]

    @strawberry.field
    def rolePermissions(self, info: strawberry.Info, roleId: strawberry.ID) -> List[RolePermissionType]:
        db = info.context["db"]
        actor = leer_actor(db, info)
        exigir_permiso(db, actor["company_user"].id, "roles.read")
        assignments = (
            db.query(models.RolePermission)
            .filter(
                models.RolePermission.role_id == roleId,
                models.RolePermission.is_active == True,
            )
            .all()
        )
        return [
            RolePermissionType(
                id=str(a.id),
                roleId=str(a.role_id),
                permissionId=str(a.permission_id),
                isActive=a.is_active,
                createdAt=a.created_at,
                role=role_to_gql(a.role),
                permission=permission_to_gql(a.permission),
            )
            for a in assignments
        ]

    @strawberry.field
    def users(self, info: strawberry.Info) -> List[User]:
        db = info.context["db"]
        actor = leer_actor(db, info)
        exigir_permiso(db, actor["company_user"].id, "company.users.read")
        return [User(id=u.id, name=u.name, email=u.email) for u in db.query(models.User).all()]

    @strawberry.field
    def companyUsers(self, info: strawberry.Info) -> List[CompanyUserType]:
        db = info.context["db"]
        actor = leer_actor(db, info)
        exigir_permiso(db, actor["company_user"].id, "company.users.read")
        memberships = db.query(models.CompanyUser).all()
        return [
            CompanyUserType(
                id=str(m.id),
                companyId=str(m.company_id),
                userId=str(m.user_id),
                isAdmin=m.is_admin,
                isActive=m.is_active,
            )
            for m in memberships
        ]

    # --- BALANCES (Actividad 7) ---
    @strawberry.field
    def accountBalance(self, info: strawberry.Info, accountId: strawberry.ID,
                       fromDate: date, toDate: date) -> AccountBalance:
        db = info.context["db"]
        actor = leer_actor(db, info)
        exigir_permisos_balance(db, actor["company_user"].id)
        # Cuenta inexistente, ID inválido o cuenta de otra empresa: MISMO error.
        try:
            id_cuenta = int(accountId)
        except (TypeError, ValueError):
            raise Exception("Cuenta no disponible")
        try:
            filas = calcular_balances_por_cuenta(
                db, int(actor["company_id"]), fromDate, toDate,
                account_id=id_cuenta,
            )
        except ValueError as e:
            raise Exception(str(e))
        if not filas:
            raise Exception("Cuenta no disponible")
        return balance_to_gql(filas[0])

    @strawberry.field
    def generalBalance(self, info: strawberry.Info, fromDate: date, toDate: date) -> GeneralBalance:
        return resolver_balance_general(info, fromDate, toDate)

    @strawberry.field
    def companyBalance(self, info: strawberry.Info, fromDate: date, toDate: date) -> GeneralBalance:
        # Alias de compatibilidad con consultas anteriores a generalBalance.
        return resolver_balance_general(info, fromDate, toDate)


# --- MUTATIONS ---
@strawberry.type
class Mutation:
    @strawberry.mutation
    def setRolePermissions(self, info: strawberry.Info, input: SetRolePermissionsInput) -> RolePermissionUpdate:
        db = info.context["db"]
        try:
            actor = leer_actor(db, info)
            exigir_permiso(db, actor["company_user"].id, "roles.write")
            resultado = aplicar_permisos_rol(db, input.roleId, input.permissionIds)
            return RolePermissionUpdate(
                role=role_to_gql(resultado["role"]),
                activated=[permission_to_gql(p) for p in resultado["activated"]],
                deactivated=[permission_to_gql(p) for p in resultado["deactivated"]],
                unchanged=[permission_to_gql(p) for p in resultado["unchanged"]],
                finalCount=resultado["final_count"],
                changed=resultado["changed"],
            )
        except Exception:
            db.rollback()
            raise

    @strawberry.mutation
    def login(self, info: strawberry.Info, input: LoginInput) -> AuthPayload:
        db = info.context["db"]
        user = db.query(models.User).filter(models.User.email == input.email).first()
        if not user or not verify_password(input.password, user.hashed_password):
            raise Exception("Credenciales incorrectas")
        if not user.is_active:
            raise Exception("Usuario inactivo")
        membresia = (
            db.query(models.CompanyUser)
            .filter(models.CompanyUser.user_id == user.id,
                    models.CompanyUser.is_active == True)
            .first()
        )
        if membresia is None:
            raise Exception("El usuario no tiene una membresía activa")
        token = crear_token(company_user_id=membresia.id, company_id=membresia.company_id)
        return AuthPayload(
            token=token,
            tokenType="Bearer",
            user=User(id=user.id, name=user.name, email=user.email),
        )

    @strawberry.mutation
    def createRole(self, info: strawberry.Info, input: CreateRoleInput) -> Role:
        db = info.context["db"]
        actor = leer_actor(db, info)
        exigir_permiso(db, actor["company_user"].id, "roles.write")
        if db.query(models.Role).filter(models.Role.code == input.code).first():
            raise Exception("Ya existe un rol con ese código")
        r = models.Role(code=input.code, name=input.name, description=input.description)
        db.add(r)
        db.commit()
        db.refresh(r)
        return role_to_gql(r)

    @strawberry.mutation
    def deactivateRole(self, info: strawberry.Info, id: strawberry.ID) -> Role:
        db = info.context["db"]
        actor = leer_actor(db, info)
        exigir_permiso(db, actor["company_user"].id, "roles.write")
        r = db.query(models.Role).filter(models.Role.id == id).first()
        if not r:
            raise Exception("Rol no encontrado")
        r.is_active = False
        db.commit()
        db.refresh(r)
        return role_to_gql(r)

    @strawberry.mutation
    def createPermission(self, info: strawberry.Info, input: CreatePermissionInput) -> Permission:
        db = info.context["db"]
        actor = leer_actor(db, info)
        exigir_permiso(db, actor["company_user"].id, "roles.write")
        if db.query(models.Permission).filter(models.Permission.code == input.code).first():
            raise Exception("Ya existe un permiso con ese código")
        p = models.Permission(code=input.code, name=input.name, description=input.description)
        db.add(p)
        db.commit()
        db.refresh(p)
        return permission_to_gql(p)

    @strawberry.mutation
    def createAccount(self, info: strawberry.Info, input: CreateAccountInput) -> Account:
        db = info.context["db"]
        actor = leer_actor(db, info)
        exigir_permiso(db, actor["company_user"].id, "accounts.write")
        if int(input.companyId) != int(actor["company_id"]):
            raise Exception("No puedes acceder a otra empresa")
        existing = db.query(models.Account).filter(
            models.Account.company_id == input.companyId,
            models.Account.name == input.name,
        ).first()
        if existing:
            raise Exception("La cuenta ya existe para esta empresa")
        db_a = models.Account(
            company_id=input.companyId, account_type=input.accountType.value,
            name=input.name, bank_name=input.bankName,
            account_number=input.accountNumber, clabe=input.clabe,
            card_last_digits=input.cardLastDigits,
            short_description=input.shortDescription,
            long_description=input.longDescription,
        )
        db.add(db_a)
        db.commit()
        db.refresh(db_a)
        return account_to_gql(db_a)

    @strawberry.mutation
    def deactivateAccount(self, info: strawberry.Info, id: strawberry.ID) -> Account:
        """Soft-delete de cuenta: se marca inactiva; su historial se conserva."""
        db = info.context["db"]
        actor = leer_actor(db, info)
        exigir_permiso(db, actor["company_user"].id, "accounts.write")
        cuenta = db.query(models.Account).filter(models.Account.id == id).first()
        if cuenta is None or int(cuenta.company_id) != int(actor["company_id"]):
            raise Exception("Cuenta no disponible")
        cuenta.is_active = False
        db.commit()
        db.refresh(cuenta)
        return account_to_gql(cuenta)

    @strawberry.mutation
    def createConcept(self, info: strawberry.Info, input: CreateConceptInput) -> Concept:
        db = info.context["db"]
        actor = leer_actor(db, info)
        exigir_permiso(db, actor["company_user"].id, "concepts.write")
        if int(input.companyId) != int(actor["company_id"]):
            raise Exception("No puedes acceder a otra empresa")
        existing = db.query(models.Concept).filter(
            models.Concept.company_id == input.companyId,
            models.Concept.name == input.name,
        ).first()
        if existing:
            raise Exception("El concepto ya existe para esta empresa")
        db_c = models.Concept(
            company_id=input.companyId, concept_type=input.conceptType.value,
            name=input.name, short_description=input.shortDescription,
            long_description=input.longDescription,
        )
        db.add(db_c)
        db.commit()
        db.refresh(db_c)
        return concept_to_gql(db_c)

    @strawberry.mutation
    def assignConceptToAccount(self, info: strawberry.Info, input: AssignConceptToAccountInput) -> AccountConcept:
        db = info.context["db"]
        actor = leer_actor(db, info)
        exigir_permiso(db, actor["company_user"].id, "concepts.write")
        cuenta = db.query(models.Account).filter(models.Account.id == input.accountId).first()
        concepto = db.query(models.Concept).filter(models.Concept.id == input.conceptId).first()
        if (not cuenta or not concepto
                or int(cuenta.company_id) != int(actor["company_id"])
                or int(concepto.company_id) != int(actor["company_id"])):
            raise Exception("La cuenta y el concepto deben pertenecer a tu empresa")
        existing = db.query(models.AccountConcept).filter(
            models.AccountConcept.account_id == input.accountId,
            models.AccountConcept.concept_id == input.conceptId,
        ).first()
        if existing:
            if not existing.is_active:
                existing.is_active = True
                db.commit()
                db.refresh(existing)
                return account_concept_to_gql(existing)
            raise Exception("La relación cuenta-concepto ya existe")
        db_ac = models.AccountConcept(account_id=input.accountId, concept_id=input.conceptId)
        db.add(db_ac)
        db.commit()
        db.refresh(db_ac)
        return account_concept_to_gql(db_ac)

    @strawberry.mutation
    def removeConceptFromAccount(self, info: strawberry.Info, accountId: strawberry.ID,
                                 conceptId: strawberry.ID) -> bool:
        db = info.context["db"]
        actor = leer_actor(db, info)
        exigir_permiso(db, actor["company_user"].id, "concepts.write")
        cuenta = db.query(models.Account).filter(models.Account.id == accountId).first()
        if cuenta is None or int(cuenta.company_id) != int(actor["company_id"]):
            raise Exception("La cuenta no pertenece a tu empresa")
        ac = db.query(models.AccountConcept).filter(
            models.AccountConcept.account_id == accountId,
            models.AccountConcept.concept_id == conceptId,
        ).first()
        if not ac:
            raise Exception("Relación no encontrada")
        ac.is_active = False
        db.commit()
        return True

    @strawberry.mutation
    def createTransaction(self, info: strawberry.Info, input: CreateTransactionInput) -> Transaction:
        db = info.context["db"]
        actor = leer_actor(db, info)
        exigir_permiso(db, actor["company_user"].id, "transactions.write")
        user = db.query(models.User).filter(models.User.id == actor["company_user"].user_id).first()
        if user is None or not user.is_active:
            raise Exception("Usuario inactivo o inexistente")

        try:
            monto_validado = validar_monto(input.amount)
        except ValueError as e:
            raise Exception(str(e))

        account = db.query(models.Account).filter(
            models.Account.id == input.accountId, models.Account.is_active == True
        ).first()
        if not account:
            raise Exception("La cuenta no existe.")
        concept = db.query(models.Concept).filter(
            models.Concept.id == input.conceptId, models.Concept.is_active == True
        ).first()
        if not concept:
            raise Exception("El concepto no existe.")

        if (int(account.company_id) != int(actor["company_id"])
                or int(concept.company_id) != int(actor["company_id"])):
            raise Exception("La cuenta y el concepto deben pertenecer a tu empresa")

        allowed = db.query(models.AccountConcept).filter(
            models.AccountConcept.account_id == account.id,
            models.AccountConcept.concept_id == concept.id,
            models.AccountConcept.is_active == True,
        ).first()
        if not allowed:
            raise Exception("El concepto no está permitido para la cuenta seleccionada.")

        if input.transactionType.value != concept.concept_type.value:
            raise Exception("El tipo de movimiento debe ser compatible con el tipo de concepto.")

        # La fecha de operación debe traer zona horaria; se guarda en UTC naive.
        if input.transactionDate is not None:
            try:
                fecha_operacion = normalizar_datetime_utc(input.transactionDate)
            except ValueError as e:
                raise Exception(str(e))
        else:
            fecha_operacion = ahora_utc_naive()

        db_t = models.Transaction(
            account_id=input.accountId, concept_id=input.conceptId,
            transaction_type=input.transactionType.value, amount=monto_validado,
            transaction_date=fecha_operacion,
            captured_at=ahora_utc_naive(),
            captured_by=user.id,
            short_description=input.shortDescription,
            long_description=input.longDescription,
        )
        db.add(db_t)
        db.commit()
        db.refresh(db_t)
        return transaction_to_gql(db_t)

    @strawberry.mutation
    def deleteTransaction(self, info: strawberry.Info, id: strawberry.ID) -> Transaction:
        db = info.context["db"]
        actor = leer_actor(db, info)
        exigir_permiso(db, actor["company_user"].id, "transactions.write")
        t = db.query(models.Transaction).filter(models.Transaction.id == id).first()
        if not t:
            raise Exception("Movimiento no encontrado")
        if int(t.account.company_id) != int(actor["company_id"]):
            raise Exception("No puedes modificar movimientos de otra empresa")
        t.is_active = False
        db.commit()
        db.refresh(t)
        return transaction_to_gql(t)

    @strawberry.mutation
    def assignPermissionToRole(self, info: strawberry.Info, roleId: strawberry.ID,
                               permissionId: strawberry.ID) -> RolePermissionType:
        db = info.context["db"]
        actor = leer_actor(db, info)
        exigir_permiso(db, actor["company_user"].id, "roles.write")
        role = db.query(models.Role).filter(models.Role.id == roleId).first()
        if not role:
            raise Exception("Rol no encontrado")
        permission = db.query(models.Permission).filter(models.Permission.id == permissionId).first()
        if not permission:
            raise Exception("Permiso no encontrado")
        assignment = db.query(models.RolePermission).filter(
            models.RolePermission.role_id == roleId,
            models.RolePermission.permission_id == permissionId,
        ).first()
        if assignment:
            if assignment.is_active:
                raise Exception("El permiso ya está asignado a este rol")
            assignment.is_active = True
        else:
            assignment = models.RolePermission(
                role_id=role.id, permission_id=permission.id, is_active=True
            )
            db.add(assignment)
        db.commit()
        db.refresh(assignment)
        return RolePermissionType(
            id=str(assignment.id),
            roleId=str(assignment.role_id),
            permissionId=str(assignment.permission_id),
            isActive=assignment.is_active,
            createdAt=assignment.created_at,
            role=role_to_gql(role),
            permission=permission_to_gql(permission),
        )

    @strawberry.mutation
    def removePermissionFromRole(self, info: strawberry.Info, roleId: strawberry.ID,
                                 permissionId: strawberry.ID) -> bool:
        db = info.context["db"]
        actor = leer_actor(db, info)
        exigir_permiso(db, actor["company_user"].id, "roles.write")
        assignment = db.query(models.RolePermission).filter(
            models.RolePermission.role_id == roleId,
            models.RolePermission.permission_id == permissionId,
        ).first()
        if not assignment:
            raise Exception("La asignación entre el rol y el permiso no existe")
        if not assignment.is_active:
            raise Exception("La asignación ya está desactivada")
        assignment.is_active = False
        db.commit()
        return True

    @strawberry.mutation
    def assignRole(self, info: strawberry.Info, companyUserId: strawberry.ID,
                   roleId: strawberry.ID) -> bool:
        db = info.context["db"]
        actor = leer_actor(db, info)
        exigir_permiso(db, actor["company_user"].id, "roles.write")
        company_user = db.query(models.CompanyUser).filter(
            models.CompanyUser.id == companyUserId
        ).first()
        if not company_user:
            raise Exception("La membresía del usuario no existe")
        if int(company_user.company_id) != int(actor["company_id"]):
            raise Exception("No puedes modificar miembros de otra empresa")
        if not company_user.is_active:
            raise Exception("La membresía del usuario está inactiva")
        role = db.query(models.Role).filter(models.Role.id == roleId).first()
        if not role:
            raise Exception("El rol no existe")
        if not role.is_active:
            raise Exception("El rol está inactivo")
        try:
            assignment = db.query(models.CompanyUserRole).filter(
                models.CompanyUserRole.company_user_id == company_user.id,
                models.CompanyUserRole.role_id == role.id,
            ).first()
            active_assignments = db.query(models.CompanyUserRole).filter(
                models.CompanyUserRole.company_user_id == company_user.id,
                models.CompanyUserRole.is_active == True,
            ).all()
            for current in active_assignments:
                current.is_active = False
            if assignment:
                assignment.is_active = True
            else:
                db.add(models.CompanyUserRole(
                    company_user_id=company_user.id, role_id=role.id, is_active=True
                ))
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise

    @strawberry.mutation
    def createCompanyAdmin(self, info: strawberry.Info, companyName: str, adminName: str,
                           adminEmail: str, adminPassword: str) -> bool:
        db = info.context["db"]
        try:
            if db.query(models.User).filter(models.User.email == adminEmail).first():
                raise Exception("El correo ya está registrado")
            admin_role = db.query(models.Role).filter(
                models.Role.code == "ADMINISTRADOR",
                models.Role.is_active == True,
            ).first()
            if not admin_role:
                raise Exception("No existe un rol ADMINISTRADOR activo")
            company = models.Company(name=companyName, is_active=True)
            db.add(company)
            db.flush()
            user = models.User(
                name=adminName, email=adminEmail,
                hashed_password=get_password_hash(adminPassword), is_active=True,
            )
            db.add(user)
            db.flush()
            membership = models.CompanyUser(
                company_id=company.id, user_id=user.id, is_admin=True, is_active=True
            )
            db.add(membership)
            db.flush()
            db.add(models.CompanyUserRole(
                company_user_id=membership.id, role_id=admin_role.id, is_active=True
            ))
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise


schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_app = GraphQLRouter(schema, context_getter=get_context)

app = FastAPI(title="Sistema Financiero API - Actividad 7")
app.include_router(graphql_app, prefix="/graphql")