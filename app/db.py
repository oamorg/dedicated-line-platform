import os
from pathlib import Path
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://dedicated_line@127.0.0.1:3306/dedicated_line?charset=utf8mb4",
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
