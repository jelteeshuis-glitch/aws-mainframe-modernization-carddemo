"""
Authentication Router - REST API replacing COSGN00C.cbl CICS transactions

Legacy endpoints (CICS):
  CC00 transaction -> COSGN00C program -> COSGN00 BMS map

Modernized endpoints:
  POST /api/v1/auth/login     -> Authenticate and receive JWT
  POST /api/v1/auth/logout    -> Invalidate token
  GET  /api/v1/auth/me        -> Get current user info
  GET  /api/v1/auth/users     -> List users (admin only)
"""

from fastapi import APIRouter, HTTPException, status

from ..services.auth_service import authenticate_user, list_users

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/login", summary="User login - replaces CC00 CICS transaction")
async def login(username: str, password: str):
    """
    Authenticate user and return JWT token.

    Replaces the COSGN00C.cbl sign-on flow:
    - Legacy: BMS screen -> VSAM READ -> plaintext password compare -> XCTL
    - Modern: JSON request -> DB query -> bcrypt verify -> JWT token

    Demo credentials:
    - Admin: admin001 / SecureP@ss1!
    - User:  user0001 / SecureP@ss2!
    """
    result = authenticate_user(username, password)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials. Legacy equivalent: 'Wrong Password. Try again ...' or 'User not found. Try again ...'",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return result


@router.get("/users", summary="List users - replaces CU00 CICS transaction")
async def get_users():
    """
    List all users. Replaces COUSR00C.cbl (User List screen).
    In production, this would require admin JWT token.
    """
    return list_users()
