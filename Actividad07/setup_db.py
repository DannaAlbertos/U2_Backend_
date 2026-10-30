import sqlite3

conn = sqlite3.connect("sistema.db")
cursor = conn.cursor()
cursor.execute(
    'INSERT OR IGNORE INTO companies (id, name) VALUES (1, "Empresa");'
)
conn.commit()
conn.close()
print("¡Empresa creada con éxito!")