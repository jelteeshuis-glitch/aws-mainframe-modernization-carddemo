"""Runtime configuration for the batch services (all overridable via environment)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path


def database_url() -> str:
    """Return the SQLAlchemy database URL.

    Priority:
      1. ``DATABASE_URL`` if set (e.g. ``postgresql+psycopg2://user:pw@host/db``).
      2. Assembled from ``PG*`` environment variables (Docker / Step Functions default).
    """
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    host = os.environ.get("PGHOST", "localhost")
    port = os.environ.get("PGPORT", "5432")
    user = os.environ.get("PGUSER", "carddemo")
    password = os.environ.get("PGPASSWORD", "carddemo")
    db = os.environ.get("PGDATABASE", "carddemo")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


def data_dir() -> Path:
    """Directory holding the fixed-width source data files (``app/data/ASCII``)."""
    env = os.environ.get("CARDDEMO_DATA_DIR")
    if env:
        return Path(env)
    # Default: repository ``app/data/ASCII`` relative to this file.
    return Path(__file__).resolve().parents[4] / "app" / "data" / "ASCII"


def output_dir() -> Path:
    """Directory where CREASTMT statements and TRANREPT reports are written."""
    return Path(os.environ.get("CARDDEMO_OUTPUT_DIR", "output"))


def interest_parm_date() -> str:
    """The INTCALC run date used to build generated interest transaction ids.

    Mirrors the JCL ``PARM='2022071800'`` of ``INTCALC.jcl``.
    """
    return os.environ.get("CARDDEMO_PARM_DATE", "2022071800")


def report_date_range() -> tuple[str, str]:
    """Start/end ``YYYY-MM-DD`` dates for TRANREPT (was the DATEPARM file).

    Defaults to the current UTC date so the report covers the transactions processed by
    the current pipeline run (their ``proc_ts`` is stamped at posting time). Override with
    ``CARDDEMO_REPORT_START`` / ``CARDDEMO_REPORT_END``.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start = os.environ.get("CARDDEMO_REPORT_START", today)
    end = os.environ.get("CARDDEMO_REPORT_END", today)
    return start, end
