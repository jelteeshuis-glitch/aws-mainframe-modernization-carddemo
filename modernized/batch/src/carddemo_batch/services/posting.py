"""POSTTRAN — transaction posting service (modern equivalent of CBTRN02C).

Reads the staged daily transactions in file order, validates each against the card
cross-reference and account master, then either posts it (updating the transaction
master, the transaction-category balance and the account balances) or writes a reject
record. See ``BUSINESS_RULES.md`` section 2 for the exact rules preserved here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account, CardXref, DailyReject, DailyTransaction, TranCatBalance, Transaction
from .common import (
    REJECT_ACCT_NOT_FOUND,
    REJECT_EXPIRED,
    REJECT_INVALID_CARD,
    REJECT_OVERLIMIT,
    db2_timestamp,
)


@dataclass
class PostingResult:
    processed: int = 0
    posted: int = 0
    rejected: int = 0

    @property
    def return_code(self) -> int:
        """CBTRN02C sets RETURN-CODE 4 when any transaction was rejected."""
        return 4 if self.rejected > 0 else 0


def validate(session: Session, dt: DailyTransaction) -> tuple[int, str]:
    """Return ``(reason_code, reason_desc)``; ``(0, "")`` means the transaction is valid.

    Mirrors ``1500-VALIDATE-TRAN``: the xref check short-circuits, and within the account
    check the expiry test runs after (and can override the reason of) the credit-limit
    test — exactly as the sequential COBOL MOVEs behave.
    """
    xref = session.get(CardXref, dt.card_num)
    if xref is None:
        return REJECT_INVALID_CARD

    acct = session.get(Account, xref.acct_id)
    if acct is None:
        return REJECT_ACCT_NOT_FOUND

    temp_bal = acct.curr_cyc_credit - acct.curr_cyc_debit + dt.amount
    reason = (0, "")
    if not (acct.credit_limit >= temp_bal):
        reason = REJECT_OVERLIMIT
    if not (acct.expiration_date >= dt.orig_ts[:10]):
        reason = REJECT_EXPIRED
    return reason


def _post_transaction(session: Session, dt: DailyTransaction, now: datetime | None) -> None:
    """Mirror ``2000-POST-TRANSACTION``."""
    xref = session.get(CardXref, dt.card_num)
    assert xref is not None  # guaranteed valid by validate()
    acct = session.get(Account, xref.acct_id)
    assert acct is not None

    txn = Transaction(
        id=dt.id,
        type_cd=dt.type_cd,
        cat_cd=dt.cat_cd,
        source=dt.source,
        description=dt.description,
        amount=dt.amount,
        merchant_id=dt.merchant_id,
        merchant_name=dt.merchant_name,
        merchant_city=dt.merchant_city,
        merchant_zip=dt.merchant_zip,
        card_num=dt.card_num,
        orig_ts=dt.orig_ts,
        proc_ts=db2_timestamp(now),
    )

    # 2700 — update / create the transaction-category balance.
    key = (xref.acct_id, dt.type_cd, dt.cat_cd)
    tcb = session.get(TranCatBalance, key)
    if tcb is None:
        session.add(
            TranCatBalance(
                acct_id=xref.acct_id,
                type_cd=dt.type_cd,
                cat_cd=dt.cat_cd,
                balance=dt.amount,
            )
        )
    else:
        tcb.balance = tcb.balance + dt.amount

    # 2800 — update account balances.
    acct.curr_bal = acct.curr_bal + dt.amount
    if dt.amount >= Decimal("0"):
        acct.curr_cyc_credit = acct.curr_cyc_credit + dt.amount
    else:
        acct.curr_cyc_debit = acct.curr_cyc_debit + dt.amount

    # 2900 — write the transaction master record.
    session.add(txn)


def _write_reject(session: Session, dt: DailyTransaction, reason: int, desc: str) -> None:
    """Mirror ``2500-WRITE-REJECT-REC`` — 80-byte trailer = reason(4) + desc(76)."""
    trailer = f"{reason:04d}{desc:<76}"
    session.add(
        DailyReject(
            tran_id=dt.id,
            reason_code=reason,
            reason_desc=desc,
            raw_record=trailer,
        )
    )


def run(session: Session, now: datetime | None = None) -> PostingResult:
    """Process every staged daily transaction. ``now`` fixes ``proc_ts`` for testing."""
    result = PostingResult()
    stmt = select(DailyTransaction).order_by(DailyTransaction.seq)
    for dt in session.scalars(stmt):
        result.processed += 1
        reason, desc = validate(session, dt)
        if reason == 0:
            _post_transaction(session, dt, now)
            result.posted += 1
        else:
            _write_reject(session, dt, reason, desc)
            result.rejected += 1
    session.flush()
    return result
