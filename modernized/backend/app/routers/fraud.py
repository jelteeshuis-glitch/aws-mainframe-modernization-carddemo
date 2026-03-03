"""
Fraud Detection Router - NEW capability enabled by modernization

This router has NO legacy equivalent. The original CardDemo only had
basic validation (card exists, account exists, credit limit check).

The comment at CBTRN02C.cbl line 377 says it all:
    * ADD MORE VALIDATIONS HERE

This is what those "more validations" look like on a modern platform.
"""

from decimal import Decimal

from fastapi import APIRouter

from ..services.fraud_service import analyze_transaction

router = APIRouter(prefix="/api/v1/fraud", tags=["Fraud Detection (NEW)"])


@router.post("/check", summary="Real-time fraud check - NEW capability")
async def check_fraud(
    card_number: str,
    amount: float,
    merchant_name: str = "Unknown",
    merchant_city: str = "Unknown",
    merchant_zip: str = "Unknown",
    transaction_type: str = "01",
    source: str = "ONLINE",
):
    """
    Perform real-time fraud analysis on a proposed transaction.

    This endpoint demonstrates a capability that was IMPOSSIBLE in the
    legacy mainframe batch architecture:

    - The legacy CBTRN02C.cbl processed transactions in batch mode
      (via JCL job POSTTRAN) - there was no way to check fraud in
      real-time before the transaction was posted.

    - The only "validation" was checking if the card/account existed
      and if the credit limit would be exceeded.

    The modern fraud engine analyzes:
    1. Transaction amount patterns
    2. Velocity (multiple transactions in short time)
    3. Merchant risk profiling
    4. Geographic anomaly detection
    5. Time-of-day analysis
    6. Credit utilization patterns
    7. Round amount detection

    Try these scenarios:
    - Normal: card=4111111111111111, amount=50, merchant_name=Albert Heijn
    - High risk: card=4111111111111111, amount=8000, merchant_name=CRYPTO EXCHANGE
    - Velocity: Submit 5+ requests quickly with the same card
    """
    result = analyze_transaction(
        card_number=card_number,
        amount=Decimal(str(amount)),
        merchant_name=merchant_name,
        merchant_city=merchant_city,
        merchant_zip=merchant_zip,
        transaction_type=transaction_type,
        source=source,
    )
    return result
