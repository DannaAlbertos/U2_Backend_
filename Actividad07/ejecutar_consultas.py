import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "sistema.db"
SQL_PATH = BASE_DIR / "consulta.sql"

if not DB_PATH.exists():
    raise FileNotFoundError(f"No se encontró la base de datos: {DB_PATH}")

if not SQL_PATH.exists():
    raise FileNotFoundError(f"No se encontró el archivo SQL: {SQL_PATH}")

conexion = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)

try:
    consultas = SQL_PATH.read_text(encoding="utf-8")
    cursor = conexion.cursor()

    for consulta in consultas.split(";"):
        consulta = consulta.strip()

        if not consulta:
            continue

        print(f"\n--- Consulta ---\n{consulta}")

        cursor.execute(consulta)

        if cursor.description:
            columnas = [columna[0] for columna in cursor.description]
            print(" | ".join(columnas))

            for fila in cursor.fetchall():
                print(" | ".join(str(valor) for valor in fila))
        else:
            print("Consulta ejecutada.")

finally:
    conexion.close()

import sqlite3

conn = sqlite3.connect("sistema.db")
print(conn.execute(
    "SELECT name FROM sqlite_master WHERE type = 'table'"
).fetchall())
conn.close()