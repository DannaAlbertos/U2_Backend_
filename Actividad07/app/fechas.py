"""Funciones de fecha para Actividad 7. La BD conserva datetime naive en UTC."""
from datetime import date, datetime, time, timedelta, timezone

def normalizar_datetime_utc(valor: datetime) -> datetime:
    """Valida una fecha con zona y devuelve UTC naive para persistencia.

    La columna SQLAlchemy DateTime existente no declara timezone=True; por eso
    se guarda el instante UTC sin tzinfo y se documenta esa convención.
    """
    if not isinstance(valor, datetime):
        raise ValueError("transactionDate debe ser una fecha y hora válida.")
    if valor.tzinfo is None or valor.utcoffset() is None:
        raise ValueError(
            "transactionDate debe incluir zona horaria, por ejemplo 2026-10-27T12:00:00Z."
        )
    return valor.astimezone(timezone.utc).replace(tzinfo=None)

def ahora_utc_naive() -> datetime:
    """Instante actual del servidor en UTC, en formato naive para la BD."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

def fecha_utc_para_respuesta(valor: datetime) -> datetime:
    """Interpreta filas naive existentes como UTC y devuelve datetime aware UTC."""
    if valor.tzinfo is None or valor.utcoffset() is None:
        return valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(timezone.utc)

def limites_periodo_utc(from_date: date, to_date: date) -> tuple[datetime, datetime]:
    """Devuelve [inicio, fin_exclusivo): días completos UTC, incluido to_date."""
    if not isinstance(from_date, date) or isinstance(from_date, datetime):
        raise ValueError("fromDate debe ser una fecha válida en formato YYYY-MM-DD.")
    if not isinstance(to_date, date) or isinstance(to_date, datetime):
        raise ValueError("toDate debe ser una fecha válida en formato YYYY-MM-DD.")
    if from_date > to_date:
        raise ValueError("fromDate no puede ser posterior a toDate.")
    inicio = datetime.combine(from_date, time.min)
    fin_exclusivo = datetime.combine(to_date + timedelta(days=1), time.min)
    return inicio, fin_exclusivo
