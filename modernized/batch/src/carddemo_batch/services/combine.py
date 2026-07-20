"""COMBTRAN — combine transaction files (modern equivalent of the SORT/IDCAMS step).

The mainframe job concatenates the transaction-master backup with the system-generated
interest transactions (SYSTRAN), sorts them ascending by transaction id, and reloads the
combined result into the transaction master. Here the posted transactions already live
in the ``transaction`` table, so this step merges the ``system_transaction`` rows into
it. Ordering is intrinsic to the relational store (``ORDER BY id``). See
``BUSINESS_RULES.md`` section 4.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import SystemTransaction, Transaction


@dataclass
class CombineResult:
    merged: int = 0
    total: int = 0


def run(session: Session) -> CombineResult:
    """Merge system (interest) transactions into the transaction master."""
    result = CombineResult()
    existing_ids = set(session.scalars(select(Transaction.id)))
    for sysx in session.scalars(select(SystemTransaction).order_by(SystemTransaction.id)):
        if sysx.id in existing_ids:
            continue
        session.add(
            Transaction(
                id=sysx.id,
                type_cd=sysx.type_cd,
                cat_cd=sysx.cat_cd,
                source=sysx.source,
                description=sysx.description,
                amount=sysx.amount,
                merchant_id=sysx.merchant_id,
                merchant_name=sysx.merchant_name,
                merchant_city=sysx.merchant_city,
                merchant_zip=sysx.merchant_zip,
                card_num=sysx.card_num,
                orig_ts=sysx.orig_ts,
                proc_ts=sysx.proc_ts,
            )
        )
        existing_ids.add(sysx.id)
        result.merged += 1
    session.flush()
    result.total = session.scalar(select(func.count()).select_from(Transaction)) or 0
    return result
