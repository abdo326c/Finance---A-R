# models.py
# ─────────────────────────────────────────────
# SQLAlchemy ORM models + DB engine + helpers
# All DB indexes are declared here.
# ─────────────────────────────────────────────
import streamlit as st
from sqlalchemy import (
    create_engine, Column, Integer, String, Float,
    ForeignKey, DateTime, Date, Boolean, LargeBinary, Index, text
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
from contextlib import contextmanager

DB_URL = st.secrets.get("DB_URL", "sqlite:///finance.db")


# ── Engine ────────────────────────────────────
@st.cache_resource
def get_db_engine():
    if "sqlite" in DB_URL:
        return create_engine(DB_URL, connect_args={"check_same_thread": False})
    return create_engine(DB_URL, pool_size=10, max_overflow=20, pool_pre_ping=True)

engine       = get_db_engine()
Base         = declarative_base()
SessionLocal = sessionmaker(bind=engine)


@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Models ────────────────────────────────────
class SystemUser(Base):
    __tablename__ = "system_users"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    username      = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)   # bcrypt hash
    role          = Column(String, nullable=False, default="Editor")
    is_active     = Column(Boolean, default=True)


class Student(Base):
    __tablename__ = "students"
    id            = Column(Integer, primary_key=True)
    name          = Column(String)
    college       = Column(String)
    program       = Column(String)
    birth_date    = Column(Date)
    email         = Column(String)
    mobile        = Column(String)
    national_id   = Column(String)
    nationality   = Column(String)
    admit_year    = Column(Integer)
    price_per_hr  = Column(Float)
    financial_dimension = Column(String, nullable=True)
    
    # 🟢 التعديلات الجديدة في الـ Master Data للطالب
    is_sponsored  = Column(Boolean, default=False)
    sponsor_name  = Column(String, nullable=True)
    general_notes = Column(String, nullable=True)
    sibling_id    = Column(Integer, ForeignKey("students.id"), nullable=True)


class ScholarshipType(Base):
    __tablename__ = "scholarship_types"
    id   = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True)


class StudentScholarship(Base):
    __tablename__ = "student_scholarships"
    id                 = Column(Integer, primary_key=True, autoincrement=True)
    student_id         = Column(Integer, ForeignKey("students.id"), nullable=False)
    scholarship_type_id= Column(Integer, ForeignKey("scholarship_types.id"), nullable=False)
    # Always stored as 0–100 (percentage points, NOT a decimal fraction)
    percentage         = Column(Float, nullable=False)
    term               = Column(String, nullable=False, default="Spring")
    academic_year      = Column(Integer, nullable=False)
    is_active          = Column(Boolean, default=True)


class StudentStatus(Base):
    __tablename__ = "student_statuses"
    id           = Column(Integer, primary_key=True, autoincrement=True)
    student_id   = Column(Integer, ForeignKey("students.id"), nullable=False)
    term         = Column(String, nullable=False)
    academic_year= Column(Integer, nullable=False)
    status       = Column(String, nullable=False)


class Transaction(Base):
    __tablename__ = "transactions"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    reference_no     = Column(String, unique=True)
    batch_id         = Column(String, nullable=True)
    student_id       = Column(Integer, ForeignKey("students.id"))
    scholarship_type_id = Column(Integer, ForeignKey("scholarship_types.id"), nullable=True)
    transaction_type = Column(String, nullable=False)
    description      = Column(String)
    
    # 🟢 حقل الـ Internal Note (للملاحظات المخفية عن الطالب في الـ PDF)
    internal_note    = Column(String, nullable=True)
    
    hours_change     = Column(Float, default=0.0)
    debit            = Column(Float, default=0)
    credit           = Column(Float, default=0)
    entry_date       = Column(Date, nullable=False)
    term             = Column(String, nullable=False)
    academic_year    = Column(Integer, nullable=False)
    created_at       = Column(DateTime, server_default=func.now())


class RefCounter(Base):
    """Single-row counter that replaces the slow full-table scan."""
    __tablename__ = "ref_counter"
    id  = Column(Integer, primary_key=True, default=1)
    seq = Column(Integer, default=0, nullable=False)


