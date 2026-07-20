"""Unit tests for the POSTTRAN (CBTRN02C) transaction-posting service."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from carddemo_batch.models import (
    Account,
    CardXref,
    DailyReject,
    DailyTransaction,
    TranCatBalance,
    Transaction,
)
from carddemo_batch.services import posting

FIXED_NOW = datetime(2022, 7, 18, 12, 0, 0, tzinfo=timezone.utc)
CARD = "4859452612877065"


def _account(session: Session, **overrides) -> Account:
    defaults = dict(
        id=101,
        active_status="Y",
        curr_bal=Decimal("0.00"),
        credit_limit=Decimal("5000.00"),
        cash_credit_limit=Decimal("1000.00"),
        open_date="2014-11-20",
        expiration_date="2030-01-01",
        reissue_date="2020-01-01",
        curr_cyc_credit=Decimal("0.00"),
        curr_cyc_debit=Decimal("0.00"),
        addr_zip="00000",
        group_id="GROUP01",
    )
    defaults.update(overrides)
    acct = Account(**defaults)
    session.add(acct)
    return acct


def _xref(session: Session, card: str = CARD, acct_id: int = 101) -> CardXref:
    xref = CardXref(card_num=card, cust_id=1, acct_id=acct_id)
    session.add(xref)
    return xref


def _daily(session: Session, **overrides) -> DailyTransaction:
    defaults = dict(
        id="TXN0000000000001",
        type_cd="01",
        cat_cd=1,
        source="POS TERM",
        description="Purchase",
        amount=Decimal("100.00"),
        merchant_id=800000000,
        merchant_name="Merchant",
        merchant_city="City",
        merchant_zip="00000",
        card_num=CARD,
        orig_ts="2022-06-10 19:27:53.000000",
        proc_ts="",
    )
    defaults.update(overrides)
    dt = DailyTransaction(**defaults)
    session.add(dt)
    return dt


def test_valid_transaction_posts_and_updates_credit(session: Session) -> None:
    _account(session)
    _xref(session)
    _daily(session, amount=Decimal("120.50"))
    session.commit()

    result = posting.run(session, now=FIXED_NOW)
    session.commit()

    assert (result.posted, result.rejected, result.return_code) == (1, 0, 0)
    acct = session.get(Account, 101)
    assert acct.curr_bal == Decimal("120.50")
    assert acct.curr_cyc_credit == Decimal("120.50")
    assert acct.curr_cyc_debit == Decimal("0.00")
    txn = session.get(Transaction, "TXN0000000000001")
    assert txn is not None
    assert txn.proc_ts == "2022-07-18-12.00.00.000000"


def test_negative_transaction_updates_debit(session: Session) -> None:
    _account(session)
    _xref(session)
    _daily(session, amount=Decimal("-75.25"))
    session.commit()

    posting.run(session, now=FIXED_NOW)
    session.commit()

    acct = session.get(Account, 101)
    assert acct.curr_bal == Decimal("-75.25")
    assert acct.curr_cyc_credit == Decimal("0.00")
    assert acct.curr_cyc_debit == Decimal("-75.25")


def test_tcatbal_created_then_incremented(session: Session) -> None:
    _account(session)
    _xref(session)
    _daily(session, id="TXN0000000000001", amount=Decimal("10.00"))
    _daily(session, id="TXN0000000000002", amount=Decimal("15.00"))
    session.commit()

    posting.run(session, now=FIXED_NOW)
    session.commit()

    tcb = session.get(TranCatBalance, (101, "01", 1))
    assert tcb is not None
    assert tcb.balance == Decimal("25.00")


def test_reject_invalid_card(session: Session) -> None:
    _account(session)
    # no xref for this card
    _daily(session, card_num="0000000000000000")
    session.commit()

    reason, desc = posting.validate(session, session.query(DailyTransaction).one())
    assert reason == 100
    assert desc == "INVALID CARD NUMBER FOUND"

    posting.run(session, now=FIXED_NOW)
    session.commit()
    rej = session.query(DailyReject).one()
    assert rej.reason_code == 100
    assert rej.raw_record.startswith("0100")


def test_reject_account_not_found(session: Session) -> None:
    _xref(session, acct_id=999)  # xref points at a missing account
    _daily(session)
    session.commit()

    reason, desc = posting.validate(session, session.query(DailyTransaction).one())
    assert reason == 101
    assert desc == "ACCOUNT RECORD NOT FOUND"


def test_reject_overlimit(session: Session) -> None:
    _account(session, credit_limit=Decimal("50.00"))
    _xref(session)
    _daily(session, amount=Decimal("100.00"))
    session.commit()

    reason, desc = posting.validate(session, session.query(DailyTransaction).one())
    assert reason == 102
    assert desc == "OVERLIMIT TRANSACTION"


def test_reject_expired_account(session: Session) -> None:
    _account(session, expiration_date="2020-01-01")
    _xref(session)
    _daily(session, orig_ts="2022-06-10 19:27:53.000000")
    session.commit()

    reason, desc = posting.validate(session, session.query(DailyTransaction).one())
    assert reason == 103
    assert desc == "TRANSACTION RECEIVED AFTER ACCT EXPIRATION"


def test_expiry_overrides_overlimit_reason(session: Session) -> None:
    # When both the credit-limit and expiry checks fail, the expiry reason wins (103),
    # matching the sequential MOVEs in CBTRN02C 1500-B-LOOKUP-ACCT.
    _account(session, credit_limit=Decimal("1.00"), expiration_date="2020-01-01")
    _xref(session)
    _daily(session, amount=Decimal("500.00"), orig_ts="2022-06-10 19:27:53.000000")
    session.commit()

    reason, _ = posting.validate(session, session.query(DailyTransaction).one())
    assert reason == 103


def test_credit_limit_boundary_is_inclusive(session: Session) -> None:
    # ACCT-CREDIT-LIMIT >= WS-TEMP-BAL passes at equality.
    _account(session, credit_limit=Decimal("100.00"))
    _xref(session)
    _daily(session, amount=Decimal("100.00"))
    session.commit()

    reason, _ = posting.validate(session, session.query(DailyTransaction).one())
    assert reason == 0
