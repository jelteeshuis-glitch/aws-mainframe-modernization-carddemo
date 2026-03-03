"""
Transaction Service - Replacing CBTRN02C.cbl (Batch Transaction Posting)
and COTRN02C.cbl (Online Transaction Add via CICS)

Legacy batch flow (CBTRN02C.cbl):
  1. Open 6 VSAM files sequentially
  2. Read DALYTRAN (daily transaction) records one by one
  3. Validate: lookup XREF by card number, lookup ACCT, check credit limit
  4. Post valid transactions to TRANSACT VSAM file
  5. Write rejects to DALYREJS file
  6. Update account balances (ACCTFILE)
  7. Update category balances (TCATBALF)
  8. Close all files, display counts, set return code

Legacy online flow (COTRN02C.cbl):
  1. CICS RECEIVE from BMS map COTRN02
  2. Validate input fields
  3. Write transaction to TRANSACT VSAM
  4. CICS SEND confirmation back to terminal

Modernized flow:
  1. Receive JSON via REST API
  2. Validate with Pydantic schemas
  3. Run real-time fraud detection (NEW)
  4. Process transaction with ACID guarantees (PostgreSQL)
  5. Emit event for downstream consumers (NEW)
  6. Return structured JSON response
"""

import secrets
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from .fraud_service import analyze_transaction

# Simulated data stores (replacing VSAM files)

# Card cross-reference (replaces CARDXREF.VSAM.KSDS)
# Legacy: XREF-CARD-NUM(16) + XREF-CUST-NUM(9) + XREF-ACCT-ID(11) + FILLER(14)
CARD_XREF: dict[str, dict] = {
    "4111111111111111": {"customer_id": 1, "account_id": 1},
    "4222222222222222": {"customer_id": 1, "account_id": 1},
    "5333333333333333": {"customer_id": 2, "account_id": 2},
    "5444444444444444": {"customer_id": 3, "account_id": 3},
}

# Account master (replaces ACCTDATA.VSAM.KSDS)
ACCOUNTS: dict[int, dict] = {
    1: {
        "id": 1,
        "customer_id": 1,
        "status": "Y",
        "current_balance": Decimal("1250.75"),
        "credit_limit": Decimal("10000.00"),
        "cash_credit_limit": Decimal("2000.00"),
        "open_date": "2020-03-15",
        "expiration_date": "2027-03-15",
        "reissue_date": None,
        "current_cycle_credit": Decimal("500.00"),
        "current_cycle_debit": Decimal("1750.75"),
        "zip_code": "10001",
        "group_id": "PREMIUM",
    },
    2: {
        "id": 2,
        "customer_id": 2,
        "status": "Y",
        "current_balance": Decimal("3420.50"),
        "credit_limit": Decimal("15000.00"),
        "cash_credit_limit": Decimal("3000.00"),
        "open_date": "2019-06-01",
        "expiration_date": "2026-06-01",
        "reissue_date": "2023-06-01",
        "current_cycle_credit": Decimal("200.00"),
        "current_cycle_debit": Decimal("3620.50"),
        "zip_code": "94105",
        "group_id": "GOLD",
    },
    3: {
        "id": 3,
        "customer_id": 3,
        "status": "Y",
        "current_balance": Decimal("750.25"),
        "credit_limit": Decimal("5000.00"),
        "cash_credit_limit": Decimal("1000.00"),
        "open_date": "2022-01-10",
        "expiration_date": "2028-01-10",
        "reissue_date": None,
        "current_cycle_credit": Decimal("100.00"),
        "current_cycle_debit": Decimal("850.25"),
        "zip_code": "60601",
        "group_id": "STANDARD",
    },
}

