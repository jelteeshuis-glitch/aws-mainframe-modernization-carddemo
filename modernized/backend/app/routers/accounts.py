"""
Account & Customer Router - REST API replacing CICS online programs

Legacy endpoints (CICS):
  CAVW -> COACTVWC -> Account View
  CAUP -> COACTUPC -> Account Update
  CCLI -> COCRDLIC -> Credit Card List
  CCDL -> COCRDSLC -> Credit Card View

Modernized endpoints:
  GET /api/v1/accounts             -> List accounts
  GET /api/v1/accounts/{id}        -> View account detail
  GET /api/v1/customers            -> List customers
  GET /api/v1/customers/{id}       -> View customer detail
"""

from fastapi import APIRouter, HTTPException

from ..services.transaction_service import (
    get_account_by_id,
    get_accounts,
    get_customer_by_id,
    get_customers,
)

router = APIRouter(prefix="/api/v1", tags=["Accounts & Customers"])


@router.get("/accounts", summary="List accounts - replaces CAVW CICS transaction")
async def list_accounts():
    """
    List all accounts with summary info.

    Replaces COACTVWC.cbl which displayed account details on a CICS BMS
    screen (COACTVW map). The legacy screen could only show one account
    at a time, requiring the user to enter an account ID.

    The modern API returns all accounts in a single response with
    customer name joined from the customer file.
    """
    return get_accounts()


@router.get("/accounts/{account_id}", summary="View account - replaces CAVW CICS transaction")
async def view_account(account_id: int):
    """
    View account details with full customer profile.

    Replaces COACTVWC.cbl + COACTUPC.cbl (4237 lines of COBOL!)
    The legacy COACTUPC.cbl is the largest program in CardDemo at 4237 lines,
    handling both display and update with complex state management via
    ACUP-CHANGE-ACTION flags and WS-THIS-PROGCOMMAREA.

    The modern API separates read and write into distinct endpoints.
    """
    account = get_account_by_id(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.get("/customers", summary="List customers")
async def list_all_customers():
    """List all customers with their details."""
    return get_customers()


@router.get("/customers/{customer_id}", summary="View customer detail")
async def view_customer(customer_id: int):
    """View detailed customer profile."""
    customer = get_customer_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer
