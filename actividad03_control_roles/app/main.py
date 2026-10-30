from fastapi import FastAPI, Depends, Request, HTTPException
import strawberry
from strawberry.fastapi import GraphQLRouter
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from jose import jwt, JWTError
import bcrypt
from decimal import Decimal
from .database import engine, Base, get_db, SessionLocal
from . import models

# --- SEGURIDAD ---
SECRET_KEY = "clave_super_secreta_jwt"
ALGORITHM = "HS256"

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict):
    to_encode = data.copy()
    to_encode.update({"exp": datetime.utcnow() + timedelta(hours=2)})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user_from_token(token: str, db: Session):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None: return None
        return db.query(models.User).filter(models.User.email == email).first()
    except JWTError:
        return None

Base.metadata.create_all(bind=engine)
# Parte 1 de la actividad 3 - Datos iniciales: roles y permisos

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

##

#Matriz inicial de permisos por rol 

MATRIZ_PERMISOS = {
    "ADMINISTRADOR": [
        "company.users.read",
        "company.users.write",
        "accounts.read",
        "accounts.write",
        "concepts.read",
        "concepts.write",
        "transactions.read",
        "transactions.write",
        "roles.read",
        "roles.write",
    ],
    "CONTADOR": [
        "company.users.read",
        "accounts.read",
        "accounts.write",
        "concepts.read",
        "concepts.write",
        "transactions.read",
        "transactions.write",
        "roles.read",
    ],
    "CAPTURISTA": [
        "accounts.read",
        "concepts.read",
        "transactions.read",
        "transactions.write",
    ],
    "CONSULTA": [
        "company.users.read",
        "accounts.read",
        "concepts.read",
        "transactions.read",
    ],
}


def seed_role_permissions():
    db = SessionLocal()

    try:
        for role_code, permission_codes in MATRIZ_PERMISOS.items():

            # Buscar el rol por su código
            role = db.query(models.Role).filter(
                models.Role.code == role_code
            ).first()

            if role is None:
                continue

            # Si el rol ya tiene asignaciones, no volver a cargarlas
            existing = db.query(models.RolePermission).filter(
                models.RolePermission.role_id == role.id
            ).first()

            if existing:
                continue

            # Buscar y asignar cada permiso de la matriz
            for permission_code in permission_codes:
                permission = db.query(models.Permission).filter(
                    models.Permission.code == permission_code
                ).first()

                if permission is None:
                    raise ValueError(
                        f"No existe el permiso: {permission_code}"
                    )

                assignment = models.RolePermission(
                    role_id=role.id,
                    permission_id=permission.id,
                    is_active=True,
                )

                db.add(assignment)

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


##


def seed_roles_y_permisos():
    db = SessionLocal()
    try:
        if db.query(models.Role).count() == 0:
            for code, name, desc in ROLES_INICIALES:
                db.add(models.Role(code=code, name=name, description=desc))
        if db.query(models.Permission).count()== 0:
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

# Class Role
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



# Tipo GraphQL para la relación rol-permiso

@strawberry.type
class RolePermissionType:
    id: strawberry.ID
    roleId: strawberry.ID
    permissionId: strawberry.ID
    isActive: bool
    createdAt: datetime
    role: Role
    permission: Permission


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

# Clase CreateRoleInput
@strawberry.input
class CreateRoleInput:
    code: str
    name: str
    description: Optional[str]

# Clase CreatePermission Input
@strawberry.input
class CreatePermissionInput:
    code: str
    name: str
    description: Optional[str] 
# --- DEPENDENCIAS ---
async def get_context(request: Request, db: Session = Depends(get_db)):
    return {"db": db, "request": request}
# Implementando los métodos convertidores
def role_to_gql(r: models.Role) -> Role:
    return Role(id=r.id, code=r.code, name=r.name, description=r.description, isActive=r.is_active)

def permission_to_gql(p: models.Permission) -> Permission:
    return Permission(id=p.id, code=p.code, name=p.name, description=p.description, isActive=p.is_active)

def account_to_gql(a: models.Account) -> Account:
    return Account(
        id=a.id,
        companyId=a.company_id,
        accountType=AccountType(a.account_type.value),
        name=a.name,
        bankName=a.bank_name,
        accountNumber=a.account_number,
        clabe=a.clabe,
        cardLastDigits=a.card_last_digits,
        shortDescription=a.short_description,
        longDescription=a.long_description,
        isActive=a.is_active,
        createdAt=a.created_at,
        updatedAt=a.updated_at,
        company=Company(id=a.company.id, name=a.company.name, isActive=a.company.is_active),
    )

