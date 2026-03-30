from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base


def build_engine(database_url: str):
    engine_kwargs: dict = {"future": True, "pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in database_url or database_url.endswith("://"):
            engine_kwargs["poolclass"] = StaticPool
    return create_engine(database_url, **engine_kwargs)


def build_session_factory(engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_database(engine) -> None:
    import app.db.models  # noqa: F401

    Base.metadata.create_all(bind=engine)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]):
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

