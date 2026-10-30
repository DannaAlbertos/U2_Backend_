from datetime import date
from decimal import Decimal

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from . import models
from .fechas import limites_periodo_utc

DOS = Decimal("0.01")
INCOME = models.TransactionTypeEnum.INCOME
EXPENSE = models.TransactionTypeEnum.EXPENSE


def _dec(valor) -> Decimal:
    return Decimal(str(valor or 0)).quantize(DOS)


def calcular_balances_por_cuenta(
    db: Session,
    company_id: int,
    from_date: date,
    to_date: date,
    account_id: int | None = None,
) -> list[dict]:
    """Balance por cuenta en [from_date, to_date], ambos días incluidos.

    - openingBalance: saldo histórico (movimientos anteriores a from_date)
    - income / expense / profit: movimientos dentro del rango
    - closingBalance: openingBalance + profit
    """
    inicio, fin = limites_periodo_utc(from_date, to_date)
    T, A = models.Transaction, models.Account

    antes = T.transaction_date < inicio
    periodo = and_(T.transaction_date >= inicio, T.transaction_date < fin)

    def suma(tipo, condicion):
        return func.coalesce(
            func.sum(
                case((and_(T.transaction_type == tipo, condicion), T.amount), else_=0)
            ),
            0,
        )

    stmt = (
        select(
            A.id,
            A.name,
            A.is_active,
            (suma(INCOME, antes) - suma(EXPENSE, antes)).label("opening"),
            suma(INCOME, periodo).label("income"),
            suma(EXPENSE, periodo).label("expense"),
        )
        .select_from(A)
        # LEFT JOIN: las condiciones van en el ON (no en el WHERE) para que
        # las cuentas sin movimientos sigan apareciendo, en cero.
        .outerjoin(
            T,
            and_(
                T.account_id == A.id,
                T.is_active.is_(True),
                T.transaction_date < fin,
            ),
        )
        .where(A.company_id == company_id)
        .group_by(A.id, A.name, A.is_active)
        .order_by(A.id)
    )
    if account_id is not None:
        stmt = stmt.where(A.id == account_id)

    resultado = []
    for fila in db.execute(stmt).all():
        opening = _dec(fila.opening)
        income = _dec(fila.income)
        expense = _dec(fila.expense)
        profit = income - expense
        resultado.append(
            {
                "accountId": fila.id,
                "accountName": fila.name,
                "isActive": fila.is_active,
                "openingBalance": opening,
                "income": income,
                "expense": expense,
                "profit": profit,
                "closingBalance": opening + profit,
            }
        )
    return resultado


def calcular_balance_general(
    db: Session, company_id: int, from_date: date, to_date: date
) -> dict:
    """Totales de la empresa. Sin cuentas (caso B03) devuelve todo en 0.00."""
    cuentas = calcular_balances_por_cuenta(db, company_id, from_date, to_date)
    cero = Decimal("0.00")
    return {
        "companyId": company_id,
        "openingBalance": sum((c["openingBalance"] for c in cuentas), cero),
        "income": sum((c["income"] for c in cuentas), cero),
        "expense": sum((c["expense"] for c in cuentas), cero),
        "profit": sum((c["profit"] for c in cuentas), cero),
        "closingBalance": sum((c["closingBalance"] for c in cuentas), cero),
        "accounts": cuentas,
    }