def concept_to_gql(c: models.Concept) -> Concept:
    return Concept(
        id=c.id,
        companyId=c.company_id,
        conceptType=ConceptType(c.concept_type.value),
        name=c.name,
        shortDescription=c.short_description,
        longDescription=c.long_description,
        isActive=c.is_active,
        createdAt=c.created_at,
        updatedAt=c.updated_at,
    )

def transaction_to_gql(t: models.Transaction) -> Transaction:
    user = t.captured_by_user
    return Transaction(
        id=t.id,
        accountId=t.account_id,
        conceptId=t.concept_id,
        transactionType=TransactionType(t.transaction_type.value),
        amount=t.amount,
        transactionDate=t.transaction_date,
        capturedAt=t.captured_at,
        capturedBy=t.captured_by,
        shortDescription=t.short_description,
        longDescription=t.long_description,
        isActive=t.is_active,
        createdAt=t.created_at,
        updatedAt=t.updated_at,
        account=account_to_gql(t.account),
        concept=concept_to_gql(t.concept),
        capturedByUser=User(id=user.id, name=user.name, email=user.email),
    )

def exigir_permiso(db: Session, company_user_id: int, codigo: str) -> None:
    asignacion = (
        db.query(models.CompanyUserRole)
        .filter(
            models.CompanyUserRole.company_user_id == company_user_id,
            models.CompanyUserRole.is_active.is_(True)
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
            models.Permission.is_active.is_(True)
        )
        .first()
    )
    if permitido is None:
        raise Exception(f"El rol no tiene el permiso {codigo}")

