"""CREASTMT — statement generation service (modern equivalent of CBSTM03A).

For each card in the cross-reference, joins customer + account + that card's
transactions and renders a per-account statement in both plain text and HTML. Unlike
the COBOL version there is no fixed 51-card / 10-transaction in-memory limit; grouping
is done with a database query. HTML content is escaped for safety while keeping the
original layout. See ``BUSINESS_RULES.md`` section 5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from html import escape

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account, CardXref, Customer, Statement, Transaction

_WIDTH = 80
_RULE = "-" * _WIDTH


@dataclass
class RenderedStatement:
    acct_id: int
    card_num: str
    text_body: str
    html_body: str


@dataclass
class StatementResult:
    statements: list[RenderedStatement] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.statements)


def _full_name(cust: Customer | None) -> str:
    if cust is None:
        return ""
    parts = [cust.first_name.strip(), cust.middle_name.strip(), cust.last_name.strip()]
    return " ".join(p for p in parts if p)


def _address_line_3(cust: Customer | None) -> str:
    if cust is None:
        return ""
    parts = [
        cust.addr_line_3.strip(),
        cust.addr_state_cd.strip(),
        cust.addr_country_cd.strip(),
        cust.addr_zip.strip(),
    ]
    return " ".join(p for p in parts if p)


def _money(value: Decimal) -> str:
    return f"{value:,.2f}"


def _build_text(cust: Customer | None, acct: Account, txns: list[Transaction]) -> str:
    lines = [
        _RULE,
        "START OF STATEMENT".center(_WIDTH),
        _RULE,
        _full_name(cust),
    ]
    if cust is not None:
        lines += [cust.addr_line_1.strip(), cust.addr_line_2.strip(), _address_line_3(cust)]
    lines += [
        _RULE,
        f"Account ID      : {acct.id}",
        f"Current Balance : {_money(acct.curr_bal)}",
        f"FICO Score      : {cust.fico_credit_score if cust else 0}",
        _RULE,
        "TRANSACTIONS",
        _RULE,
        f"{'Tran ID':<18}{'Tran Details':<44}{'Amount':>18}",
        _RULE,
    ]
    total = Decimal("0")
    for txn in txns:
        total += txn.amount
        lines.append(f"{txn.id:<18}{txn.description.strip()[:44]:<44}{_money(txn.amount):>18}")
    lines += [
        _RULE,
        f"{'Total EXP:':<62}{_money(total):>18}",
        _RULE,
        "END OF STATEMENT".center(_WIDTH),
        _RULE,
    ]
    return "\n".join(lines) + "\n"


def _build_html(cust: Customer | None, acct: Account, txns: list[Transaction]) -> str:
    rows = []
    total = Decimal("0")
    for txn in txns:
        total += txn.amount
        rows.append(
            "<tr>"
            f"<td>{escape(txn.id)}</td>"
            f"<td>{escape(txn.description.strip())}</td>"
            f"<td class='amt'>{escape(_money(txn.amount))}</td>"
            "</tr>"
        )
    address = "<br>".join(
        escape(p)
        for p in (
            cust.addr_line_1.strip() if cust else "",
            cust.addr_line_2.strip() if cust else "",
            _address_line_3(cust),
        )
        if p
    )
    return (
        "<!DOCTYPE html>\n<html><head><meta charset='utf-8'>"
        "<style>body{font-family:Arial,sans-serif}"
        "table{border-collapse:collapse;width:100%}"
        "th,td{border:1px solid #ccc;padding:4px 8px;text-align:left}"
        ".amt{text-align:right}</style></head><body>\n"
        "<h1>Bank of XYZ</h1>\n"
        f"<h2>{escape(_full_name(cust))}</h2>\n"
        f"<p>{address}</p>\n"
        "<table><tbody>"
        f"<tr><th>Account ID</th><td>{escape(str(acct.id))}</td></tr>"
        f"<tr><th>Current Balance</th><td class='amt'>{escape(_money(acct.curr_bal))}</td></tr>"
        f"<tr><th>FICO Score</th><td>{escape(str(cust.fico_credit_score if cust else 0))}</td></tr>"
        "</tbody></table>\n"
        "<h3>Transactions</h3>\n"
        "<table><thead><tr><th>Tran ID</th><th>Tran Details</th><th class='amt'>Amount</th>"
        "</tr></thead><tbody>\n"
        + "\n".join(rows)
        + f"\n<tr><th colspan='2'>Total EXP</th><td class='amt'>{escape(_money(total))}</td></tr>"
        "</tbody></table>\n"
        "<p>End of Statement</p>\n</body></html>\n"
    )


def run(session: Session) -> StatementResult:
    """Render and persist a statement per card/account."""
    result = StatementResult()
    xrefs = session.scalars(select(CardXref).order_by(CardXref.card_num))
    for xref in xrefs:
        acct = session.get(Account, xref.acct_id)
        if acct is None:
            continue
        cust = session.get(Customer, xref.cust_id)
        txns = list(
            session.scalars(
                select(Transaction)
                .where(Transaction.card_num == xref.card_num)
                .order_by(Transaction.id)
            )
        )
        text_body = _build_text(cust, acct, txns)
        html_body = _build_html(cust, acct, txns)

        existing = session.get(Statement, acct.id)
        if existing is None:
            session.add(
                Statement(
                    acct_id=acct.id,
                    card_num=xref.card_num,
                    text_body=text_body,
                    html_body=html_body,
                )
            )
        else:
            existing.card_num = xref.card_num
            existing.text_body = text_body
            existing.html_body = html_body

        result.statements.append(
            RenderedStatement(acct.id, xref.card_num, text_body, html_body)
        )
    session.flush()
    return result