# Customer master (replaces CUSTDATA.VSAM.KSDS)
CUSTOMERS: dict[int, dict] = {
    1: {
        "id": 1,
        "first_name": "Jan",
        "middle_name": "Willem",
        "last_name": "de Vries",
        "address_line_1": "Bijlmerdreef 24",
        "address_line_2": "Amsterdam Zuidoost",
        "address_line_3": "",
        "state_code": "NH",
        "country_code": "NL",
        "zip_code": "1102 CT",
        "phone_primary": "+31 20 555 0101",
        "phone_secondary": "+31 6 1234 5678",
        "ssn_last_four": "4321",
        "date_of_birth": "1985-03-22",
        "eft_account_id": "NL91ABNA0417164300",
        "is_primary_cardholder": True,
        "fico_credit_score": 742,
        "email": "jan.devries@example.nl",
    },
    2: {
        "id": 2,
        "first_name": "Emma",
        "middle_name": None,
        "last_name": "Bakker",
        "address_line_1": "Coolsingel 120",
        "address_line_2": "",
        "address_line_3": "",
        "state_code": "ZH",
        "country_code": "NL",
        "zip_code": "3011 AG",
        "phone_primary": "+31 10 555 0202",
        "phone_secondary": None,
        "ssn_last_four": "8765",
        "date_of_birth": "1990-07-14",
        "eft_account_id": "NL20INGB0001234567",
        "is_primary_cardholder": True,
        "fico_credit_score": 695,
        "email": "emma.bakker@example.nl",
    },
    3: {
        "id": 3,
        "first_name": "Pieter",
        "middle_name": "Johannes",
        "last_name": "Jansen",
        "address_line_1": "Markt 1",
        "address_line_2": "Eindhoven",
        "address_line_3": "",
        "state_code": "NB",
        "country_code": "NL",
        "zip_code": "5611 EB",
        "phone_primary": "+31 40 555 0303",
        "phone_secondary": "+31 6 9876 5432",
        "ssn_last_four": "2468",
        "date_of_birth": "1978-11-30",
        "eft_account_id": "NL18RABO0123456789",
        "is_primary_cardholder": True,
        "fico_credit_score": 810,
        "email": "pieter.jansen@example.nl",
    },
}

# Transaction store (replaces TRANSACT.VSAM.KSDS)
TRANSACTIONS: list[dict] = [
    {
        "id": "0000000000000001",
        "transaction_type": "01",
        "category_code": 5411,
        "source": "POS TERM",
        "description": "Albert Heijn - Groceries",
        "amount": Decimal("87.45"),
        "card_number": "4111111111111111",
        "merchant_id": 100001,
        "merchant_name": "Albert Heijn",
        "merchant_city": "Amsterdam",
        "merchant_zip": "1012 JS",
        "originated_at": "2024-11-15T10:30:00Z",
        "processed_at": "2024-11-15T10:30:02Z",
        "account_id": 1,
        "customer_id": 1,
        "fraud_score": 0.02,
        "fraud_risk_level": "low",
        "fraud_flags": [],
    },
    {
        "id": "0000000000000002",
        "transaction_type": "01",
        "category_code": 5812,
        "source": "POS TERM",
        "description": "Restaurant De Kas - Dining",
        "amount": Decimal("156.00"),
        "card_number": "4111111111111111",
        "merchant_id": 100002,
        "merchant_name": "Restaurant De Kas",
        "merchant_city": "Amsterdam",
        "merchant_zip": "1098 EP",
        "originated_at": "2024-11-16T19:45:00Z",
        "processed_at": "2024-11-16T19:45:01Z",
        "account_id": 1,
        "customer_id": 1,
        "fraud_score": 0.05,
        "fraud_risk_level": "low",
        "fraud_flags": [],
    },
    {
        "id": "0000000000000003",
        "transaction_type": "01",
        "category_code": 4111,
        "source": "ONLINE",
        "description": "NS - Train Ticket Amsterdam-Rotterdam",
        "amount": Decimal("23.50"),
        "card_number": "5333333333333333",
        "merchant_id": 100003,
        "merchant_name": "NS Dutch Railways",
        "merchant_city": "Utrecht",
        "merchant_zip": "3500",
        "originated_at": "2024-11-17T07:15:00Z",
        "processed_at": "2024-11-17T07:15:01Z",
        "account_id": 2,
        "customer_id": 2,
        "fraud_score": 0.01,
        "fraud_risk_level": "low",
        "fraud_flags": [],
    },
    {
        "id": "0000000000000004",
        "transaction_type": "01",
        "category_code": 5691,
        "source": "ONLINE",
        "description": "Bol.com - Electronics Purchase",
        "amount": Decimal("449.99"),
        "card_number": "5333333333333333",
        "merchant_id": 100004,
        "merchant_name": "Bol.com",
        "merchant_city": "Utrecht",
        "merchant_zip": "3500",
        "originated_at": "2024-11-18T14:20:00Z",
        "processed_at": "2024-11-18T14:20:03Z",
        "account_id": 2,
        "customer_id": 2,
        "fraud_score": 0.12,
        "fraud_risk_level": "low",
        "fraud_flags": [],
    },
    {
        "id": "0000000000000005",
        "transaction_type": "02",
        "category_code": 2,
        "source": "ONLINE",
        "description": "Bill Payment - Online",
        "amount": Decimal("-500.00"),
        "card_number": "5444444444444444",
        "merchant_id": 999999999,
        "merchant_name": "BILL PAYMENT",
        "merchant_city": "N/A",
        "merchant_zip": "N/A",
        "originated_at": "2024-11-19T09:00:00Z",
        "processed_at": "2024-11-19T09:00:01Z",
        "account_id": 3,
        "customer_id": 3,
        "fraud_score": 0.01,
        "fraud_risk_level": "low",
        "fraud_flags": [],
    },
]

