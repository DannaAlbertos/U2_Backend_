import unittest
from unittest.mock import Mock

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app import models
from app.main import aplicar_permisos_rol


class TestRollbackE07(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.SessionTest = sessionmaker(bind=self.engine, autoflush=False)

        with self.SessionTest() as db:
            role = models.Role(code="CAPTURISTA", name="Capturista", is_active=True)
            permisos = [
                models.Permission(code="accounts.read", name="Leer cuentas", is_active=True),
                models.Permission(code="accounts.write", name="Escribir cuentas", is_active=True),
                models.Permission(code="concepts.read", name="Leer conceptos", is_active=True),
            ]
            db.add(role)
            db.add_all(permisos)
            db.flush()
            self.rol_id = role.id
            self.permisos_ids = {p.code: p.id for p in permisos}
            for code in ("accounts.read", "concepts.read"):
                db.add(models.RolePermission(
                    role_id=role.id,
                    permission_id=self.permisos_ids[code], is_active=True
                ))
            db.commit()

    def consultar_estado(self):
        with self.SessionTest() as db:
            return sorted(
                (rel.permission.code, rel.is_active)
                for rel in db.query(models.RolePermission).filter_by(role_id=self.rol_id).all()
            )

    def test_e07_rollback_despues_de_flush(self):
        antes = self.consultar_estado()
        db = self.SessionTest()
        try:
            with self.assertRaisesRegex(RuntimeError, "Fallo controlado E07"):
                aplicar_permisos_rol(
                    db,
                    self.rol_id,
                    [self.permisos_ids["accounts.write"]],
                    antes_commit=Mock(side_effect=RuntimeError("Fallo controlado E07")),
                )
        finally:
            db.close()
        despues = self.consultar_estado()
        self.assertEqual(antes, despues)
        self.assertEqual(len(despues), 2)


if __name__ == "__main__":
    unittest.main()
