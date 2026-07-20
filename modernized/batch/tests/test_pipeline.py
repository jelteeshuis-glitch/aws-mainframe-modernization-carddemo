"""Integration test: run the whole pipeline against the app/data sample fixtures.

Exercises LOAD -> POSTTRAN -> INTCALC -> COMBTRAN -> CREASTMT -> TRANREPT end to end and
asserts the aggregate behaviour matches the COBOL semantics (rejects, interest rollup,
combined master, statements per card).
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from carddemo_batch.loader import load_all
from carddemo_batch.models import (
    Account,
    DailyReject,
    DailyTransaction,
    Statement,
    SystemTransaction,
    Transaction,
)
from carddemo_batch.services import combine, interest, posting, report, statement

FIXED_NOW = datetime(2022, 7, 18, 12, 0, 0, tzinfo=timezone.utc)


def test_full_pipeline_against_sample_data(session: Session, data_dir) -> None:
    counts = load_all(session, data_dir)
    session.commit()
    assert counts["daily_transactions"] == 300
    assert counts["accounts"] == 50

    post = posting.run(session, now=FIXED_NOW)
    session.commit()
    # Every daily transaction is either posted or rejected.
    assert post.processed == 300
    assert post.posted + post.rejected == 300
    assert post.rejected > 0
    assert post.return_code == 4
    assert session.scalar(select(func.count()).select_from(Transaction)) == post.posted
    assert session.scalar(select(func.count()).select_from(DailyReject)) == post.rejected

    intr = interest.run(session, parm_date="2022071800", now=FIXED_NOW)
    session.commit()
    assert intr.interest_transactions > 0
    assert session.scalar(select(func.count()).select_from(SystemTransaction)) \
        == intr.interest_transactions

    comb = combine.run(session)
    session.commit()
    # Combined master = posted transactions + merged interest transactions.
    assert comb.merged == intr.interest_transactions
    assert comb.total == post.posted + intr.interest_transactions

    stmt = statement.run(session)
    session.commit()
    assert stmt.count > 0
    assert session.scalar(select(func.count()).select_from(Statement)) == stmt.count

    rep = report.run(session, "2022-07-18", "2022-07-18")
    session.commit()
    assert rep.lines > 0
    assert "Grand Total" in rep.body


def test_posting_conserves_amounts_on_account(session: Session, data_dir) -> None:
    """Sum of posted amounts per account equals the change in account current balance."""
    load_all(session, data_dir)
    session.commit()

    before = {a.id: a.curr_bal for a in session.scalars(select(Account))}
    posting.run(session, now=FIXED_NOW)
    session.commit()

    posted_by_acct: dict[int, Decimal] = {}
    for dt in session.scalars(select(DailyTransaction)):
        txn = session.get(Transaction, dt.id)
        if txn is None:
            continue
        # Resolve account via xref.
        from carddemo_batch.models import CardXref

        xref = session.get(CardXref, dt.card_num)
        assert xref is not None
        posted_by_acct[xref.acct_id] = posted_by_acct.get(xref.acct_id, Decimal("0")) + dt.amount

    for acct_id, delta in posted_by_acct.items():
        acct = session.get(Account, acct_id)
        assert acct.curr_bal == before[acct_id] + delta
