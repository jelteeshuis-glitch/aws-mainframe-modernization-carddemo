"""TRANREPT — transaction detail report (modern equivalent of CBTRN03C).

Reads the transaction master filtered by processing-date range and sorted by card
number, resolves type / category descriptions, and emits a paginated report with page
totals (every 20 lines), per-account totals (on card change) and a grand total. See
``BUSINESS_RULES.md`` section 6.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    Transaction,
    TransactionCategoryType,
    TransactionReport,
    TransactionType,
)

_PAGE_SIZE = 20
_WIDTH = 133


@dataclass
class ReportResult:
    body: str = ""
    lines: int = 0
    grand_total: Decimal = Decimal("0")


def _money(value: Decimal) -> str:
    return f"{value:>15,.2f}"


def _header(start: str, end: str) -> list[str]:
    return [
        f"CardDemo Transaction Detail Report  ({start} to {end})".center(_WIDTH).rstrip(),
        "",
        f"{'Tran ID':<18}{'Card Number':<18}{'Type':<26}{'Category':<28}"
        f"{'Source':<12}{'Amount':>15}",
        "-" * _WIDTH,
    ]


def run(session: Session, start_date: str, end_date: str) -> ReportResult:
    """Render the transaction report for the ``[start_date, end_date]`` proc-date range."""
    type_desc = {t.type_cd: t.description.strip() for t in session.scalars(select(TransactionType))}
    cat_desc = {
        (c.type_cd, c.cat_cd): c.description.strip()
        for c in session.scalars(select(TransactionCategoryType))
    }

    stmt = (
        select(Transaction)
        .where(Transaction.proc_ts.isnot(None))
        .order_by(Transaction.card_num, Transaction.id)
    )

    out: list[str] = []
    page_total = Decimal("0")
    account_total = Decimal("0")
    grand_total = Decimal("0")
    line_counter = 0
    curr_card = None
    first = True

    def write_headers() -> None:
        nonlocal line_counter
        out.extend(_header(start_date, end_date))
        line_counter += len(_header(start_date, end_date))

    def flush_page_total() -> None:
        nonlocal page_total, grand_total, line_counter
        out.append(f"{'Page Total:':<102}{_money(page_total)}")
        grand_total += page_total
        page_total = Decimal("0")
        line_counter += 1

    def flush_account_total() -> None:
        nonlocal account_total, line_counter
        out.append(f"{'Account Total:':<102}{_money(account_total)}")
        account_total = Decimal("0")
        line_counter += 1

    for txn in session.scalars(stmt):
        proc_day = (txn.proc_ts or "")[:10]
        if not (start_date <= proc_day <= end_date):
            continue

        if curr_card != txn.card_num:
            if not first:
                flush_account_total()
            curr_card = txn.card_num

        if first:
            first = False
            write_headers()
        elif line_counter % _PAGE_SIZE == 0:
            flush_page_total()
            write_headers()

        page_total += txn.amount
        account_total += txn.amount
        cat = cat_desc.get((txn.type_cd, txn.cat_cd), "")
        out.append(
            f"{txn.id:<18}{txn.card_num:<18}{type_desc.get(txn.type_cd, ''):<26}"
            f"{cat:<28}{txn.source.strip():<12}{_money(txn.amount)}"
        )
        line_counter += 1

    if not first:
        flush_account_total()
        flush_page_total()
        out.append(f"{'Grand Total:':<102}{_money(grand_total)}")

    body = "\n".join(out) + ("\n" if out else "")
    session.add(TransactionReport(start_date=start_date, end_date=end_date, body=body))
    session.flush()
    return ReportResult(body=body, lines=len(out), grand_total=grand_total)
