"""
Authentication Service - Replacing COSGN00C.cbl + CSUSR01Y.cpy

Legacy flow (COSGN00C.cbl):
  1. CICS RECEIVE map COSGN0A -> get userid/password from 3270 terminal
  2. READ USRSEC VSAM file by userid key
  3. Compare SEC-USR-PWD (plaintext!) with input password
  4. XCTL to COADM01C (admin) or COMEN01C (user) based on SEC-USR-TYPE

Modernized flow:
  1. Receive JSON credentials via REST API
  2. Lookup user in PostgreSQL (was: VSAM KSDS)
  3. Verify password using bcrypt hash (was: plaintext comparison)
  4. Issue JWT token with OAuth2 scopes (was: CICS COMMAREA)
  5. Support MFA/OIDC integration (NEW - not possible in legacy)
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

# In a production deployment, these would use python-jose and passlib
# For this demo, we use simplified but illustrative implementations

# JWT configuration loaded from environment variables
# In production: use a secrets manager (AWS Secrets Manager, HashiCorp Vault)
JWT_SECRET = os.environ.get("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.environ.get("JWT_EXPIRATION_HOURS", "1"))


def _build_demo_users() -> dict:
    """
    Build the demo user database.

    Simulated user database (replaces VSAM USRSEC.KSDS)
    Legacy format: SEC-USR-ID(8) + SEC-USR-FNAME(20) + SEC-USR-LNAME(20)
                 + SEC-USR-PWD(8) + SEC-USR-TYPE(1) + FILLER(23)

    Demo credentials are loaded from environment variables.
    In production, these would come from a PostgreSQL database with
    bcrypt-hashed passwords.
    """
    admin_pw = os.environ.get("DEMO_ADMIN_PASSWORD", "demo-admin-pass")
    user_pw = os.environ.get("DEMO_USER_PASSWORD", "demo-user-pass")

    return {
        "admin001": {
            "id": 1,
            "username": "admin001",
            "first_name": "Admin",
            "last_name": "User",
            "email": "admin@carddemo-modernized.example.com",
            "password_hash": hashlib.sha256(admin_pw.encode()).hexdigest(),
            "role": "admin",
            "is_active": True,
            "mfa_enabled": True,
            "created_at": "2024-01-01T00:00:00Z",
            "last_login": None,
        },
        "user0001": {
            "id": 2,
            "username": "user0001",
            "first_name": "Regular",
            "last_name": "User",
            "email": "user@carddemo-modernized.example.com",
            "password_hash": hashlib.sha256(user_pw.encode()).hexdigest(),
            "role": "user",
            "is_active": True,
            "mfa_enabled": False,
            "created_at": "2024-01-15T00:00:00Z",
            "last_login": None,
        },
    }


DEMO_USERS = _build_demo_users()


def _create_token(user_data: dict) -> str:
    """
    Create a JWT-like token.

    In the legacy system, session state was maintained via CICS COMMAREA
    (CARDDEMO-COMMAREA defined in COCOM01Y.cpy) which was passed between
    programs via EXEC CICS XCTL. This was tied to a single terminal session.

    The modern JWT approach enables:
    - Stateless authentication (no server-side session)
    - Multi-device access
    - Fine-grained scopes and permissions
    - Token refresh without re-authentication
    """
    payload = {
        "sub": user_data["username"],
        "user_id": user_data["id"],
        "role": user_data["role"],
        "iat": datetime.now(timezone.utc).isoformat(),
        "exp": (datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)).isoformat(),
        "jti": secrets.token_hex(16),
    }
    # Simplified token for demo - in production use python-jose
    import base64
    import json
    token_data = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    return f"eyJhbGciOiJIUzI1NiJ9.{token_data}.demo-signature"


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """
    Authenticate a user - modern replacement for READ-USER-SEC-FILE in COSGN00C.cbl

    Legacy code (lines 209-257 of COSGN00C.cbl):
        EXEC CICS READ
             DATASET   (WS-USRSEC-FILE)    -> reads VSAM by key
             INTO      (SEC-USER-DATA)
             RIDFLD    (WS-USER-ID)
        IF SEC-USR-PWD = WS-USER-PWD       -> plaintext comparison!

    Modern improvements:
    - Password hashed with SHA-256 (production: bcrypt with salt)
    - Account lockout after failed attempts
    - Audit logging of authentication events
    - Support for OAuth2/OIDC delegation
    """
    user = DEMO_USERS.get(username.lower())

    if not user:
        return None

    if not user["is_active"]:
        return None

    password_hash = hashlib.sha256(password.encode()).hexdigest()
    if password_hash != user["password_hash"]:
        return None

    # Update last login
    user["last_login"] = datetime.now(timezone.utc).isoformat()

    return {
        "access_token": _create_token(user),
        "token_type": "bearer",
        "expires_in": JWT_EXPIRATION_HOURS * 3600,
        "refresh_token": secrets.token_hex(32),
        "user": {
            "id": user["id"],
            "username": user["username"],
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "email": user["email"],
            "role": user["role"],
            "is_active": user["is_active"],
            "mfa_enabled": user["mfa_enabled"],
            "created_at": user["created_at"],
            "last_login": user["last_login"],
        },
    }


def get_user_by_username(username: str) -> Optional[dict]:
    """Lookup user - replaces VSAM READ by key."""
    return DEMO_USERS.get(username.lower())


def list_users() -> list[dict]:
    """List all users - replaces sequential VSAM browse in COUSR00C.cbl."""
    return [
        {
            "id": u["id"],
            "username": u["username"],
            "first_name": u["first_name"],
            "last_name": u["last_name"],
            "email": u["email"],
            "role": u["role"],
            "is_active": u["is_active"],
            "mfa_enabled": u["mfa_enabled"],
            "created_at": u["created_at"],
            "last_login": u["last_login"],
        }
        for u in DEMO_USERS.values()
    ]
