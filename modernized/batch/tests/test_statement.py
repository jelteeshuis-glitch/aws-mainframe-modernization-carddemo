"""Unit tests for the CREASTMT (CBSTM03A) statement-generation service."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from carddemo_batch.models import Account, CardXref, Customer, Transaction
from carddemo_batch.services import statement

CARD_A = "1111111111111111"
CARD_B = "2222222222222222"


def _setup(session: Session) -> None:
    session.add(Account(id=101, curr_bal=Decimal("1500.00"), group_id="G1"))
    session.add(Account(id=202, curr_bal=Decimal("42.00"), group_id="G1"))
    session.add(Customer(id=1, first_name="Jane", middle_name="Q", last_name="Doe",
                         addr_line_1="1 Main St", addr_line_2="Apt 2",
                         addr_line_3="Springfield", addr_state_cd="IL",
                         addr_country_cd="USA", addr_zip="62701",
                         fico_credit_score=742))
    session.add(Customer(id=2, first_name="John", last_name="Roe", fico_credit_score=650))
    session.add(CardXref(card_num=CARD_A, cust_id=1, acct_id=101))
    session.add(CardXref(card_num=CARD_B, cust_id=2, acct_id=202))
    session.add(Transaction(id="A1", description="Coffee", amount=Decimal("4.50"),
                            card_num=CARD_A))
    session.add(Transaction(id="A2", description="Books", amount=Decimal("30.00"),
                            card_num=CARD_A))
    session.add(Transaction(id="B1", description="Fuel", amount=Decimal("60.00"),
                            card_num=CARD_B))
    session.commit()


def test_one_statement_per_card_with_grouped_transactions(session: Session) -> None:
    _setup(session)
    result = statement.run(session)
    session.commit()

    assert result.count == 2
    by_acct = {s.acct_id: s for s in result.statements}
    text_a = by_acct[101].text_body
    assert "Jane Q Doe" in text_a
    assert "Account ID      : 101" in text_a
    assert "Current Balance : 1,500.00" in text_a
    assert "FICO Score      : 742" in text_a
    # Only card A's transactions appear on account 101's statement.
    assert "Coffee" in text_a and "Books" in text_a
    assert "Fuel" not in text_a
    # Total EXP = 4.50 + 30.00 = 34.50
    assert "34.50" in text_a


def test_html_output_is_escaped(session: Session) -> None:
    session.add(Account(id=101, curr_bal=Decimal("0.00"), group_id="G1"))
    session.add(Customer(id=1, first_name="Jane", last_name="Doe", fico_credit_score=700))
    session.add(CardXref(card_num=CARD_A, cust_id=1, acct_id=101))
    session.add(Transaction(id="A1", description="<script>alert(1)</script>",
                            amount=Decimal("1.00"), card_num=CARD_A))
    session.commit()

    result = statement.run(session)
    html = result.statements[0].html_body
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "<!DOCTYPE html>" in html
