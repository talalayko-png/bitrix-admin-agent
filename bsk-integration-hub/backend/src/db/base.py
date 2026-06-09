"""SQLAlchemy engine / session management.

Engine and sessionmaker are created lazily so tests can point DATABASE_URL at a
temporary database before anything connects. ``reset_engine`` disposes the
current engine (used by the test fixtures).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.config import get_settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _make_engine(url: str) -> Engine:
    connect_args: dict = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        # ensure the directory for a file-based sqlite db exists
        prefix = "sqlite:///"
        if url.startswith(prefix):
            path = url[len(prefix):]
            if path and path != ":memory:":
                directory = os.path.dirname(path)
                if directory:
                    os.makedirs(directory, exist_ok=True)
    return create_engine(url, future=True, pool_pre_ping=True, connect_args=connect_args)


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = _make_engine(get_settings().database_url)
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            expire_on_commit=False,
            future=True,
        )
    return _SessionLocal


def reset_engine() -> None:
    """Dispose the engine and clear cached session factory (tests)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session context: commit on success, rollback on error."""
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create all tables (MVP — Alembic migrations are on the roadmap)."""
    from src.db import models  # noqa: F401  (register mappers)

    Base.metadata.create_all(bind=get_engine())
