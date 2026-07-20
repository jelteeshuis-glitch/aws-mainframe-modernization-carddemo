"""Unit tests for the INTCALC (CBACT04C) interest-calculation service."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from carddemo_batch.models import (
    Account,
    CardXref,
    DisclosureGroup,
    SystemTransaction,
    TranCatBalance,
)
from carddemo_batch.services import interest

FIXED_NOW = datetime(2022, 7, 18, 12, 0, 0, tzinfo=timezone.utc)
CARD = "4859452612877065"


def _account(session: Session, group_id: str = "GROUP01", **overrides) -> Account:
    defaults = dict(
        id=101,
        curr_bal=Decimal("100.00"),
        credit_limit=Decimal("5000.00"),
        cash_credit_limit=Decimal("0.00"),
        curr_cyc_credit=Decimal("50.00"),
        curr_cyc_debit=Decimal("20.00"),
        group_id=group_id,
        expiration_date="2030-01-01",
    )
    defaults.update(overrides)
    acct = Account(**defaults)
    session.add(acct)
    session.add(CardXref(card_num=CARD, cust_id=1, acct_id=defaults["id"]))
    return acct


def _tcatbal(session: Session, balance: Decimal, type_cd="01", cat_cd=1, acct_id=101) -> None:
    session.add(
        TranCatBalance(acct_id=acct_id, type_cd=type_cd, cat_cd=cat_cd, balance=balance)
    )


def test_monthly_interest_formula_and_generated_transaction(session: Session) -> None:
    _account(session)
    _tcatbal(session, Decimal("1000.00"))
    session.add(DisclosureGroup(group_id="GROUP01", type_cd="01", cat_cd=1,
                                int_rate=Decimal("12.00")))
    session.commit()

    result = interest.run(session, parm_date="2022071800", now=FIXED_NOW)
    session.commit()

    # (1000 * 12) / 1200 = 10.00
    assert result.total_interest == Decimal("10.00")
    assert result.interest_transactions == 1

    sysx = session.query(SystemTransaction).one()
    assert sysx.id == "2022071800000001"
    assert sysx.type_cd == "01"
    assert sysx.cat_cd == 5
    assert sysx.source == "System"
    assert sysx.description == "Int. for a/c 101"
    assert sysx.amount == Decimal("10.00")
    assert sysx.card_num == CARD
    assert sysx.merchant_id == 0


def test_account_finalization_adds_interest_and_resets_cycles(session: Session) -> None:
    _account(session, curr_bal=Decimal("100.00"))
    _tcatbal(session, Decimal("1200.00"))
    session.add(DisclosureGroup(group_id="GROUP01", type_cd="01", cat_cd=1,
                                int_rate=Decimal("12.00")))
    session.commit()

    interest.run(session, now=FIXED_NOW)
    session.commit()

    acct = session.get(Account, 101)
    # 1200 * 12 / 1200 = 12.00 added to 100.00
    assert acct.curr_bal == Decimal("112.00")
    assert acct.curr_cyc_credit == Decimal("0.00")
    assert acct.curr_cyc_debit == Decimal("0.00")


def test_default_group_fallback(session: Session) -> None:
    _account(session, group_id="NOSUCH")
    _tcatbal(session, Decimal("1000.00"))
    # Only a DEFAULT rate exists for this (type, category).
    session.add(DisclosureGroup(group_id="DEFAULT", type_cd="01", cat_cd=1,
                                int_rate=Decimal("6.00")))
    session.commit()

    result = interest.run(session, now=FIXED_NOW)
    session.commit()

    # (1000 * 6) / 1200 = 5.00
    assert result.total_interest == Decimal("5.00")


def test_zero_rate_writes_no_transaction_but_resets_cycles(session: Session) -> None:
    _account(session, curr_bal=Decimal("100.00"))
    _tcatbal(session, Decimal("1000.00"))
    session.add(DisclosureGroup(group_id="GROUP01", type_cd="01", cat_cd=1,
                                int_rate=Decimal("0.00")))
    session.commit()

    result = interest.run(session, now=FIXED_NOW)
    session.commit()

    assert result.interest_transactions == 0
    acct = session.get(Account, 101)
    assert acct.curr_bal == Decimal("100.00")  # no interest added
    assert acct.curr_cyc_credit == Decimal("0.00")
    assert acct.curr_cyc_debit == Decimal("0.00")


def test_interest_truncates_to_cents(session: Session) -> None:
    _account(session)
    _tcatbal(session, Decimal("100.05"))
    session.add(DisclosureGroup(group_id="GROUP01", type_cd="01", cat_cd=1,
                                int_rate=Decimal("13.00")))
    session.commit()

    result = interest.run(session, now=FIXED_NOW)
    session.commit()

    # 100.05 * 13 / 1200 = 1.08387... -> truncated (not rounded) to 1.08
    assert result.total_interest == Decimal("1.08")
