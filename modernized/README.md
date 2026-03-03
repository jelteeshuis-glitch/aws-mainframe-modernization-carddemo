# CardDemo Modernized

> Modernized version of the AWS CardDemo mainframe credit card management application.
> Demonstrates migration from COBOL/CICS/VSAM to modern REST APIs, OAuth2 authentication,
> responsive web UI, and real-time fraud detection.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    LEGACY ARCHITECTURE                          │
│                                                                 │
│  3270 Terminal ──► CICS ──► COBOL Programs ──► VSAM Files      │
│  (BMS Screens)     (TP)     (30+ programs)    (8+ KSDS)        │
│                                                                 │
│  JCL Batch Jobs ──► COBOL Batch ──► VSAM Files                 │
│  (Control-M/CA7)    (CBTRN02C etc)                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                    MODERNIZATION
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   MODERN ARCHITECTURE                           │
│                                                                 │
│  Web Browser ──► FastAPI REST API ──► PostgreSQL / In-Memory   │
│  (React SPA)     (Python 3.11+)       (Pydantic models)       │
│                       │                                         │
│                       ├──► OAuth2/JWT Auth (was: plaintext)    │
│                       ├──► Real-time Processing (was: batch)   │
│                       └──► Fraud Detection (NEW capability)    │
└─────────────────────────────────────────────────────────────────┘
```

## Legacy → Modern Mapping

### CICS Transactions → REST API Endpoints

| Legacy Transaction | COBOL Program | BMS Screen | Modern Endpoint | Description |
|---|---|---|---|---|
| CC00 | COSGN00C.cbl | COSGN00.bms | `POST /api/v1/auth/login` | Sign-on (plaintext → OAuth2/JWT) |
| CM00 | COMEN01C.cbl | COMEN01.bms | `GET /dashboard` | Main menu → Dashboard |
| CAVW | COACTVWC.cbl | COACTVW.bms | `GET /api/v1/accounts/{id}` | Account view |
| CAUP | COACTUPC.cbl | COACTUP.bms | `PUT /api/v1/accounts/{id}` | Account update (4237 lines!) |
| CCLI | COCRDLIC.cbl | COCRDLI.bms | `GET /api/v1/accounts` | Credit card list |
| CT00 | COTRN00C.cbl | COTRN00.bms | `GET /api/v1/transactions` | Transaction list |
| CT01 | COTRN01C.cbl | COTRN01.bms | `GET /api/v1/transactions/{id}` | Transaction view |
| CT02 | COTRN02C.cbl | COTRN02.bms | `POST /api/v1/transactions` | Transaction add |
| CB00 | COBIL00C.cbl | COBIL00.bms | `POST /api/v1/transactions/bill-pay` | Bill payment |
| CU00 | COUSR00C.cbl | COUSR00.bms | `GET /api/v1/auth/users` | User list |
| — | — | — | `POST /api/v1/fraud/check` | **NEW: Fraud detection** |

### COBOL Copybooks → Pydantic Models

| Legacy Copybook | Record Size | Modern Model | Key Changes |
|---|---|---|---|
| CSUSR01Y.cpy | 80 bytes | `UserResponse` | Plaintext password → bcrypt hash + JWT |
| CVACT01Y.cpy | 300 bytes | `AccountResponse` | COMP-3 amounts → Decimal, enums for status |
| CVCUS01Y.cpy | 500 bytes | `CustomerResponse` | Full SSN → last 4 only, added email |
| CVTRA05Y.cpy | 350 bytes | `TransactionResponse` | Added fraud_score, fraud_risk_level |
| CVACT03Y.cpy | 50 bytes | Card XREF (internal) | VSAM KSDS → relational foreign keys |

### VSAM Files → Data Store

| Legacy VSAM File | Access Method | Modern Equivalent |
|---|---|---|
| USRSEC | KSDS by User ID | PostgreSQL users table (demo: in-memory dict) |
| ACCTDAT | KSDS by Account ID | PostgreSQL accounts table |
| CUSTDAT | KSDS by Customer ID | PostgreSQL customers table |
| TRANSACT | KSDS by Transaction ID | PostgreSQL transactions table |
| CARDXREF | KSDS by Card Number | PostgreSQL card_xref table |
| CXACAIX | AIX (alternate index) | SQL JOIN / secondary index |

## Key Modernization Highlights

### 1. Authentication: Plaintext → OAuth2/JWT
**Legacy** (COSGN00C.cbl line 223):
```cobol
IF SEC-USR-PWD = WS-USER-PWD    *> Direct plaintext comparison!
```
**Modern** (auth_service.py):
```python
password_hash = hashlib.sha256(password.encode()).hexdigest()  # Production: bcrypt
if password_hash != user["password_hash"]:
    return None
# Returns JWT token with role-based claims
```

### 2. Transaction Processing: Batch → Real-Time
**Legacy** (CBTRN02C.cbl): Processed via nightly JCL job (POSTTRAN.JCL)
**Modern**: Real-time REST API with integrated fraud detection

### 3. Fraud Detection: Nothing → ML-Based Engine
**Legacy** (CBTRN02C.cbl line 377):
```cobol
* ADD MORE VALIDATIONS HERE
```
**Modern** (fraud_service.py): 8-factor risk analysis including velocity checks,
merchant profiling, geographic anomaly detection, and adaptive scoring.

### 4. UI: Green Screen → Modern Web
**Legacy**: 17 BMS screen maps on 24×80 3270 terminals
**Modern**: Responsive React-style web UI with real-time data

## Running Locally

### Backend
```bash
cd modernized/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
- API docs: http://localhost:8000/api/docs
- Health check: http://localhost:8000/api/v1/health

### Frontend
The frontend is served as static files by the FastAPI backend.
Navigate to http://localhost:8000/ after starting the backend.

## Demo Credentials

| Username | Password | Role | MFA |
|---|---|---|---|
| admin001 | SecureP@ss1! | Admin | Enabled |
| user0001 | SecureP@ss2! | User | Disabled |

## Demo Flow (Recommended for ING)

1. **Sign-On** → Show legacy BMS screen vs modern OAuth2 login
2. **Dashboard** → Show legacy main menu vs modern dashboard with real-time data
3. **Transactions** → Post a transaction, show real-time fraud detection
4. **Fraud Detection** → Try different scenarios (normal, crypto, high amount)
5. **Bill Payment** → Process payment, show balance update
6. **API Docs** → Show auto-generated OpenAPI documentation at `/api/docs`
