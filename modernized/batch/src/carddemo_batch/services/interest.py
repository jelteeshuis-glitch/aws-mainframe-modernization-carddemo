"""INTCALC — interest calculation service (modern equivalent of CBACT04C).

Walks the transaction-category balances in key order, computes monthly interest per
category using the disclosure-group rate (falling back to the ``DEFAULT`` group), writes
a system-generated interest transaction per category, and rolls the accrued interest
into each account balance while resetting the cycle counters. See ``BUSINESS_RULES.md``
section 3.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_DOWN, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account, CardXref, DisclosureGroup, SystemTransaction, TranCatBalance
from .common import db2_timestamp

_CENTS = Decimal("0.01")


@dataclass
class InterestResult:
    accounts_updated: int = 0
    interest_transactions: int = 0
    total_interest: Decimal = Decimal("0")


def _lookup_rate(session: Session, group_id: str, type_cd: str, cat_cd: int) -> Decimal:
    """Interest rate for (group, type, category); fall back to the ``DEFAULT`` group.

    Mirrors ``1200-GET-INTEREST-RATE`` + ``1200-A-GET-DEFAULT-INT-RATE``. A missing
    default group yields a rate of 0 (no interest), matching a status-23 read.
    """
    row = session.get(DisclosureGroup, (group_id, type_cd, cat_cd))
    if row is None:
        row = session.get(DisclosureGroup, ("DEFAULT", type_cd, cat_cd))
    return row.int_rate if row is not None else Decimal("0")


def _monthly_interest(balance: Decimal, rate: Decimal) -> Decimal:
    """``(balance * rate) / 1200`` truncated to cents (COBOL COMPUTE without ROUNDED)."""
    return (balance * rate / Decimal("1200")).quantize(_CENTS, rounding=ROUND_DOWN)


def run(
    session: Session,
    parm_date: str = "2022071800",
    now: datetime | None = None,
) -> InterestResult:
    """Compute interest across all category balances. ``now``/``parm_date`` aid testing."""
    result = InterestResult()
    suffix = 0

    current_acct: Account | None = None
    current_xref: CardXref | None = None
    total_int = Decimal("0")

    def finalize_account() -> None:
        # 1050-UPDATE-ACCOUNT for the account we just finished.
        nonlocal total_int
        if current_acct is not None:
            current_acct.curr_bal = current_acct.curr_bal + total_int
            current_acct.curr_cyc_credit = Decimal("0")
            current_acct.curr_cyc_debit = Decimal("0")
            result.accounts_updated += 1
        total_int = Decimal("0")

    stmt = select(TranCatBalance).order_by(
        TranCatBalance.acct_id, TranCatBalance.type_cd, TranCatBalance.cat_cd
    )
    for tcb in session.scalars(stmt):
        if current_acct is None or tcb.acct_id != current_acct.id:
            finalize_account()
            current_acct = session.get(Account, tcb.acct_id)
            current_xref = session.scalar(
                select(CardXref).where(CardXref.acct_id == tcb.acct_id)
            )
            if current_acct is None:
                # ACCOUNT NOT FOUND — the COBOL only DISPLAYs and continues; skip.
                continue

        rate = _lookup_rate(session, current_acct.group_id.strip(), tcb.type_cd, tcb.cat_cd)
        if rate == 0:
            continue

        monthly = _monthly_interest(tcb.balance, rate)
        total_int += monthly
        result.total_interest += monthly

        suffix += 1
        card_num = current_xref.card_num if current_xref is not None else ""
        ts = db2_timestamp(now)
        session.add(
            SystemTransaction(
                id=f"{parm_date}{suffix:06d}",
                type_cd="01",
                cat_cd=5,
                source="System",
                description=f"Int. for a/c {current_acct.id}",
                amount=monthly,
                merchant_id=0,
                merchant_name="",
                merchant_city="",
                merchant_zip="",
                card_num=card_num,
                orig_ts=ts,
                proc_ts=ts,
            )
        )
        result.interest_transactions += 1

    finalize_account()
    session.flush()
    return result
