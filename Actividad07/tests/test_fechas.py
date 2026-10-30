import unittest
from datetime import date, datetime, timezone, timedelta
from app.fechas import normalizar_datetime_utc, limites_periodo_utc

class TestFechasActividad7(unittest.TestCase):
    def test_normaliza_offset_a_utc_naive(self):
        entrada = datetime.fromisoformat("2026-10-27T14:00:00+02:00")
        resultado = normalizar_datetime_utc(entrada)
        self.assertEqual(resultado, datetime(2026, 10, 27, 12, 0, 0))
        self.assertIsNone(resultado.tzinfo)

    def test_rechaza_datetime_sin_zona(self):
        with self.assertRaisesRegex(ValueError, "zona horaria"):
            normalizar_datetime_utc(datetime(2026, 10, 27, 12, 0, 0))

    def test_rango_incluye_dia_final_completo(self):
        inicio, fin = limites_periodo_utc(date(2026, 10, 26), date(2026, 10, 30))
        self.assertEqual(inicio, datetime(2026, 10, 26, 0, 0, 0))
        self.assertEqual(fin, datetime(2026, 10, 31, 0, 0, 0))

    def test_rechaza_rango_invertido(self):
        with self.assertRaisesRegex(ValueError, "fromDate no puede ser posterior"):
            limites_periodo_utc(date(2026, 10, 31), date(2026, 10, 26))

if __name__ == "__main__":
    unittest.main()
    