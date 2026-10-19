"""Database engine/session. Production target is PostgreSQL via DATABASE_URL.

If DATABASE_URL is unset, a local SQLite file is used so the app still starts
for development; this is logged, and is NOT the supported deployment target.
"""
import logging
import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        logger.warning("DATABASE_URL not set; using local SQLite dev database (not for production).")
        return "sqlite:///./snaptix_dev.db"
    return url


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        url = database_url()
        kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True}
        _engine = create_engine(url, **kwargs)
        _enable_sqlite_fk(_engine)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def _enable_sqlite_fk(engine: Engine) -> None:
    """Enforce FKs/cascades on SQLite the way PostgreSQL always does."""
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")


def set_engine(engine: Engine) -> None:
    """Test hook: use a specific engine."""
    global _engine, _SessionLocal
    _enable_sqlite_fk(engine)
    _engine = engine
    _SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def new_session() -> Session:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal()


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request; commit is explicit in services."""
    db = new_session()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    db = new_session()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
