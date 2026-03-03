"""
Transaction Router - REST API replacing CBTRN02C.cbl (batch) and COTRN02C.cbl (online)

Legacy endpoints (CICS):
  CT00 -> COTRN00C -> Transaction List
  CT01 -> COTRN01C -> Transaction View
  CT02 -> COTRN02C -> Transaction Add
  CB00 -> COBIL00C -> Bill Payment
  CR00 -> CORPT00C -> Transaction Report

Modernized endpoints:
  GET    /api/v1/transactions          -> List transactions (paginated)
  GET    /api/v1/transactions/{id}     -> View transaction detail
  POST   /api/v1/transactions          -> Create transaction (with fraud check)
  POST   /api/v1/transactions/bill-pay -> Process bill payment
"""

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..services.transaction_service import (
    get_transaction_by_id,
    get_transactions,
    process_bill_payment,
    process_transaction,
)

router = APIRouter(prefix="/api/v1/transactions", tags=["Transactions"])


@router.get("", summary="List transactions - replaces CT00 CICS transaction")
async def list_transactions(
    account_id: Optional[int] = Query(None, description="Filter by account ID"),
    card_number: Optional[str] = Query(None, description="Filter by card number"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    List transactions with pagination and filtering.

    Replaces COTRN00C.cbl which displayed transactions in a CICS BMS
    screen with PF7/PF8 for paging. The legacy screen was limited to
    displaying ~10 records at a time on a 24x80 terminal.

    The modern API supports arbitrary page sizes, filtering, and
    returns structured JSON instead of fixed-format screen data.
    """
    return get_transactions(
        account_id=account_id,
        card_number=card_number,
        page=page,
        page_size=page_size,
    )


@router.get("/{transaction_id}", summary="View transaction - replaces CT01 CICS transaction")
async def view_transaction(transaction_id: str):
    """
    View transaction details. Replaces COTRN01C.cbl.

    The legacy screen showed transaction details on a single BMS map.
    The modern API returns full transaction data including fraud analysis
    results that were not available in the legacy system.
    """
    transaction = get_transaction_by_id(transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@router.post("", summary="Create transaction - replaces CT02 CICS + CBTRN02C batch")
async def create_transaction(
    card_number: str,
    transaction_type: str = "01",
    category_code: int = 5411,
    source: str = "ONLINE",
    description: str = "Purchase",
    amount: float = 0.0,
    merchant_id: Optional[int] = None,
    merchant_name: Optional[str] = None,
    merchant_city: Optional[str] = None,
    merchant_zip: Optional[str] = None,
):
    """
    Create and post a transaction with real-time fraud detection.

    This endpoint combines and modernizes:
    1. COTRN02C.cbl (online add via CICS BMS screen)
    2. CBTRN02C.cbl (batch posting from daily transaction file)

    Key improvements over legacy:
    - Real-time processing (was: batch-only for CBTRN02C)
    - ML-based fraud detection (was: basic validation only)
    - Structured error responses (was: ABEND codes)
    - Full audit trail with timestamps
    """
    try:
        result = process_transaction(
            card_number=card_number,
            transaction_type=transaction_type,
            category_code=category_code,
            source=source,
            description=description,
            amount=Decimal(str(amount)),
            merchant_id=merchant_id,
            merchant_name=merchant_name,
            merchant_city=merchant_city,
            merchant_zip=merchant_zip,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bill-pay", summary="Bill payment - replaces CB00 CICS transaction")
async def bill_payment(
    account_id: int,
    amount: Optional[float] = None,
):
    """
    Process a bill payment. Replaces COBIL00C.cbl.

    Legacy flow:
    1. CICS READ ACCTDAT -> get account balance
    2. CICS READ CXACAIX -> get card for account
    3. STARTBR/READPREV TRANSACT -> get next transaction ID
    4. Create payment transaction with type '02'
    5. COMPUTE ACCT-CURR-BAL = ACCT-CURR-BAL - TRAN-AMT
    6. CICS REWRITE ACCTDAT

    Modern flow does the same with added fraud detection and
    returns a confirmation number.
    """
    try:
        result = process_bill_payment(
            account_id=account_id,
            amount=Decimal(str(amount)) if amount else None,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
