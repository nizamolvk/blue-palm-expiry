from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from task2_api.config import database_url


class Base(DeclarativeBase):
    pass


def make_engine(url: str | None = None):
    url = database_url() if url is None else url
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        if url in {"sqlite://", "sqlite:///:memory:"}:
            return create_engine(url, connect_args=connect_args, poolclass=StaticPool)
        return create_engine(url, connect_args=connect_args)
    return create_engine(url)


def make_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)
