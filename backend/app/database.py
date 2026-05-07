from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

DB_PATH = Path(__file__).resolve().parent.parent / "honorarios.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Users ─────────────────────────────────────────────────────────

class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    azure_id = Column(String(128), unique=True, nullable=False, index=True)
    email = Column(String(256), unique=True, nullable=False, index=True)
    name = Column(String(256), nullable=False, default="")
    role = Column(String(32), nullable=False, default="advogado")  # advogado | admin
    created_at = Column(DateTime, nullable=False, default=utcnow)


# ── Contracts ─────────────────────────────────────────────────────

class ContractDB(Base):
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(String(64), unique=True, nullable=False, index=True)
    status = Column(String(32), nullable=False, default="rascunho")
    client_name = Column(String(256), nullable=False, default="")
    client_email = Column(String(256), nullable=False, default="")
    current_version = Column(Integer, nullable=False, default=1)
    created_by = Column(String(256), nullable=True)  # user email
    updated_by = Column(String(256), nullable=True)  # user email
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    versions = relationship(
        "ContractVersionDB", back_populates="contract", order_by="ContractVersionDB.version_number"
    )
    audit_logs = relationship(
        "AuditLogDB", back_populates="contract", order_by="AuditLogDB.created_at.desc()"
    )


class ContractVersionDB(Base):
    __tablename__ = "contract_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(String(64), ForeignKey("contracts.contract_id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False, default=1)
    form_data_json = Column(Text, nullable=False)
    file_path = Column(String(512), nullable=True)
    docuseal_submission_id = Column(String(128), nullable=True)
    created_by = Column(String(256), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    contract = relationship("ContractDB", back_populates="versions")


class AuditLogDB(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(String(64), ForeignKey("contracts.contract_id"), nullable=False, index=True)
    action = Column(String(64), nullable=False)
    detail = Column(Text, nullable=True)
    version_number = Column(Integer, nullable=True)
    user_email = Column(String(256), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    contract = relationship("ContractDB", back_populates="audit_logs")


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
