import sqlite3

conn = sqlite3.connect("sistema.db")
cursor = conn.cursor()

query = """
SELECT rp.id, r.code, p.code, rp.is_active
FROM role_permissions rp
JOIN roles r ON r.id = rp.role_id
JOIN permissions p ON p.id = rp.permission_id
WHERE r.code = 'CAPTURISTA';
"""

print(f"{'ID':<5} | {'ROL':<15} | {'PERMISO':<25} | {'ACTIVA'}")
print("-" * 60)

for fila in cursor.execute(query):
    print(f"{fila[0]:<5} | {fila[1]:<15} | {fila[2]:<25} | {fila[3]}")
    



conn.close()