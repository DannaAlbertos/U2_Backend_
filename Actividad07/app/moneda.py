"""Reglas monetarias de la Actividad 7 (Parte 3).

Todo el dinero se maneja con ``Decimal`` y dos posiciones decimales.
Nunca se convierte a ``float``: los float binarios no representan
exactamente valores como 0.10 o 0.20 (0.1 + 0.2 != 0.3).
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENTAVO = Decimal("0.01")
CERO = Decimal("0.00")

# Numeric(10, 2) en la tabla transactions admite hasta 99,999,999.99
MONTO_MAXIMO = Decimal("99999999.99")


def validar_monto(valor) -> Decimal:
    """Valida el monto de un movimiento capturado.

    Reglas: no float, numérico y finito, mayor que cero, máximo dos
    decimales y que quepa en Numeric(10, 2). Devuelve el monto con
    exactamente dos decimales (10 -> 10.00, 10.5 -> 10.50).

    Lanza ValueError con un mensaje claro si no cumple.
    """
    if isinstance(valor, float):
        raise ValueError("No se permiten valores float; envía el monto como texto.")
    try:
        monto = Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("El monto no es válido.")
    if not monto.is_finite():
        raise ValueError("El monto debe ser un número finito.")
    if monto <= CERO:
        raise ValueError("El monto del movimiento debe ser mayor que cero.")
    if monto != monto.quantize(CENTAVO):
        raise ValueError("El monto no puede tener más de dos decimales.")
    if monto > MONTO_MAXIMO:
        raise ValueError("El monto excede el máximo permitido (99999999.99).")
    return monto.quantize(CENTAVO)


def moneda(valor) -> Decimal:
    """Normaliza un importe (por ejemplo, leído de la BD) a dos decimales."""
    if valor is None:
        return CERO
    if isinstance(valor, float):
        raise ValueError("No se permiten valores float.")
    numero = Decimal(str(valor))
    if not numero.is_finite():
        raise ValueError("Importe monetario no válido.")
    resultado = numero.quantize(CENTAVO, rounding=ROUND_HALF_UP)
    # Evita el "-0.00" que Decimal conserva al redondear -0.001.
    return CERO if resultado == 0 else resultado


def formato_moneda(valor) -> str:
    """Representación textual exacta con dos decimales ('0.00', '50.50')."""
    return f"{moneda(valor):.2f}"


def esta_en_rojo(saldo_final) -> bool:
    """True si el SALDO FINAL es negativo.

    Se evalúa sobre el saldo final, nunca sobre el profit: una cuenta puede
    perder dinero en el periodo (profit < 0) y seguir con saldo positivo.
    """
    return moneda(saldo_final) < CERO
