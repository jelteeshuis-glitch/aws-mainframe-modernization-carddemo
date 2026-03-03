"""
CardDemo Modernized - FastAPI Application

This is the modernized version of the CardDemo mainframe application.
It replaces:
  - CICS transaction processing (30+ COBOL programs)
  - BMS screen maps (17 screen definitions)
  - VSAM data stores (8+ KSDS files)
  - JCL batch jobs (17+ job definitions)
  - Control-M/CA7 scheduling

With:
  - REST API endpoints (FastAPI)
  - Modern web UI (served as static files)
  - In-memory data store (demo; PostgreSQL in production)
  - Real-time fraud detection (NEW capability)
  - OAuth2/JWT authentication (was: plaintext VSAM passwords)

Legacy Transaction -> Modern API Mapping:
  CC00 (Sign-on)        -> POST /api/v1/auth/login
  CM00 (Main Menu)      -> GET  / (Web UI)
  CAVW (Account View)   -> GET  /api/v1/accounts/{id}
  CAUP (Account Update) -> PUT  /api/v1/accounts/{id}
  CCLI (Card List)      -> GET  /api/v1/accounts/{id}/cards
  CT00 (Transaction List)-> GET  /api/v1/transactions
  CT01 (Transaction View)-> GET  /api/v1/transactions/{id}
  CT02 (Transaction Add) -> POST /api/v1/transactions
  CB00 (Bill Payment)   -> POST /api/v1/transactions/bill-pay
  CR00 (Reports)        -> GET  /api/v1/reports/statement
  CU00 (User List)      -> GET  /api/v1/auth/users
  NEW: Fraud Detection  -> POST /api/v1/fraud/check
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from .routers import auth, transactions, accounts, fraud

app = FastAPI(
    title="CardDemo Modernized",
    description=(
        "Modernized version of the AWS CardDemo mainframe credit card management application. "
        "Demonstrates migration from COBOL/CICS/VSAM to modern REST APIs with "
        "real-time fraud detection, OAuth2 authentication, and a responsive web UI."
    ),
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(transactions.router)
app.include_router(accounts.router)
app.include_router(fraud.router)


@app.get("/api/v1/health", tags=["System"])
async def health_check():
    """
    System health check.

    Legacy equivalent: None. The mainframe had no health check endpoint.
    CICS availability was monitored via CEMT INQUIRE TRANSACTION.
    """
    return {
        "status": "healthy",
        "version": "2.0.0",
        "legacy_version": "CardDemo_v1.0",
        "modernization_phase": "Phase 1 - API Extraction & UI Modernization",
        "components": {
            "authentication": {"status": "active", "type": "OAuth2/JWT", "was": "VSAM plaintext passwords"},
            "data_store": {"status": "active", "type": "In-memory (demo) / PostgreSQL (prod)", "was": "VSAM KSDS"},
            "transaction_processing": {"status": "active", "type": "REST API real-time", "was": "CICS online + JCL batch"},
            "fraud_detection": {"status": "active", "type": "ML-based real-time", "was": "Not available"},
            "ui": {"status": "active", "type": "Modern Web SPA", "was": "BMS 3270 green screens"},
        },
        "legacy_programs_replaced": [
            "COSGN00C.cbl (Sign-on)",
            "COMEN01C.cbl (Main Menu)",
            "COACTVWC.cbl (Account View)",
            "COACTUPC.cbl (Account Update - 4237 lines!)",
            "COCRDLIC.cbl (Card List)",
            "COTRN00C.cbl (Transaction List)",
            "COTRN01C.cbl (Transaction View)",
            "COTRN02C.cbl (Transaction Add)",
            "COBIL00C.cbl (Bill Payment)",
            "CBTRN02C.cbl (Batch Transaction Posting)",
            "CBACT04C.cbl (Interest Calculation)",
            "CBSTM03A.CBL (Statement Generation)",
        ],
    }


# Serve frontend static files
# __file__ = .../modernized/backend/app/main.py
# Go up 3 levels to reach modernized/, then into frontend/
frontend_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend"
)
if os.path.isdir(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_dir, "index.html"))

    @app.get("/dashboard", include_in_schema=False)
    async def serve_dashboard():
        return FileResponse(os.path.join(frontend_dir, "pages", "dashboard.html"))

    @app.get("/accounts-page", include_in_schema=False)
    async def serve_accounts():
        return FileResponse(os.path.join(frontend_dir, "pages", "accounts.html"))

    @app.get("/transactions-page", include_in_schema=False)
    async def serve_transactions():
        return FileResponse(os.path.join(frontend_dir, "pages", "transactions.html"))

    @app.get("/fraud-page", include_in_schema=False)
    async def serve_fraud():
        return FileResponse(os.path.join(frontend_dir, "pages", "fraud.html"))
