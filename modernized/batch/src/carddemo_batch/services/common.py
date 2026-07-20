"""Shared helpers for the batch services."""

from __future__ import annotations

from datetime import datetime, timezone

# Validation reject reason codes / descriptions, identical to CBTRN02C.
REJECT_INVALID_CARD = (100, "INVALID CARD NUMBER FOUND")
REJECT_ACCT_NOT_FOUND = (101, "ACCOUNT RECORD NOT FOUND")
REJECT_OVERLIMIT = (102, "OVERLIMIT TRANSACTION")
REJECT_EXPIRED = (103, "TRANSACTION RECEIVED AFTER ACCT EXPIRATION")


def db2_timestamp(now: datetime | None = None) -> str:
    """Return a 26-char DB2-style timestamp ``YYYY-MM-DD-HH.MM.SS.mmmmmm``.

    Equivalent to the ``Z-GET-DB2-FORMAT-TIMESTAMP`` routine used by CBTRN02C/CBACT04C
    to stamp ``TRAN-PROC-TS``.
    """
    now = now or datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d-%H.%M.%S.%f")
