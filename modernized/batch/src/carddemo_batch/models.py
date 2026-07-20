"""SQLAlchemy ORM models — the relational schema derived from the CardDemo copybooks.

Each table maps to a VSAM/PS file used by the original batch programs. Money fields use
``Numeric`` (arbitrary-precision) to preserve exact ``PIC S9(n)V99`` semantics. The
same models drive both PostgreSQL (production, see ``schema/schema.sql``) and the
SQLite databases used by the test suite.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

MONEY = Numeric(14, 2)
RATE = Numeric(6, 2)


class Base(DeclarativeBase):
    pass


class CardXref(Base):
    """CVACT03Y CARD-XREF-RECORD — links card number to customer and account."""

    __tablename__ = "card_xref"

    card_num: Mapped[str] = mapped_column(String(16), primary_key=True)
    cust_id: Mapped[int] = mapped_column(Integer, nullable=False)
    acct_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)


class Account(Base):
    """CVACT01Y ACCOUNT-RECORD — account master."""

    __tablename__ = "account"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    active_status: Mapped[str] = mapped_column(String(1), default="Y")
    curr_bal: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    credit_limit: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    cash_credit_limit: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    open_date: Mapped[str] = mapped_column(String(10), default="")
    expiration_date: Mapped[str] = mapped_column(String(10), default="")
    reissue_date: Mapped[str] = mapped_column(String(10), default="")
    curr_cyc_credit: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    curr_cyc_debit: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    addr_zip: Mapped[str] = mapped_column(String(10), default="")
    group_id: Mapped[str] = mapped_column(String(10), default="")


class Customer(Base):
    """CVCUS01Y / CUSTREC CUSTOMER-RECORD — customer master."""

    __tablename__ = "customer"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    first_name: Mapped[str] = mapped_column(String(25), default="")
    middle_name: Mapped[str] = mapped_column(String(25), default="")
    last_name: Mapped[str] = mapped_column(String(25), default="")
    addr_line_1: Mapped[str] = mapped_column(String(50), default="")
    addr_line_2: Mapped[str] = mapped_column(String(50), default="")
    addr_line_3: Mapped[str] = mapped_column(String(50), default="")
    addr_state_cd: Mapped[str] = mapped_column(String(2), default="")
    addr_country_cd: Mapped[str] = mapped_column(String(3), default="")
    addr_zip: Mapped[str] = mapped_column(String(10), default="")
    fico_credit_score: Mapped[int] = mapped_column(Integer, default=0)


class DisclosureGroup(Base):
    """CVTRA02Y DIS-GROUP-RECORD — interest rate per (group, type, category)."""

    __tablename__ = "disclosure_group"

    group_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    type_cd: Mapped[str] = mapped_column(String(2), primary_key=True)
    cat_cd: Mapped[int] = mapped_column(Integer, primary_key=True)
    int_rate: Mapped[Decimal] = mapped_column(RATE, default=Decimal("0"))


class TranCatBalance(Base):
    """CVTRA01Y TRAN-CAT-BAL-RECORD — per (account, type, category) running balance."""

    __tablename__ = "tran_cat_balance"

    acct_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type_cd: Mapped[str] = mapped_column(String(2), primary_key=True)
    cat_cd: Mapped[int] = mapped_column(Integer, primary_key=True)
    balance: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))


class TransactionType(Base):
    """CVTRA03Y TRAN-TYPE-RECORD."""

    __tablename__ = "transaction_type"

    type_cd: Mapped[str] = mapped_column(String(2), primary_key=True)
    description: Mapped[str] = mapped_column(String(50), default="")


class TransactionCategoryType(Base):
    """CVTRA04Y TRAN-CAT-RECORD."""

    __tablename__ = "transaction_category_type"

    type_cd: Mapped[str] = mapped_column(String(2), primary_key=True)
    cat_cd: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(50), default="")


class _TransactionColumns:
    """Shared column definitions for the CVTRA05Y/CVTRA06Y transaction layout."""

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    type_cd: Mapped[str] = mapped_column(String(2), default="")
    cat_cd: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(10), default="")
    description: Mapped[str] = mapped_column(String(100), default="")
    amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    merchant_id: Mapped[int] = mapped_column(Integer, default=0)
    merchant_name: Mapped[str] = mapped_column(String(50), default="")
    merchant_city: Mapped[str] = mapped_column(String(50), default="")
    merchant_zip: Mapped[str] = mapped_column(String(10), default="")
    card_num: Mapped[str] = mapped_column(String(16), default="", index=True)
    orig_ts: Mapped[str] = mapped_column(String(26), default="")
    proc_ts: Mapped[str] = mapped_column(String(26), default="")


class DailyTransaction(_TransactionColumns, Base):
    """CVTRA06Y DALYTRAN-RECORD — the daily input file staged for POSTTRAN.

    ``seq`` preserves the sequential file order the COBOL program reads records in.
    """

    __tablename__ = "daily_transaction"

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(16), index=True, default="")


class Transaction(_TransactionColumns, Base):
    """CVTRA05Y TRAN-RECORD — the posted transaction master."""

    __tablename__ = "transaction"


class SystemTransaction(_TransactionColumns, Base):
    """Interest transactions generated by INTCALC (the SYSTRAN file) before COMBTRAN."""

    __tablename__ = "system_transaction"


class DailyReject(Base):
    """Rejected daily transactions (the DALYREJS file) with the validation trailer."""

    __tablename__ = "daily_reject"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tran_id: Mapped[str] = mapped_column(String(16), default="")
    reason_code: Mapped[int] = mapped_column(Integer, default=0)
    reason_desc: Mapped[str] = mapped_column(String(76), default="")
    raw_record: Mapped[str] = mapped_column(String(430), default="")


class Statement(Base):
    """Generated statement output for CREASTMT (text + HTML per account)."""

    __tablename__ = "statement"

    acct_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_num: Mapped[str] = mapped_column(String(16), default="")
    text_body: Mapped[str] = mapped_column(String(), default="")
    html_body: Mapped[str] = mapped_column(String(), default="")


class TransactionReport(Base):
    """Rendered TRANREPT output (single row holding the full report text)."""

    __tablename__ = "transaction_report"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    start_date: Mapped[str] = mapped_column(String(10), default="")
    end_date: Mapped[str] = mapped_column(String(10), default="")
    body: Mapped[str] = mapped_column(String(), default="")


# Foreign keys are omitted deliberately: the original VSAM files have no enforced
# referential integrity and POSTTRAN must be able to *detect* missing xref / account
# rows (reject reasons 100 / 101) rather than fail on a database constraint.