# --- QUERIES ---
@strawberry.type
class Query:
    @strawberry.field
    def accounts(self, info: strawberry.Info, companyId: strawberry.ID, actorCompanyUserId: strawberry.ID, accountType: Optional[AccountType] = None, activeOnly: Optional[bool] = None) -> List[Account]:
        db = info.context["db"]
        exigir_permiso(db, int(actorCompanyUserId), "accounts.read")
        q = db.query(models.Account).filter(models.Account.company_id == companyId)
        if accountType: q = q.filter(models.Account.account_type == accountType.value)
        if activeOnly: q = q.filter(models.Account.is_active == True)
        return [account_to_gql(a) for a in q.all()]

    @strawberry.field
    def concepts(self, info: strawberry.Info, companyId: strawberry.ID, actorCompanyUserId: strawberry.ID, conceptType: Optional[ConceptType] = None, activeOnly: Optional[bool] = None) -> List[Concept]:
        db = info.context["db"]
        exigir_permiso(db, int(actorCompanyUserId), "concepts.read")
        q = db.query(models.Concept).filter(models.Concept.company_id == companyId)
        if conceptType: q = q.filter(models.Concept.concept_type == conceptType.value)
        if activeOnly: q = q.filter(models.Concept.is_active == True)
        return [concept_to_gql(c) for c in q.all()]

    @strawberry.field
    def accountConcepts(self, info: strawberry.Info, accountId: strawberry.ID) -> List[AccountConcept]:
        db = info.context["db"]
        q = db.query(models.AccountConcept).filter(models.AccountConcept.account_id == accountId, models.AccountConcept.is_active == True)
        res = []
        for ac in q.all():
            a = ac.account
            c = ac.concept
            gql_a = account_to_gql(a)
            gql_c = concept_to_gql(c)
            res.append(AccountConcept(id=ac.id, accountId=ac.account_id, conceptId=ac.concept_id, isActive=ac.is_active, createdAt=ac.created_at, account=gql_a, concept=gql_c))
        return res

    @strawberry.field
    def transactions(self, info: strawberry.Info, actorCompanyUserId: strawberry.ID, accountId: Optional[strawberry.ID] = None, transactionType: Optional[TransactionType] = None, limit: Optional[int] = 50, offset: Optional[int] = 0) -> List[Transaction]:
        db = info.context["db"]
        exigir_permiso(db, int(actorCompanyUserId), "transactions.read")
        q = db.query(models.Transaction).filter(models.Transaction.is_active == True)
        if accountId: q = q.filter(models.Transaction.account_id == accountId)
        if transactionType: q = q.filter(models.Transaction.transaction_type == transactionType.value)
        q = q.offset(offset).limit(limit)
        return [transaction_to_gql(t) for t in q.all()]

    # Implementación de campos (roles, rol y permisos)

    # Roles
    @strawberry.field
    def roles(self, info: strawberry.Info, activeOnly: Optional[bool] = None) -> List[Role]:
        db = info.context["db"]
        q = db.query(models.Role)
        if activeOnly: q = q.filter(models.Role.is_active == True)
        return [role_to_gql(r) for r in q.order_by(models.Role.id).all()]

    # Rol
    @strawberry.field
    def role(self, info: strawberry.Info, id: strawberry.ID) -> Optional[Role]:
        db = info.context["db"]
        r = db.query(models.Role).filter(models.Role.id == id).first()
        return role_to_gql(r) if r else None

    # Permisos
    @strawberry.field
    def permissions(self, info: strawberry.Info, activeOnly: Optional[bool] = None) -> List[Permission]:
        db = info.context["db"]
        q = db.query(models.Permission)
        if activeOnly: q = q.filter(models.Permission.is_active == True)
        return [permission_to_gql(p) for p in q.order_by(models.Permission.id).all()]
    
    
    # Consultar permisos de un rol 

    @strawberry.field
    def rolePermissions(
        self,
        info: strawberry.Info,
        roleId: strawberry.ID
    ) -> List[RolePermissionType]:

        db = info.context["db"]

        assignments = (
            db.query(models.RolePermission)
            .filter(
                models.RolePermission.role_id == roleId,
                models.RolePermission.is_active == True
            )
            .all()
        )

        result = []

        for assignment in assignments:
            result.append(
                RolePermissionType(
                    id=str(assignment.id),
                    roleId=str(assignment.role_id),
                    permissionId=str(assignment.permission_id),
                    isActive=assignment.is_active,
                    createdAt=assignment.created_at,
                    role=role_to_gql(assignment.role),
                    permission=permission_to_gql(
                        assignment.permission
                    )
                )
            )

        return result

    
    @strawberry.field
    def users(self, info: strawberry.Info) -> List[User]:
        db = info.context["db"]
        db_users = db.query(models.User).all()
        return [User(id=u.id, name=u.name, email=u.email) for u in db_users]

    
    
    @strawberry.field
    def companyUsers(self, info: strawberry.Info) -> List[CompanyUserType]:
        db = info.context["db"]

        memberships = db.query(models.CompanyUser).all()

        return [
            CompanyUserType(
                id=str(membership.id),
                companyId=str(membership.company_id),
                userId=str(membership.user_id),
                isAdmin=membership.is_admin,
                isActive=membership.is_active
            )
            for membership in memberships
        ]
    

    
