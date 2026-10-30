from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Request
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def utcnow():
    return datetime.now(timezone.utc)


def aware(value: datetime):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def new_id(prefix: str):
    return f"{prefix}_{uuid4().hex}"


class Base(DeclarativeBase):
    pass


def make_engine(url: str):
    kwargs = {"connect_args": {"check_same_thread": False, "timeout": 15}} if url.startswith("sqlite:") else {}
    engine = create_engine(url, pool_pre_ping=True, **kwargs)
    if url.startswith("sqlite:"):
        @event.listens_for(engine, "connect")
        def sqlite_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
    return engine


def make_session_factory(engine):
    return sessionmaker(engine, expire_on_commit=False)


def get_db(request: Request):
    with request.app.state.sessions() as db:
        yield db
