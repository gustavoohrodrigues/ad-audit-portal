"""Engine SQLAlchemy síncrono para as tarefas Celery."""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import config

engine = create_engine(config.database_url_sync, pool_pre_ping=True, future=True)
SessionFactory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


@contextmanager
def session_scope():
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
