"""Database engine / session helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from . import config
from .models import Base


def make_engine(url: str | None = None, echo: bool = False) -> Engine:
    """Create a SQLAlchemy engine for ``url`` (defaults to the configured database)."""
    return create_engine(url or config.database_url(), echo=echo, future=True)


def create_schema(engine: Engine) -> None:
    """Create all tables (idempotent). Used by tests and the loader bootstrap."""
    Base.metadata.create_all(engine)


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """Transactional session scope: commit on success, roll back on error."""
    factory = session_factory(engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
