from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, load_settings


def build_engine(database_url: str, *, echo: bool = False) -> Engine:
    options = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, echo=echo, pool_pre_ping=True, connect_args=options)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def session_dependency(settings: Settings | None = None) -> Iterator[Session]:
    engine = build_engine((settings or load_settings()).database_url)
    with build_session_factory(engine)() as session:
        yield session