class DeletedBatchLog(Base):
    __tablename__ = "deleted_batch_logs"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    batch_id         = Column(String, nullable=False)
    transaction_type = Column(String)
    record_count     = Column(Integer)
    total_debit      = Column(Float)
    total_credit     = Column(Float)
    deleted_by       = Column(String)
    deleted_at       = Column(DateTime, server_default=func.now())


class PolicyDocument(Base):
    __tablename__ = "policy_documents"
    id           = Column(Integer, primary_key=True, autoincrement=True)
    title        = Column(String, nullable=False)
    academic_year= Column(String, nullable=False)
    file_name    = Column(String, nullable=False)
    file_data    = Column(LargeBinary, nullable=False)
    uploaded_by  = Column(String)
    uploaded_at  = Column(DateTime, server_default=func.now())


class AuditLog(Base):
    """Immutable record of every write operation."""
    __tablename__ = "audit_logs"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    username   = Column(String, nullable=False)
    action     = Column(String, nullable=False)   # e.g. "POST_PAYMENT"
    target     = Column(String)                   # e.g. "student_id=26100123"
    detail     = Column(String)                   # free-text summary
    created_at = Column(DateTime, server_default=func.now())


class SystemConfig(Base):
    __tablename__ = "system_configs"
    key           = Column(String, primary_key=True)
    value         = Column(String, nullable=False)


# ── Indexes (performance) ─────────────────────
Index("ix_tx_student",  Transaction.student_id)
Index("ix_tx_batch",    Transaction.batch_id)
Index("ix_tx_term_yr",  Transaction.term, Transaction.academic_year)
Index("ix_ss_student",  StudentScholarship.student_id)
Index("ix_stat_student",StudentStatus.student_id)


# ── Schema creation ───────────────────────────
Base.metadata.create_all(engine)

# ── Seed default users (first run only) ───────
def seed_default_users():
    from auth import hash_pw
    with get_db() as db:
        if not db.query(SystemUser).first():
            db.add(SystemUser(
                username="fin_admin",
                password_hash=hash_pw("NU_2026"),
                role="Admin",
                is_active=True,
            ))
            db.add(SystemUser(
                username="abdo_finance",
                password_hash=hash_pw("Finance2026"),
                role="Editor",
                is_active=True,
            ))
            db.add(RefCounter(id=1, seq=0))
            db.commit()


# ── Ref-counter helper (replaces full table scan) ──
def next_ref_sequence(db) -> int:
    row = db.get(RefCounter, 1)
    if row is None:
        row = RefCounter(id=1, seq=0)
        db.add(row)
        db.flush()
    row.seq += 1
    db.flush()
    return row.seq


def next_ref_block(db, count: int) -> int:
    row = db.get(RefCounter, 1)
    if row is None:
        row = RefCounter(id=1, seq=0)
        db.add(row)
        db.flush()
    start = row.seq + 1
    row.seq += count
    db.flush()
    return start


# ── Audit helper ──────────────────────────────
def write_audit(db, username: str, action: str, target: str = "", detail: str = ""):
    db.add(AuditLog(username=username, action=action, target=target, detail=detail))
    # caller is responsible for commit


# ── Cached lookups ────────────────────────────
@st.cache_data(ttl=1800)
def get_static_lookups():
    with get_db() as s:
        sch_map  = {sch.name: sch.id for sch in s.query(ScholarshipType).all()}
        colleges = [c[0] for c in s.query(Student.college).distinct().all() if c[0]]
        years    = [y[0] for y in s.query(Transaction.academic_year).distinct().all() if y[0]]
        
        # حماية بسيطة لو years رجعت فاضية
        if not years:
            from config import DEFAULT_YEAR
            years = [DEFAULT_YEAR]
            
        return sch_map, colleges, years


def highlight_negatives(val):
    """Pandas Styler: colour negative numbers red."""
    try:
        v = float(str(val).replace(",", ""))
        return "color: #d32f2f; font-weight: bold;" if v < 0 else ""
    except Exception:
        return ""