_transaction_counter = len(TRANSACTIONS)


def _generate_transaction_id() -> str:
    """Generate a 16-character transaction ID (matching legacy TRAN-ID PIC X(16))."""
    global _transaction_counter
    _transaction_counter += 1
    return f"{_transaction_counter:016d}"


def _lookup_xref(card_number: str) -> Optional[dict]:
    """
    Replaces 1500-A-LOOKUP-XREF in CBTRN02C.cbl:
        MOVE DALYTRAN-CARD-NUM TO FD-XREF-CARD-NUM
        READ XREF-FILE INTO CARD-XREF-RECORD
           INVALID KEY
             MOVE 100 TO WS-VALIDATION-FAIL-REASON
             MOVE 'INVALID CARD NUMBER FOUND'
    """
    return CARD_XREF.get(card_number)


def _lookup_account(account_id: int) -> Optional[dict]:
    """
    Replaces 1500-B-LOOKUP-ACCT in CBTRN02C.cbl:
        MOVE XREF-ACCT-ID TO FD-ACCT-ID
        READ ACCOUNT-FILE INTO ACCOUNT-RECORD
    """
    return ACCOUNTS.get(account_id)


def process_transaction(
    card_number: str,
    transaction_type: str,
    category_code: int,
    source: str,
    description: str,
    amount: Decimal,
    merchant_id: Optional[int] = None,
    merchant_name: Optional[str] = None,
    merchant_city: Optional[str] = None,
    merchant_zip: Optional[str] = None,
) -> dict:
    """
    Process a transaction - replaces the main loop in CBTRN02C.cbl:
        PERFORM 1500-VALIDATE-TRAN
        IF WS-VALIDATION-FAIL-REASON = 0
          PERFORM 2000-POST-TRANSACTION
        ELSE
          PERFORM 2500-WRITE-REJECT-REC

    Enhanced with real-time fraud detection (NEW).
    """
    now = datetime.now(timezone.utc)

    # Step 1: Card lookup (was: 1500-A-LOOKUP-XREF)
    xref = _lookup_xref(card_number)
    if not xref:
        raise ValueError(
            f"VALIDATION ERROR 100: Card number not found in cross-reference. "
            f"Legacy equivalent: 'INVALID CARD NUMBER FOUND' (CBTRN02C.cbl line 386)"
        )

    # Step 2: Account lookup (was: 1500-B-LOOKUP-ACCT)
    account = _lookup_account(xref["account_id"])
    if not account:
        raise ValueError(
            f"VALIDATION ERROR 101: Account record not found. "
            f"Legacy equivalent: 'ACCOUNT RECORD NOT FOUND' (CBTRN02C.cbl line 398)"
        )

    # Step 3: Credit limit check (was: lines 403-413 of CBTRN02C.cbl)
    if amount > 0:  # Only check for charges, not payments
        temp_bal = account["current_cycle_debit"] - account["current_cycle_credit"] + amount
        if account["credit_limit"] < temp_bal:
            raise ValueError(
                f"VALIDATION ERROR 102: Transaction would exceed credit limit. "
                f"Limit: {account['credit_limit']}, Projected: {temp_bal}. "
                f"Legacy equivalent: 'OVERLIMIT TRANSACTION' (CBTRN02C.cbl line 411)"
            )

    # Step 4: Expiration check (was: lines 414-420 of CBTRN02C.cbl)
    if account["expiration_date"] < now.strftime("%Y-%m-%d"):
        raise ValueError(
            f"VALIDATION ERROR 103: Account expired on {account['expiration_date']}. "
            f"Legacy equivalent: 'TRANSACTION RECEIVED AFTER ACCT EXPIRATION' (CBTRN02C.cbl line 418)"
        )

    # Step 5: FRAUD DETECTION (NEW - the "ADD MORE VALIDATIONS HERE" from line 377)
    fraud_result = analyze_transaction(
        card_number=card_number,
        amount=amount,
        merchant_name=merchant_name,
        merchant_city=merchant_city,
        merchant_zip=merchant_zip,
        transaction_type=transaction_type,
        source=source,
        account_credit_limit=account["credit_limit"],
        account_current_balance=account["current_balance"],
    )

    if fraud_result["risk_level"] == "critical":
        raise ValueError(
            f"FRAUD ALERT: Transaction blocked by fraud detection engine. "
            f"Risk score: {fraud_result['risk_score']:.2f}. "
            f"Flags: {', '.join(fraud_result['flags'])}. "
            f"This check was NOT possible in the legacy system."
        )

    # Step 6: Post transaction (was: 2000-POST-TRANSACTION + 2800-UPDATE-ACCOUNT-REC + 2900-WRITE-TRANSACTION-FILE)
    transaction_id = _generate_transaction_id()

    transaction = {
        "id": transaction_id,
        "transaction_type": transaction_type,
        "category_code": category_code,
        "source": source,
        "description": description,
        "amount": amount,
        "card_number": card_number,
        "merchant_id": merchant_id,
        "merchant_name": merchant_name,
        "merchant_city": merchant_city,
        "merchant_zip": merchant_zip,
        "originated_at": now.isoformat(),
        "processed_at": now.isoformat(),
        "account_id": xref["account_id"],
        "customer_id": xref["customer_id"],
        "fraud_score": fraud_result["risk_score"],
        "fraud_risk_level": fraud_result["risk_level"],
        "fraud_flags": fraud_result["flags"],
    }

    TRANSACTIONS.append(transaction)

    # Update account balances (was: 2800-UPDATE-ACCOUNT-REC)
    account["current_balance"] += amount
    if amount >= 0:
        account["current_cycle_credit"] += amount
    else:
        account["current_cycle_debit"] += amount  # amount is negative, matching COBOL: ADD DALYTRAN-AMT TO ACCT-CURR-CYC-DEBIT

    return transaction


