"""Shared pytest fixtures: an isolated in-memory SQLite database per test."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from carddemo_batch.db import create_schema

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "app" / "data" / "ASCII"


@pytest.fixture
def session() -> Iterator[Session]:
    """A committed-capable Session on a fresh in-memory SQLite database.

    StaticPool keeps the single in-memory connection alive across the whole test so the
    schema and data persist between service calls.
    """
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    create_schema(engine)
    sess = Session(engine, expire_on_commit=False)
    try:
        yield sess
    finally:
        sess.close()
        engine.dispose()


@pytest.fixture
def data_dir() -> Path:
    return DATA_DIR
