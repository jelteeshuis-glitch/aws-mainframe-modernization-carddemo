"""Tests for the fixed-width copybook parser and zoned-decimal overpunch handling."""

from __future__ import annotations

from decimal import Decimal

import pytest

from carddemo_batch import copybook


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("00000001940{", Decimal("194.00")),   # {  -> 0 positive
        ("0000005047G", Decimal("504.77")),    # G  -> 7 positive
        ("00000000000}", Decimal("0.00")),     # }  -> 0 negative
        ("0000000056O", Decimal("-5.66")),     # O  -> 6 negative
        ("00000000091J", Decimal("-9.11")),    # J  -> 1 negative
    ],
)
def test_decode_signed_overpunch(raw: str, expected: Decimal) -> None:
    assert copybook.decode_signed(raw) == expected


def test_decode_signed_plain_digits() -> None:
    # A trailing plain digit is treated as an unsigned positive value.
    assert copybook.decode_signed("00012345") == Decimal("123.45")


def test_encode_signed_roundtrip() -> None:
    for value in (Decimal("194.00"), Decimal("-56.06"), Decimal("504.77"), Decimal("0.00")):
        encoded = copybook.encode_signed(value, length=12)
        assert copybook.decode_signed(encoded) == value


def test_decode_unsigned() -> None:
    assert copybook.decode_unsigned("00000042") == 42
    assert copybook.decode_unsigned("   ") == 0


def test_parse_account_record() -> None:
    line = (
        "00000000001Y00000001940{00000020200{00000010200{"
        "2014-11-202025-05-202025-05-2000000000000{00000000000{A000000000"
    ).ljust(300)
    rec = copybook.parse_record(line, copybook.ACCOUNT_FIELDS)
    assert rec["id"] == 1
    assert rec["active_status"] == "Y"
    assert rec["curr_bal"] == Decimal("194.00")
    assert rec["credit_limit"] == Decimal("2020.00")
    assert rec["cash_credit_limit"] == Decimal("1020.00")
    assert rec["open_date"] == "2014-11-20"
    assert rec["expiration_date"] == "2025-05-20"


def test_parse_dalytran_record_from_fixture(data_dir) -> None:
    line = (data_dir / "dailytran.txt").read_text().splitlines()[0].rstrip("\r\n")
    rec = copybook.parse_record(line, copybook.DALYTRAN_FIELDS)
    assert rec["type_cd"] == "01"
    assert rec["cat_cd"] == 1
    assert rec["source"] == "POS TERM"
    assert rec["amount"] == Decimal("504.77")
    assert rec["card_num"] == "4859452612877065"
    assert rec["orig_ts"].startswith("2022-06-10")
