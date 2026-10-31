"""Pruebas unitarias del módulo monetario (Parte 3). No usan base de datos."""
from decimal import Decimal

import pytest

from app.moneda import esta_en_rojo, formato_moneda, moneda, validar_monto


def test_precision_decimal():
    # Con float, 0.1 + 0.2 - 0.3 != 0. Con Decimal es exactamente cero.
    ingreso = Decimal("0.10") + Decimal("0.20")
    egreso = Decimal("0.30")
    assert ingreso - egreso == Decimal("0.00")


def test_rechazar_decimales_extras():
    with pytest.raises(ValueError, match="dos decimales"):
        validar_monto("10.123")
    with pytest.raises(ValueError):
        validar_monto(Decimal("0.001"))


@pytest.mark.parametrize("entrada,esperado", [
    ("10", "10.00"), ("10.5", "10.50"), ("10.50", "10.50"), (Decimal("0.10"), "0.10"),
])
def test_aceptar_hasta_dos_decimales(entrada, esperado):
    assert validar_monto(entrada) == Decimal(esperado)
    assert str(validar_monto(entrada)) == esperado


@pytest.mark.parametrize("entrada", ["0", "0.00", "-5.00", "abc", "", "NaN", "Infinity", None])
def test_rechazar_montos_invalidos(entrada):
    with pytest.raises(ValueError):
        validar_monto(entrada)


def test_rechazar_float_y_monto_excesivo():
    with pytest.raises(ValueError, match="float"):
        validar_monto(0.1)
    with pytest.raises(ValueError, match="máximo"):
        validar_monto("100000000.00")


def test_formato_monetario():
    assert formato_moneda("0") == "0.00"
    assert formato_moneda("50.5") == "50.50"
    assert formato_moneda(None) == "0.00"
    assert formato_moneda("-0.001") == "0.00"  # sin "-0.00"


def test_moneda_no_acepta_float():
    with pytest.raises(ValueError):
        moneda(1.5)


def test_saldo_negativo():
    assert esta_en_rojo(Decimal("-50.00")) is True
    assert esta_en_rojo(Decimal("0.00")) is False
    assert esta_en_rojo(Decimal("1600.00")) is False
