"""Fixed-width record parsing for the CardDemo copybook layouts.

The original CardDemo data files (``app/data/ASCII``) are fixed-width records that mirror
the COBOL copybooks. Signed numeric fields (``PIC S9(n)V99`` ``DISPLAY``) carry their
sign in the last byte as an *overpunch* character; ``V99`` means the last two digits are
implied decimals. This module decodes those layouts into plain Python values so the
services can work with :class:`~decimal.Decimal` money amounts and ``str`` text fields.

See ``BUSINESS_RULES.md`` section 1 for the overpunch table and the field maps.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

# Overpunch: the final byte of a signed zoned-decimal field encodes the last digit and
# the sign of the whole number.
_OVERPUNCH_POSITIVE = {
    "{": "0", "A": "1", "B": "2", "C": "3", "D": "4",
    "E": "5", "F": "6", "G": "7", "H": "8", "I": "9",
}
_OVERPUNCH_NEGATIVE = {
    "}": "0", "J": "1", "K": "2", "L": "3", "M": "4",
    "N": "5", "O": "6", "P": "7", "Q": "8", "R": "9",
}


def decode_signed(raw: str, decimals: int = 2) -> Decimal:
    """Decode a signed zoned-decimal ``PIC S9(n)V(decimals)`` field to a ``Decimal``.

    Handles the trailing overpunch sign byte; if the last byte is already a plain digit
    the value is treated as positive.
    """
    raw = raw.strip()
    if not raw:
        return Decimal(0)
    last = raw[-1]
    if last in _OVERPUNCH_POSITIVE:
        digits = raw[:-1] + _OVERPUNCH_POSITIVE[last]
        sign = 1
    elif last in _OVERPUNCH_NEGATIVE:
        digits = raw[:-1] + _OVERPUNCH_NEGATIVE[last]
        sign = -1
    else:
        digits = raw
        sign = -1 if digits.startswith("-") else 1
        digits = digits.lstrip("+-")
    if not digits.isdigit():
        raise ValueError(f"cannot decode signed numeric field: {raw!r}")
    value = Decimal(digits)
    if decimals:
        value = value.scaleb(-decimals)
    return value * sign


def decode_unsigned(raw: str) -> int:
    """Decode an unsigned zoned-decimal ``PIC 9(n)`` field to an ``int``."""
    raw = raw.strip()
    return int(raw) if raw else 0


def encode_signed(value: Decimal, length: int, decimals: int = 2) -> str:
    """Encode a ``Decimal`` back into a signed zoned-decimal field of ``length`` bytes.

    Inverse of :func:`decode_signed`; used when writing reject records that must retain
    the original 350-byte daily-transaction layout.
    """
    quant = Decimal(1).scaleb(-decimals)
    scaled = int((abs(value).quantize(quant)).scaleb(decimals))
    digits = str(scaled).rjust(length, "0")[-length:]
    body, last = digits[:-1], digits[-1]
    table = _OVERPUNCH_POSITIVE if value >= 0 else _OVERPUNCH_NEGATIVE
    inverse = {v: k for k, v in table.items()}
    return body + inverse[last]


@dataclass(frozen=True)
class Field:
    """A single fixed-width field: name, 1-based COBOL start column and byte length."""

    name: str
    start: int  # 1-based, matching COBOL column numbering
    length: int
    kind: str = "text"  # "text" | "unsigned" | "signed"
    decimals: int = 2

    def slice(self, record: str) -> str:
        return record[self.start - 1 : self.start - 1 + self.length]

    def parse(self, record: str):
        raw = self.slice(record)
        if self.kind == "text":
            return raw.rstrip()
        if self.kind == "unsigned":
            return decode_unsigned(raw)
        if self.kind == "signed":
            return decode_signed(raw, self.decimals)
        raise ValueError(f"unknown field kind {self.kind!r}")


def parse_record(record: str, fields: list[Field]) -> dict:
    """Parse one fixed-width record string into a dict keyed by field name."""
    return {f.name: f.parse(record) for f in fields}


def iter_records(text: str, fields: list[Field]):
    """Yield parsed dicts for each non-empty line of ``text``."""
    for line in text.splitlines():
        # Strip a trailing CR (files use mixed line endings) but keep field padding.
        line = line.rstrip("\r\n")
        if not line.strip():
            continue
        yield parse_record(line, fields)


# --- Copybook field maps (1-based COBOL columns) --------------------------------------

# CVTRA06Y DALYTRAN-RECORD (350). Same physical layout as CVTRA05Y TRAN-RECORD.
DALYTRAN_FIELDS = [
    Field("id", 1, 16),
    Field("type_cd", 17, 2),
    Field("cat_cd", 19, 4, "unsigned"),
    Field("source", 23, 10),
    Field("description", 33, 100),
    Field("amount", 133, 11, "signed"),
    Field("merchant_id", 144, 9, "unsigned"),
    Field("merchant_name", 153, 50),
    Field("merchant_city", 203, 50),
    Field("merchant_zip", 253, 10),
    Field("card_num", 263, 16),
    Field("orig_ts", 279, 26),
    Field("proc_ts", 305, 26),
]

# CVACT01Y ACCOUNT-RECORD (300)
ACCOUNT_FIELDS = [
    Field("id", 1, 11, "unsigned"),
    Field("active_status", 12, 1),
    Field("curr_bal", 13, 12, "signed"),
    Field("credit_limit", 25, 12, "signed"),
    Field("cash_credit_limit", 37, 12, "signed"),
    Field("open_date", 49, 10),
    Field("expiration_date", 59, 10),
    Field("reissue_date", 69, 10),
    Field("curr_cyc_credit", 79, 12, "signed"),
    Field("curr_cyc_debit", 91, 12, "signed"),
    Field("addr_zip", 103, 10),
    Field("group_id", 113, 10),
]

# CVACT03Y CARD-XREF-RECORD (50)
XREF_FIELDS = [
    Field("card_num", 1, 16),
    Field("cust_id", 17, 9, "unsigned"),
    Field("acct_id", 26, 11, "unsigned"),
]

# CVTRA01Y TRAN-CAT-BAL-RECORD (50)
TCATBAL_FIELDS = [
    Field("acct_id", 1, 11, "unsigned"),
    Field("type_cd", 12, 2),
    Field("cat_cd", 14, 4, "unsigned"),
    Field("balance", 18, 11, "signed"),
]

# CVTRA02Y DIS-GROUP-RECORD (50)
DISCGRP_FIELDS = [
    Field("group_id", 1, 10),
    Field("type_cd", 11, 2),
    Field("cat_cd", 13, 4, "unsigned"),
    Field("int_rate", 17, 6, "signed"),
]

# CVTRA03Y TRAN-TYPE-RECORD (60)
TRANTYPE_FIELDS = [
    Field("type_cd", 1, 2),
    Field("description", 3, 50),
]

# CVTRA04Y TRAN-CAT-RECORD (60)
TRANCATG_FIELDS = [
    Field("type_cd", 1, 2),
    Field("cat_cd", 3, 4, "unsigned"),
    Field("description", 7, 50),
]

# CUSTREC / CVCUS01Y CUSTOMER-RECORD (500)
CUSTOMER_FIELDS = [
    Field("id", 1, 9, "unsigned"),
    Field("first_name", 10, 25),
    Field("middle_name", 35, 25),
    Field("last_name", 60, 25),
    Field("addr_line_1", 85, 50),
    Field("addr_line_2", 135, 50),
    Field("addr_line_3", 185, 50),
    Field("addr_state_cd", 235, 2),
    Field("addr_country_cd", 237, 3),
    Field("addr_zip", 240, 10),
    Field("phone_num_1", 250, 15),
    Field("phone_num_2", 265, 15),
    Field("ssn", 280, 9, "unsigned"),
    Field("govt_issued_id", 289, 20),
    Field("dob", 309, 10),
    Field("eft_account_id", 319, 10),
    Field("pri_card_holder_ind", 329, 1),
    Field("fico_credit_score", 330, 3, "unsigned"),
]