# --- MUTATIONS ---
@strawberry.type
class Mutation:
    # (Omitimos CRUD empresa por espacio, ya están en DB si usas la anterior)
    
    @strawberry.mutation
    def login(self, info: strawberry.Info, input: LoginInput) -> AuthPayload:
        db = info.context["db"]
        user = db.query(models.User).filter(models.User.email == input.email).first()
        if not user or not verify_password(input.password, user.hashed_password):
            raise Exception("Credenciales incorrectas")
        return AuthPayload(token=create_access_token(data={"sub": user.email}), tokenType="Bearer")
    
    # CreateRole
    @strawberry.mutation
    def createRole(self, info: strawberry.Info, input: CreateRoleInput) -> Role:
        db = info.context["db"]
        if db.query(models.Role).filter(models.Role.code == input.code).first():
            raise Exception("Ya existe un rol con ese código")
        r = models.Role(code=input.code, name=input.name, description=input.description)
        db.add(r)
        db.commit()
        db.refresh(r)
        return role_to_gql(r)

    # Desactivar un rol
    @strawberry.mutation
    def deactivateRole(self, info: strawberry.Info, id: strawberry.ID) -> Role:
        db = info.context["db"]
        r = db.query(models.Role).filter(models.Role.id == id).first()
        if not r: raise Exception("Rol no encontrado")
        r.is_active = False
        db.commit()
        db.refresh(r)
        return role_to_gql(r)

    # Crear un permiso
    @strawberry.mutation
    def createPermission(self, info: strawberry.Info, input: CreatePermissionInput) -> Permission:
        db = info.context["db"]
        if db.query(models.Permission).filter(models.Permission.code == input.code).first():
            raise Exception("Ya existe un permiso con ese código")
        p = models.Permission(code=input.code, name=input.name, description=input.description)
        db.add(p)
        db.commit()
        db.refresh(p)
        return permission_to_gql(p)
    
    @strawberry.mutation
    def createAccount(self, info: strawberry.Info, input: CreateAccountInput, actorCompanyUserId: strawberry.ID) -> Account:
        db = info.context["db"]
        exigir_permiso(db, int(actorCompanyUserId), "accounts.write")
        # Validar duplicidad
        existing = db.query(models.Account).filter(models.Account.company_id == input.companyId, models.Account.name == input.name).first()
        if existing: raise Exception("La cuenta ya existe para esta empresa")
        
        db_a = models.Account(company_id=input.companyId, account_type=input.accountType.value, name=input.name, bank_name=input.bankName, account_number=input.accountNumber, clabe=input.clabe, card_last_digits=input.cardLastDigits, short_description=input.shortDescription, long_description=input.longDescription)
        db.add(db_a)
        db.commit()
        db.refresh(db_a)
        return Query.accounts(None, info, companyId=input.companyId, actorCompanyUserId=actorCompanyUserId)[-1]

    @strawberry.mutation
    def createConcept(self, info: strawberry.Info, input: CreateConceptInput, actorCompanyUserId: strawberry.ID) -> Concept:
        db = info.context["db"]
        exigir_permiso(db, int(actorCompanyUserId), "concepts.write")
        existing = db.query(models.Concept).filter(models.Concept.company_id == input.companyId, models.Concept.name == input.name).first()
        if existing: raise Exception("El concepto ya existe para esta empresa")
        
        db_c = models.Concept(company_id=input.companyId, concept_type=input.conceptType.value, name=input.name, short_description=input.shortDescription, long_description=input.longDescription)
        db.add(db_c)
        db.commit()
        db.refresh(db_c)
        return Query.concepts(None, info, companyId=input.companyId, actorCompanyUserId=actorCompanyUserId)[-1]

    @strawberry.mutation
    def assignConceptToAccount(self, info: strawberry.Info, input: AssignConceptToAccountInput, actorCompanyUserId: strawberry.ID) -> AccountConcept:
        db = info.context["db"]
        exigir_permiso(db, int(actorCompanyUserId), "concepts.write")
        existing = db.query(models.AccountConcept).filter(models.AccountConcept.account_id == input.accountId, models.AccountConcept.concept_id == input.conceptId).first()
        if existing:
            if not existing.is_active:
                existing.is_active = True
                db.commit()
                return Query.accountConcepts(None, info, accountId=input.accountId)[-1]
            raise Exception("La relación cuenta-concepto ya existe")
            
        db_ac = models.AccountConcept(account_id=input.accountId, concept_id=input.conceptId)
        db.add(db_ac)
        db.commit()
        return Query.accountConcepts(None, info, accountId=input.accountId)[-1]

    @strawberry.mutation
    def removeConceptFromAccount(self, info: strawberry.Info, accountId: strawberry.ID, conceptId: strawberry.ID) -> bool:
        db = info.context["db"]
        ac = db.query(models.AccountConcept).filter(models.AccountConcept.account_id == accountId, models.AccountConcept.concept_id == conceptId).first()
        if not ac: raise Exception("Relación no encontrada")
        ac.is_active = False
        db.commit()
        return True

    @strawberry.mutation
    def createTransaction(self, info: strawberry.Info, input: CreateTransactionInput, actorCompanyUserId: strawberry.ID) -> Transaction:
        db = info.context["db"]
        exigir_permiso(db, int(actorCompanyUserId), "transactions.write")
        request = info.context["request"]
        
        # Validación: Usuario autenticado
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "): raise Exception("El usuario debe estar autenticado. Pasa el token en el header Authorization.")
        token = auth_header.split(" ")[1]
        user = get_current_user_from_token(token, db)
        if not user: raise Exception("Token inválido o expirado.")
        
        # Validación: Monto > 0
        if input.amount <= 0: raise Exception("El monto del movimiento debe ser mayor que cero.")
        
        # Validación: Cuenta y concepto existen
        account = db.query(models.Account).filter(models.Account.id == input.accountId, models.Account.is_active == True).first()
        if not account: raise Exception("La cuenta no existe.")
        concept = db.query(models.Concept).filter(models.Concept.id == input.conceptId, models.Concept.is_active == True).first()
        if not concept: raise Exception("El concepto no existe.")
        
        # Validación: Misma empresa
        if account.company_id != concept.company_id: raise Exception("La cuenta, el concepto y el usuario deben corresponder a la misma empresa.")
        user_in_company = db.query(models.CompanyUser).filter(models.CompanyUser.user_id == user.id, models.CompanyUser.company_id == account.company_id).first()
        if not user_in_company: raise Exception("La cuenta, el concepto y el usuario deben corresponder a la misma empresa.")
        
        # Validación: Concepto permitido
        allowed = db.query(models.AccountConcept).filter(models.AccountConcept.account_id == account.id, models.AccountConcept.concept_id == concept.id, models.AccountConcept.is_active == True).first()
        if not allowed: raise Exception("El concepto no está permitido para la cuenta seleccionada.")
        
        # Validación: Tipo compatible
        if input.transactionType.value != concept.concept_type.value: raise Exception("El tipo de movimiento debe ser compatible con el tipo de concepto.")
        
        db_t = models.Transaction(account_id=input.accountId, concept_id=input.conceptId, transaction_type=input.transactionType.value, amount=input.amount, transaction_date=input.transactionDate or datetime.utcnow(), captured_by=user.id, short_description=input.shortDescription, long_description=input.longDescription)
        db.add(db_t)
        db.commit()
        db.refresh(db_t)
        
        return Query.transactions(None, info, accountId=input.accountId, actorCompanyUserId=actorCompanyUserId)[-1]

    @strawberry.mutation
    def deleteTransaction(self, info: strawberry.Info, id: strawberry.ID) -> Transaction:
        db = info.context["db"]
        t = db.query(models.Transaction).filter(models.Transaction.id == id).first()
        if not t: raise Exception("Movimiento no encontrado")
        t.is_active = False
        db.commit()
        return Query.transactions(None, info, accountId=t.account_id)[0]
    
    #  Asignar un permiso a un rol 

    @strawberry.mutation
    def assignPermissionToRole(
        self,
        info: strawberry.Info,
        roleId: strawberry.ID,
        permissionId: strawberry.ID,
        actorCompanyUserId: strawberry.ID
    ) -> RolePermissionType:

        db = info.context["db"]
        exigir_permiso(db, int(actorCompanyUserId), "roles.write")

        # 1. Verificar que el rol exista
        role = db.query(models.Role).filter(
            models.Role.id == roleId
        ).first()

        if not role:
            raise Exception("Rol no encontrado")

        # 2. Verificar que el permiso exista
        permission = db.query(models.Permission).filter(
            models.Permission.id == permissionId
        ).first()

        if not permission:
            raise Exception("Permiso no encontrado")

        # 3. Buscar si la relación ya existe
        assignment = db.query(models.RolePermission).filter(
            models.RolePermission.role_id == roleId,
            models.RolePermission.permission_id == permissionId
        ).first()

        if assignment:
            if assignment.is_active:
                raise Exception(
                    "El permiso ya está asignado a este rol"
                )

            # Si existía, pero estaba desactivada, reactivarla
            assignment.is_active = True

        else:
            # 4. Crear una nueva relación
            assignment = models.RolePermission(
                role_id=role.id,
                permission_id=permission.id,
                is_active=True
            )

            db.add(assignment)

        # 5. Guardar y recuperar el registro
        db.commit()
        db.refresh(assignment)

        return RolePermissionType(
            id=str(assignment.id),
            roleId=str(assignment.role_id),
            permissionId=str(assignment.permission_id),
            isActive=assignment.is_active,
            createdAt=assignment.created_at,
            role=role_to_gql(role),
            permission=permission_to_gql(permission)
        )
    
    # Desactivar un permiso de un rol

    @strawberry.mutation
    def removePermissionFromRole(
        self,
        info: strawberry.Info,
        roleId: strawberry.ID,
        permissionId: strawberry.ID
    ) -> bool:

        db = info.context["db"]

        # Buscar la relación entre el rol y el permiso
        assignment = db.query(models.RolePermission).filter(
            models.RolePermission.role_id == roleId,
            models.RolePermission.permission_id == permissionId
        ).first()

        if not assignment:
            raise Exception(
                "La asignación entre el rol y el permiso no existe"
            )

        if not assignment.is_active:
            raise Exception(
                "La asignación ya está desactivada"
            )

        # Desactivar sin eliminar el registro
        assignment.is_active = False

        db.commit()

        return True
    
    @strawberry.mutation
    def assignRole(
        self,
        info: strawberry.Info,
        companyUserId: strawberry.ID,
        roleId: strawberry.ID,
        actorCompanyUserId: strawberry.ID
    ) -> bool:
        db = info.context["db"]
        exigir_permiso(db, int(actorCompanyUserId), "roles.write")

        # 1. Comprobar que existe la membresía del usuario en la empresa.
        company_user = (
            db.query(models.CompanyUser)
            .filter(models.CompanyUser.id == companyUserId)
            .first()
        )

        if not company_user:
            raise Exception("La membresía del usuario no existe")

        if not company_user.is_active:
            raise Exception("La membresía del usuario está inactiva")

        # 2. Comprobar que existe el rol y que está activo.
        role = (
            db.query(models.Role)
            .filter(models.Role.id == roleId)
            .first()
        )

        if not role:
            raise Exception("El rol no existe")

        if not role.is_active:
            raise Exception("El rol está inactivo")

        try:
            # 3. Buscar la asignación de ese rol a esa membresía.
            assignment = (
                db.query(models.CompanyUserRole)
                .filter(
                    models.CompanyUserRole.company_user_id == company_user.id,
                    models.CompanyUserRole.role_id == role.id
                )
                .first()
            )

            # 4. Desactivar los demás roles activos de la membresía.
            active_assignments = (
                db.query(models.CompanyUserRole)
                .filter(
                    models.CompanyUserRole.company_user_id == company_user.id,
                    models.CompanyUserRole.is_active == True
                )
                .all()
            )

            for current_assignment in active_assignments:
                current_assignment.is_active = False

            # 5. Activar el rol solicitado o crear su asignación.
            if assignment:
                assignment.is_active = True
            else:
                assignment = models.CompanyUserRole(
                    company_user_id=company_user.id,
                    role_id=role.id,
                    is_active=True
                )
                db.add(assignment)

            # 6. Guardar todos los cambios.
            db.commit()

            return True

        except Exception:
            db.rollback()
            raise
    
    @strawberry.mutation
    def createCompanyAdmin(
        self,
        info: strawberry.Info,
        companyName: str,
        adminName: str,
        adminEmail: str,
        adminPassword: str
    ) -> bool:
        db = info.context["db"]

        try:
            # 1. Validar que el correo no esté registrado
            existing_user = db.query(models.User).filter(
                models.User.email == adminEmail
            ).first()

            if existing_user:
                raise Exception("El correo ya está registrado")

            # 2. Buscar el rol ADMINISTRADOR
            admin_role = db.query(models.Role).filter(
                models.Role.code == "ADMINISTRADOR",
                models.Role.is_active == True
            ).first()

            if not admin_role:
                raise Exception(
                    "No existe un rol ADMINISTRADOR activo"
                )

            # 3. Crear la empresa
            company = models.Company(
                name=companyName,
                is_active=True
            )
            db.add(company)
            db.flush()

            # 4. Crear el usuario administrador
            hashed_password = bcrypt.hashpw(
                adminPassword.encode("utf-8"),
                bcrypt.gensalt()
            ).decode("utf-8")

            user = models.User(
                name=adminName,
                email=adminEmail,
                hashed_password=hashed_password,
                is_active=True
            )
            db.add(user)
            db.flush()

            # 5. Vincular al usuario con la empresa
            membership = models.CompanyUser(
                company_id=company.id,
                user_id=user.id,
                is_admin=True,
                is_active=True
            )
            db.add(membership)
            db.flush()

            # 6. Asignar el rol a la membresía
            company_user_role = models.CompanyUserRole(
                company_user_id=membership.id,
                role_id=admin_role.id,
                is_active=True
            )
            db.add(company_user_role)

            # 7. Confirmar todos los cambios juntos
            db.commit()

            return True

        except Exception:
            db.rollback()
            raise






schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_app = GraphQLRouter(schema, context_getter=get_context)

app = FastAPI(title="Sistema Financiero API - Actividad 4")
app.include_router(graphql_app, prefix="/graphql")