def get_transactions(
    account_id: Optional[int] = None,
    card_number: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    List transactions - replaces COTRN00C.cbl (Transaction List) CICS screen.
    Enhanced with pagination, filtering, and fraud data.
    """
    filtered = TRANSACTIONS

    if account_id:
        filtered = [t for t in filtered if t["account_id"] == account_id]
    if card_number:
        filtered = [t for t in filtered if t["card_number"] == card_number]

    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "transactions": filtered[start:end],
        "total_count": total,
        "page": page,
        "page_size": page_size,
    }


def get_transaction_by_id(transaction_id: str) -> Optional[dict]:
    """Replaces COTRN01C.cbl (Transaction View) CICS screen."""
    for t in TRANSACTIONS:
        if t["id"] == transaction_id:
            return t
    return None


def process_bill_payment(account_id: int, amount: Optional[Decimal] = None) -> dict:
    """
    Replaces COBIL00C.cbl - Bill Payment processing.

    Legacy flow:
      1. Read ACCTDAT by account ID
      2. Read CXACAIX (card xref by account alternate index)
      3. STARTBR/READPREV TRANSACT to get last transaction ID
      4. Create new transaction record with type '02' (payment)
      5. COMPUTE ACCT-CURR-BAL = ACCT-CURR-BAL - TRAN-AMT
      6. REWRITE account record
    """
    account = ACCOUNTS.get(account_id)
    if not account:
        raise ValueError("Account not found")

    if account["current_balance"] <= 0:
        raise ValueError("Nothing to pay - balance is zero or credit")

    payment_amount = amount if amount is not None else account["current_balance"]
    if payment_amount > account["current_balance"]:
        payment_amount = account["current_balance"]

    # Find card for this account
    card_number = None
    for card, xref in CARD_XREF.items():
        if xref["account_id"] == account_id:
            card_number = card
            break

    if not card_number:
        raise ValueError("No card found for account")

    previous_balance = account["current_balance"]

    # Process as a payment transaction
    transaction = process_transaction(
        card_number=card_number,
        transaction_type="02",
        category_code=2,
        source="ONLINE",
        description="BILL PAYMENT - ONLINE",
        amount=-payment_amount,  # Negative for payment
        merchant_id=999999999,
        merchant_name="BILL PAYMENT",
        merchant_city="N/A",
        merchant_zip="N/A",
    )

    return {
        "transaction_id": transaction["id"],
        "account_id": account_id,
        "amount_paid": payment_amount,
        "previous_balance": previous_balance,
        "new_balance": account["current_balance"],
        "payment_date": datetime.now(timezone.utc).isoformat(),
        "confirmation_number": f"PAY-{secrets.token_hex(6).upper()}",
    }


def get_accounts() -> list[dict]:
    """List all accounts with customer info."""
    result = []
    for acct_id, acct in ACCOUNTS.items():
        customer = CUSTOMERS.get(acct["customer_id"], {})
        result.append({
            **acct,
            "customer_name": f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
            "customer_email": customer.get("email"),
        })
    return result


def get_account_by_id(account_id: int) -> Optional[dict]:
    """Get account details with customer info."""
    acct = ACCOUNTS.get(account_id)
    if not acct:
        return None
    customer = CUSTOMERS.get(acct["customer_id"], {})
    return {
        **acct,
        "customer": customer,
    }


def get_customers() -> list[dict]:
    """List all customers."""
    return list(CUSTOMERS.values())


def get_customer_by_id(customer_id: int) -> Optional[dict]:
    """Get customer details."""
    return CUSTOMERS.get(customer_id)
