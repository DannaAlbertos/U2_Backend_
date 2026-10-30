import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "sistema.db"
SQL_PATH = BASE_DIR / "crear_concepto_expense.sql"

if not DB_PATH.exists():
    raise FileNotFoundError(f"No se encontró la base de datos: {DB_PATH}")

if not SQL_PATH.exists():
    raise FileNotFoundError(f"No se encontró el archivo SQL: {SQL_PATH}")

confirmacion = input(
    "Esto modificará la base de datos ejecutando crear_concepto_expense.sql. "
    "¿Continuar? Escribe SI para confirmar: "
)

if confirmacion != "SI":
    print("Operación cancelada.")
    raise SystemExit(0)

conexion = sqlite3.connect(DB_PATH)

try:
    conexion.executescript(
        "BEGIN;\n"
        + SQL_PATH.read_text(encoding="utf-8")
        + "\nCOMMIT;"
    )

    print("Script SQL ejecutado correctamente.")

except Exception:
    conexion.rollback()
    print("Error al ejecutar el script. Se revirtieron los cambios.")
    raise

finally:
    conexion.close()