"""Inserta los cuatro movimientos frontera de B04 en una cuenta de prueba aislada.

Uso desde la carpeta de Actividad 7:
  python preparar_b04.py --account-id 1 --concept-id 1 --captured-by 1

Selecciona un concepto INCOME permitido para la cuenta y no uses la cuenta
Banco de referencia si necesitas conservar intactos los resultados B01/B02.
"""
import argparse
from decimal import Decimal
from datetime import datetime, timezone

from app.database import SessionLocal
from app import models

def utc_naive(texto):
    valor = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    if valor.tzinfo is None:
        raise ValueError("La fecha debe incluir zona horaria UTC (Z).")
    return valor.astimezone(timezone.utc).replace(tzinfo=None)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-id", type=int, required=True)
    parser.add_argument("--concept-id", type=int, required=True)
    parser.add_argument("--captured-by", type=int, required=True)
    args = parser.parse_args()

    fronteras = [
        ("2026-10-25T23:59:59Z", "B04 antes del inicio"),
        ("2026-10-26T00:00:00Z", "B04 inicio incluido"),
        ("2026-10-30T23:59:59Z", "B04 fin del día incluido"),
        ("2026-10-31T00:00:00Z", "B04 medianoche excluida"),
    ]
    db = SessionLocal()
    try:
        cuenta = db.query(models.Account).filter_by(id=args.account_id).first()
        concepto = db.query(models.Concept).filter_by(id=args.concept_id).first()
        usuario = db.query(models.User).filter_by(id=args.captured_by).first()
        if not cuenta or not concepto or not usuario:
            raise SystemExit("No se encontró la cuenta, concepto o usuario indicado.")
        if cuenta.company_id != concepto.company_id:
            raise SystemExit("La cuenta y el concepto deben pertenecer a la misma empresa.")
        if concepto.concept_type.value != "INCOME":
            raise SystemExit("Para este script, el concepto debe ser de tipo INCOME.")
        relacion = db.query(models.AccountConcept).filter_by(
            account_id=cuenta.id, concept_id=concepto.id, is_active=True
        ).first()
        if not relacion:
            raise SystemExit("El concepto debe estar asignado y activo para la cuenta.")
        ahora = datetime.now(timezone.utc).replace(tzinfo=None)
        for fecha, descripcion in fronteras:
            db.add(models.Transaction(
                account_id=cuenta.id,
                concept_id=concepto.id,
                transaction_type=models.TransactionTypeEnum.INCOME,
                amount=Decimal("10.00"),
                transaction_date=utc_naive(fecha),
                captured_at=ahora,
                captured_by=usuario.id,
                short_description=descripcion,
                is_active=True,
            ))
        db.commit()
        print("B04: se insertaron 4 movimientos frontera.")
        for fecha, descripcion in fronteras:
            print(f"  {fecha} | 10.00 | {descripcion}")
        print("Usa una cuenta de prueba aislada; no ejecutes el script dos veces sobre la misma cuenta.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
