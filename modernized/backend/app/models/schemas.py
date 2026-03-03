"""
Modernized Data Models - Replacing COBOL Copybooks with Pydantic/SQLAlchemy Models

Mapping from legacy VSAM copybooks:
  CSUSR01Y.cpy  -> User (SEC-USER-DATA)
  CVACT01Y.cpy  -> Account (ACCOUNT-RECORD, 300 bytes)
  CVCUS01Y.cpy  -> Customer (CUSTOMER-RECORD, 500 bytes)
  CVTRA05Y.cpy  -> Transaction (TRAN-RECORD, 350 bytes)
  CVACT03Y.cpy  -> CardXref (CARD-XREF-RECORD)
  CVACT02Y.cpy  -> CreditCard (CARD-RECORD)
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, EmailStr


# --- Enums ---

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"


class AccountStatus(str, Enum):
    ACTIVE = "Y"
    INACTIVE = "N"


class TransactionType(str, Enum):
    PURCHASE = "01"
    PAYMENT = "02"
    CASH_ADVANCE = "03"
    REFUND = "04"
    FEE = "05"


class TransactionSource(str, Enum):
    ONLINE = "ONLINE"
    POS_TERMINAL = "POS TERM"
    ATM = "ATM"
    MOBILE = "MOBILE"
    BATCH = "BATCH"


class FraudRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# --- User Models (replaces CSUSR01Y.cpy / SEC-USER-DATA) ---
# Legacy: 8-char ID, 20-char first/last name, 8-char plaintext password, 1-char type

class UserBase(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    email: Optional[EmailStr] = None
    role: UserRole = UserRole.USER


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128,
                          description="Hashed with bcrypt, not stored as plaintext like legacy VSAM")


class UserResponse(UserBase):
    id: int
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool = True
    mfa_enabled: bool = False

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    refresh_token: Optional[str] = None
    user: UserResponse


# --- Customer Models (replaces CVCUS01Y.cpy / CUSTOMER-RECORD, 500 bytes) ---
# Legacy: 9-digit ID, fixed-length char fields, SSN as 9-digit numeric

class CustomerBase(BaseModel):
    first_name: str = Field(..., max_length=50)
    middle_name: Optional[str] = Field(None, max_length=50)
    last_name: str = Field(..., max_length=50)
    address_line_1: str = Field(..., max_length=100)
    address_line_2: Optional[str] = Field(None, max_length=100)
    address_line_3: Optional[str] = Field(None, max_length=100)
    state_code: str = Field(..., max_length=10)
    country_code: str = Field(..., max_length=10)
    zip_code: str = Field(..., max_length=20)
    phone_primary: Optional[str] = Field(None, max_length=20)
    phone_secondary: Optional[str] = Field(None, max_length=20)
    ssn_last_four: Optional[str] = Field(None, max_length=4,
                                          description="Only last 4 digits stored - unlike legacy which stored full SSN")
    government_id: Optional[str] = Field(None, max_length=50)
    date_of_birth: Optional[date] = None
    eft_account_id: Optional[str] = Field(None, max_length=20)
    is_primary_cardholder: bool = True
    fico_credit_score: Optional[int] = Field(None, ge=300, le=850)
    email: Optional[EmailStr] = None


class CustomerResponse(CustomerBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Account Models (replaces CVACT01Y.cpy / ACCOUNT-RECORD, 300 bytes) ---
# Legacy: 11-digit ID, S9(10)V99 for monetary fields, X(10) for dates

class AccountBase(BaseModel):
    status: AccountStatus = AccountStatus.ACTIVE
    current_balance: Decimal = Field(default=Decimal("0.00"), decimal_places=2)
    credit_limit: Decimal = Field(..., decimal_places=2)
    cash_credit_limit: Decimal = Field(..., decimal_places=2)
    open_date: date
    expiration_date: date
    reissue_date: Optional[date] = None
    current_cycle_credit: Decimal = Field(default=Decimal("0.00"), decimal_places=2)
    current_cycle_debit: Decimal = Field(default=Decimal("0.00"), decimal_places=2)
    zip_code: Optional[str] = Field(None, max_length=20)
    group_id: Optional[str] = Field(None, max_length=20)


class AccountResponse(AccountBase):
    id: int
    customer_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Transaction Models (replaces CVTRA05Y.cpy / TRAN-RECORD, 350 bytes) ---
# Legacy: X(16) ID, X(02) type code, 9(04) category, S9(09)V99 amount

class TransactionCreate(BaseModel):
    card_number: str = Field(..., min_length=16, max_length=16)
    transaction_type: TransactionType
    category_code: int = Field(..., ge=0, le=9999)
    source: TransactionSource
    description: str = Field(..., max_length=200)
    amount: Decimal = Field(..., decimal_places=2)
    merchant_id: Optional[int] = None
    merchant_name: Optional[str] = Field(None, max_length=100)
    merchant_city: Optional[str] = Field(None, max_length=100)
    merchant_zip: Optional[str] = Field(None, max_length=20)


class TransactionResponse(BaseModel):
    id: str
    transaction_type: TransactionType
    category_code: int
    source: TransactionSource
    description: str
    amount: Decimal
    card_number: str
    merchant_id: Optional[int] = None
    merchant_name: Optional[str] = None
    merchant_city: Optional[str] = None
    merchant_zip: Optional[str] = None
    originated_at: datetime
    processed_at: datetime
    account_id: int
    customer_id: int
    fraud_score: Optional[float] = None
    fraud_risk_level: Optional[FraudRiskLevel] = None
    fraud_flags: Optional[list[str]] = None

    class Config:
        from_attributes = True


class TransactionListResponse(BaseModel):
    transactions: list[TransactionResponse]
    total_count: int
    page: int = 1
    page_size: int = 20


# --- Fraud Detection Models (NEW - not in legacy) ---

class FraudCheckRequest(BaseModel):
    card_number: str
    amount: Decimal
    merchant_name: Optional[str] = None
    merchant_city: Optional[str] = None
    merchant_zip: Optional[str] = None
    transaction_type: TransactionType
    source: TransactionSource


class FraudCheckResponse(BaseModel):
    risk_score: float = Field(..., ge=0.0, le=1.0,
                               description="0.0 = no risk, 1.0 = certain fraud")
    risk_level: FraudRiskLevel
    flags: list[str] = Field(default_factory=list)
    recommendation: str
    details: dict = Field(default_factory=dict)
    checked_at: datetime


# --- Bill Payment Models (replaces COBIL00C.cbl logic) ---

class BillPaymentRequest(BaseModel):
    account_id: int
    amount: Optional[Decimal] = Field(None, description="If None, pays full balance")
    confirm: bool = False


class BillPaymentResponse(BaseModel):
    transaction_id: str
    account_id: int
    amount_paid: Decimal
    previous_balance: Decimal
    new_balance: Decimal
    payment_date: datetime
    confirmation_number: str


# --- Statement Models (replaces CBSTM03A.CBL) ---

class StatementRequest(BaseModel):
    account_id: int
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    format: str = Field(default="json", pattern="^(json|pdf|html)$")


class StatementResponse(BaseModel):
    account_id: int
    customer_name: str
    address: str
    current_balance: Decimal
    fico_score: Optional[int] = None
    transactions: list[TransactionResponse]
    total_charges: Decimal
    total_payments: Decimal
    statement_date: datetime
    period_start: date
    period_end: date


# --- Health / Info Models ---

class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "2.0.0"
    legacy_version: str = "CardDemo_v1.0"
    modernization_status: str = "Phase 1 - API Extraction & UI Modernization"
    components: dict = Field(default_factory=lambda: {
        "authentication": "OAuth2/JWT (was: VSAM plaintext)",
        "data_store": "PostgreSQL (was: VSAM KSDS)",
        "transaction_processing": "REST API (was: CICS/Batch COBOL)",
        "fraud_detection": "ML-based real-time (NEW)",
        "ui": "Modern Web SPA (was: BMS 3270 screens)",
        "batch_orchestration": "Event-driven (was: JCL/Control-M)",
    })
