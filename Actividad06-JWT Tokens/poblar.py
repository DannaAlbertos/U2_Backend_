import sqlite3
import bcrypt
from datetime import datetime

conn = sqlite3.connect("sistema.db")
cursor = conn.cursor()

# Hash estándar para la contraseña "secreto"
pwd_hash = bcrypt.hashpw(b"secreto", bcrypt.gensalt()).decode("utf-8")
ahora = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

# 1. Limpieza preventiva en orden inverso de claves foráneas
tablas = [
    "transactions", "account_concepts", "accounts", "concepts",
    "company_user_roles", "role_permissions", "company_users",
    "users", "roles", "permissions", "companies"
]
for t in tablas:
    try:
        cursor.execute(f"DELETE FROM {t}")
    except sqlite3.OperationalError:
        pass

# 2. Empresas
cursor.executemany(
    "INSERT INTO companies (id, name, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
    [
        (1, "Empresa Principal", 1, ahora, ahora),
        (2, "Empresa Secundaria", 1, ahora, ahora)
    ]
)

# 3. Permisos
permisos = [
    (1, "company.users.write", "Administrar usuarios", "company.users.write", 1),
    (2, "accounts.read", "Consultar cuentas", "accounts.read", 1),
    (3, "accounts.write", "Crear y editar cuentas", "accounts.write", 1),
    (4, "concepts.read", "Consultar conceptos", "concepts.read", 1),
    (5, "concepts.write", "Crear conceptos", "concepts.write", 1),
    (6, "transactions.read", "Consultar transacciones", "transactions.read", 1),
    (7, "transactions.write", "Crear transacciones", "transactions.write", 1),
    (8, "roles.read", "Consultar roles", "roles.read", 1),
    (9, "roles.write", "Asignar roles y permisos", "roles.write", 1)
]
cursor.executemany(
    "INSERT INTO permissions (id, code, description, name, is_active) VALUES (?, ?, ?, ?, ?)",
    permisos
)

# 4. Roles
roles = [
    (1, "ADMIN", "ADMIN", "Rol Administrador", 1),
    (2, "CAPTURISTA", "CAPTURISTA", "Rol Capturista", 1),
    (3, "CONTADOR", "CONTADOR", "Rol Contador", 1),
    (4, "CONSULTA", "CONSULTA", "Rol Consulta", 1)
]
cursor.executemany(
    "INSERT INTO roles (id, code, name, description, is_active) VALUES (?, ?, ?, ?, ?)",
    roles
)

# 5. RolePermissions (id explícito único para cada relación)
rp_data = [
    # ADMIN (1 al 9)
    (1, 1, 1, 1, ahora), (2, 1, 2, 1, ahora), (3, 1, 3, 1, ahora),
    (4, 1, 4, 1, ahora), (5, 1, 5, 1, ahora), (6, 1, 6, 1, ahora),
    (7, 1, 7, 1, ahora), (8, 1, 8, 1, ahora), (9, 1, 9, 1, ahora),
    # CAPTURISTA: concepts.read (4), transactions.read (6), transactions.write (7)
    (10, 2, 4, 1, ahora), (11, 2, 6, 1, ahora), (12, 2, 7, 1, ahora),
    # CONTADOR: accounts.read (2), accounts.write (3), concepts.read (4), concepts.write (5), transactions.read (6)
    (13, 3, 2, 1, ahora), (14, 3, 3, 1, ahora), (15, 3, 4, 1, ahora),
    (16, 3, 5, 1, ahora), (17, 3, 6, 1, ahora),
    # CONSULTA: accounts.read (2), concepts.read (4), transactions.read (6)
    (18, 4, 2, 1, ahora), (19, 4, 4, 1, ahora), (20, 4, 6, 1, ahora)
]
cursor.executemany(
    "INSERT INTO role_permissions (id, role_id, permission_id, is_active, created_at) VALUES (?, ?, ?, ?, ?)",
    rp_data
)

# 6. Usuarios
usuarios = [
    (1, "Ana", "ana@empresa.test", pwd_hash, 1, ahora, ahora),
    (2, "Maria", "maria@empresa.test", pwd_hash, 1, ahora, ahora),
    (3, "Luis", "luis@empresa.test", pwd_hash, 1, ahora, ahora),
    (4, "Pedro", "pedro@empresa.test", pwd_hash, 1, ahora, ahora),
    (5, "Externo", "externo@otraempresa.test", pwd_hash, 1, ahora, ahora)
]
cursor.executemany(
    "INSERT INTO users (id, name, email, hashed_password, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
    usuarios
)

# 7. Membresías (CompanyUser)
membresias = [
    (1, 1, 1, 1, 1, ahora), # Ana (Admin en Empresa 1)
    (2, 1, 2, 0, 1, ahora), # Maria en Empresa 1
    (3, 1, 3, 0, 1, ahora), # Luis en Empresa 1
    (4, 1, 4, 0, 1, ahora), # Pedro en Empresa 1
    (5, 2, 5, 0, 1, ahora)  # Externo en Empresa 2
]
cursor.executemany(
    "INSERT INTO company_users (id, company_id, user_id, is_admin, is_active, joined_at) VALUES (?, ?, ?, ?, ?, ?)",
    membresias
)

# 8. Asignación inicial de Roles (CompanyUserRole)
cur_data = [
    (1, 1, 1, 1, ahora), # Ana -> ADMIN
    (2, 2, 2, 1, ahora), # Maria -> CAPTURISTA
    (3, 3, 3, 1, ahora), # Luis -> CONTADOR
    (4, 4, 4, 1, ahora)  # Pedro -> CONSULTA
]
cursor.executemany(
    "INSERT INTO company_user_roles (id, company_user_id, role_id, is_active, created_at) VALUES (?, ?, ?, ?, ?)",
    cur_data
)

# 9. Cuenta base
cursor.execute(
    """INSERT INTO accounts 
       (id, company_id, account_type, name, is_active, created_at, updated_at) 
       VALUES (?, ?, ?, ?, ?, ?, ?)""",
    (1, 1, "DEBIT", "Cuenta Operativa Base", 1, ahora, ahora)
)

# 10. Concepto base
cursor.execute(
    """INSERT INTO concepts 
       (id, company_id, concept_type, name, is_active, created_at, updated_at) 
       VALUES (?, ?, ?, ?, ?, ?, ?)""",
    (1, 1, "INCOME", "Venta General", 1, ahora, ahora)
)

# 11. Vinculación Cuenta-Concepto
cursor.execute(
    """INSERT INTO account_concepts 
       (id, account_id, concept_id, is_active, created_at) 
       VALUES (?, ?, ?, ?, ?)""",
    (1, 1, 1, 1, ahora)
)

conn.commit()
conn.close()
print("¡Base de datos sistema.db poblada exitosamente sin ningún error!")