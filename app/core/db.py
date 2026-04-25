"""Database engine and connection helpers."""

from __future__ import annotations

from functools import lru_cache
from typing import Iterator

from sqlalchemy import Engine, create_engine

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Create the shared SQLAlchemy engine with production-safe pooling."""

    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
    )


def connection() -> Iterator[object]:
    """Yield a checked-out SQLAlchemy connection."""

    with get_engine().connect() as conn:
        yield conn

