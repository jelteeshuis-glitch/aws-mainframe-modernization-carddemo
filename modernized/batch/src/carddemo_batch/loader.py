"""Load the fixed-width CardDemo sample data (``app/data/ASCII``) into the database.

This is the modern equivalent of the ``IDCAMS REPRO`` / ``IEBGENER`` "refresh" jobs that
load the VSAM masters (ACCTFILE, XREFFILE, CUSTFILE, DISCGRP, TCATBALF, TRANCATG,
TRANTYPE) plus staging the daily transaction file for POSTTRAN.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from . import copybook
from .models import (
    Account,
    CardXref,
    Customer,
    DailyTransaction,
    DisclosureGroup,
    TranCatBalance,
    TransactionCategoryType,
    TransactionType,
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_accounts(session: Session, data_dir: Path) -> int:
    rows = list(copybook.iter_records(_read(data_dir / "acctdata.txt"), copybook.ACCOUNT_FIELDS))
    session.add_all(Account(**r) for r in rows)
    return len(rows)


def load_xref(session: Session, data_dir: Path) -> int:
    rows = list(copybook.iter_records(_read(data_dir / "cardxref.txt"), copybook.XREF_FIELDS))
    session.add_all(CardXref(**r) for r in rows)
    return len(rows)


def load_customers(session: Session, data_dir: Path) -> int:
    rows = list(copybook.iter_records(_read(data_dir / "custdata.txt"), copybook.CUSTOMER_FIELDS))
    # Keep only the columns the Customer model exposes.
    keep = {c.name for c in Customer.__table__.columns}
    session.add_all(Customer(**{k: v for k, v in r.items() if k in keep}) for r in rows)
    return len(rows)


def load_disclosure_groups(session: Session, data_dir: Path) -> int:
    rows = list(copybook.iter_records(_read(data_dir / "discgrp.txt"), copybook.DISCGRP_FIELDS))
    session.add_all(DisclosureGroup(**r) for r in rows)
    return len(rows)


def load_tran_cat_balances(session: Session, data_dir: Path) -> int:
    rows = list(copybook.iter_records(_read(data_dir / "tcatbal.txt"), copybook.TCATBAL_FIELDS))
    session.add_all(TranCatBalance(**r) for r in rows)
    return len(rows)


def load_tran_categories(session: Session, data_dir: Path) -> int:
    rows = list(copybook.iter_records(_read(data_dir / "trancatg.txt"), copybook.TRANCATG_FIELDS))
    session.add_all(TransactionCategoryType(**r) for r in rows)
    return len(rows)


def load_tran_types(session: Session, data_dir: Path) -> int:
    rows = list(copybook.iter_records(_read(data_dir / "trantype.txt"), copybook.TRANTYPE_FIELDS))
    session.add_all(TransactionType(**r) for r in rows)
    return len(rows)


def load_daily_transactions(session: Session, data_dir: Path) -> int:
    rows = list(copybook.iter_records(_read(data_dir / "dailytran.txt"), copybook.DALYTRAN_FIELDS))
    session.add_all(DailyTransaction(**r) for r in rows)
    return len(rows)


def load_all(session: Session, data_dir: Path) -> dict[str, int]:
    """Load every master and the daily transaction staging table; return row counts."""
    return {
        "accounts": load_accounts(session, data_dir),
        "xref": load_xref(session, data_dir),
        "customers": load_customers(session, data_dir),
        "disclosure_groups": load_disclosure_groups(session, data_dir),
        "tran_cat_balances": load_tran_cat_balances(session, data_dir),
        "tran_categories": load_tran_categories(session, data_dir),
        "tran_types": load_tran_types(session, data_dir),
        "daily_transactions": load_daily_transactions(session, data_dir),
    }
