# models.py
# ─────────────────────────────────────────────
# SQLAlchemy ORM models + DB engine + helpers
# All DB indexes are declared here.
# ─────────────────────────────────────────────
import os
from sqlalchemy import (
    create_engine, Column, Integer, String, Float,
    ForeignKey, DateTime, Date, Boolean, LargeBinary, Index, text, event
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
from functools import lru_cache

DB_URL = os.environ.get("DB_URL", "sqlite:///finance.db")

# ── Engine ────────────────────────────────────
@lru_cache(maxsize=1)
def get_db_engine():
    if "sqlite" in DB_URL:
        eng = create_engine(DB_URL, connect_args={"check_same_thread": False})
        
        # Optimize SQLite performance, speed and concurrency
        @event.listens_for(eng, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=-64000") # 64MB cache
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA busy_timeout=30000") # 30s busy timeout
            cursor.close()
            
        return eng
    return create_engine(DB_URL, pool_size=10, max_overflow=20, pool_pre_ping=True)

engine       = get_db_engine()
Base         = declarative_base()
SessionLocal = sessionmaker(bind=engine)


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
    password_changed_at = Column(DateTime, server_default=func.now())
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


class ScholarshipMapping(Base):
    __tablename__ = "scholarship_mappings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    charge_code = Column(String, unique=True, nullable=False, index=True)
    scholarship_type_id = Column(Integer, ForeignKey("scholarship_types.id"), nullable=False)


class StudentScholarship(Base):
    __tablename__ = "student_scholarships"
    id                 = Column(Integer, primary_key=True, autoincrement=True)
    student_id         = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    scholarship_type_id= Column(Integer, ForeignKey("scholarship_types.id"), nullable=False, index=True)
    # Always stored as 0–100 (percentage points, NOT a decimal fraction)
    percentage         = Column(Float, nullable=False)
    term               = Column(String, nullable=False, default="Spring")
    academic_year      = Column(Integer, nullable=False)
    is_active          = Column(Boolean, default=True)
    internal_note      = Column(String, nullable=True) # 🟢 ملاحظة داخلية للخصم/المنحة


class StudentStatus(Base):
    __tablename__ = "student_statuses"
    id           = Column(Integer, primary_key=True, autoincrement=True)
    student_id   = Column(Integer, ForeignKey("students.id"), nullable=False)
    term         = Column(String, nullable=False)
    academic_year= Column(Integer, nullable=False)
    status       = Column(String, nullable=False)


class FinancialStatusHistory(Base):
    __tablename__ = "financial_status_history"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    student_id    = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    status        = Column(String, nullable=False) # Good Standing, Financial Hold, Cleared
    comment       = Column(String, nullable=False)
    term          = Column(String, nullable=False)
    academic_year = Column(Integer, nullable=False)
    created_at    = Column(DateTime, default=func.now())
    created_by    = Column(String, nullable=True)


class Transaction(Base):
    __tablename__ = "transactions"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    reference_no     = Column(String, unique=True)
    batch_id         = Column(String, nullable=True)
    student_id       = Column(Integer, ForeignKey("students.id"), index=True)
    scholarship_type_id = Column(Integer, ForeignKey("scholarship_types.id"), nullable=True, index=True)
    transaction_type = Column(String, nullable=False)
    description      = Column(String)
    
    # 🟢 حقل الـ Internal Note (للملاحظات المخفية عن الطالب في الـ PDF)
    internal_note    = Column(String, nullable=True)
    
    # PC Integration specific
    pc_charge_credit_number = Column(String, nullable=True)
    pc_receipt_number       = Column(String, nullable=True)
    
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


class DisputeLog(Base):
    """Stores student account disputes and internal follow-up logs."""
    __tablename__ = "dispute_logs"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    is_disputed = Column(Boolean, default=False)
    notes      = Column(String, nullable=True)
    updated_by = Column(String, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


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

# ⚡ Performance optimizations compound & search indices
Index("ix_student_name",        Student.name)
Index("ix_tx_student_term_yr",  Transaction.student_id, Transaction.term, Transaction.academic_year)
Index("ix_ss_student_term_yr",  StudentScholarship.student_id, StudentScholarship.term, StudentScholarship.academic_year)


# ── Schema creation ───────────────────────────
Base.metadata.create_all(engine)

# ── Dynamic Schema Migrations ────────────────
def run_migrations():
    from sqlalchemy import inspect
    try:
        inspector = inspect(engine)
        
        if "system_users" in inspector.get_table_names():
            user_cols = [c["name"] for c in inspector.get_columns("system_users")]
            with engine.begin() as conn:
                col_type = "TIMESTAMP WITH TIME ZONE" if "postgres" in DB_URL else "DATETIME"
                bool_type = "BOOLEAN"
                if "password_changed_at" not in user_cols:
                    conn.execute(text(f"ALTER TABLE system_users ADD COLUMN password_changed_at {col_type} DEFAULT CURRENT_TIMESTAMP"))
                if "is_active" not in user_cols:
                    conn.execute(text(f"ALTER TABLE system_users ADD COLUMN is_active {bool_type} DEFAULT TRUE"))
                    
        if "student_scholarships" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("student_scholarships")]
            if "internal_note" not in columns:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE student_scholarships ADD COLUMN internal_note VARCHAR(1000) NULL"))
                    
        if "transactions" in inspector.get_table_names():
            tx_cols = [c["name"] for c in inspector.get_columns("transactions")]
            with engine.begin() as conn:
                if "pc_charge_credit_number" not in tx_cols:
                    conn.execute(text("ALTER TABLE transactions ADD COLUMN pc_charge_credit_number VARCHAR NULL"))
                if "pc_receipt_number" not in tx_cols:
                    conn.execute(text("ALTER TABLE transactions ADD COLUMN pc_receipt_number VARCHAR NULL"))
            
            # Enable pg_trgm for fast ILIKE searches (if PostgreSQL)
            if "postgres" in DB_URL:
                with engine.begin() as conn:
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_student_name_trgm ON students USING gin (name gin_trgm_ops);"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_student_email_trgm ON students USING gin (email gin_trgm_ops);"))
            
            # Explicitly create indexes for all foreign keys (create_all ignores existing tables)
            with engine.begin() as conn:
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_transactions_student_id ON transactions (student_id);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_transactions_sch_type_id ON transactions (scholarship_type_id);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_student_sch_student_id ON student_scholarships (student_id);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_student_sch_type_id ON student_scholarships (scholarship_type_id);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_fin_status_student_id ON financial_status_history (student_id);"))
    except Exception as e:
        print(f"Note: Database auto-migration alert: {e}")

run_migrations()

# ── Seed default users (first run only) ───────
def seed_default_users():
    from api.auth import hash_pw
    import os
    db = SessionLocal()
    try:
        if not db.query(SystemUser).first():
            admin_pw = os.getenv("SEED_ADMIN_PW")
            if not admin_pw:
                print('WARNING: SEED_ADMIN_PW not set — skipping user seed.')
                print('Set this env var on first deploy, then restart the service.')
                return
                
            editor_pw = os.getenv("SEED_EDITOR_PW")
            if not editor_pw:
                print('WARNING: SEED_EDITOR_PW not set — skipping user seed.')
                return
                
            db.add(SystemUser(
                username="fin_admin",
                password_hash=hash_pw(admin_pw),
                role="Admin",
                is_active=True,
            ))
            db.add(SystemUser(
                username="abdo_finance",
                password_hash=hash_pw(editor_pw),
                role="Editor",
                is_active=True,
            ))
            db.add(RefCounter(id=1, seq=0))
            db.commit()
    finally:
        db.close()

def sync_ref_counter(db):
    """Called once at startup to align counter with actual max ID."""
    max_id = db.query(func.max(Transaction.id)).scalar() or 0
    row = db.get(RefCounter, 1)
    if row and row.seq < max_id:
        row.seq = max_id + 100
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


import logging
from pythonjsonlogger import jsonlogger

# Set up structured JSON logger
audit_logger = logging.getLogger("finance_audit")
audit_logger.setLevel(logging.INFO)
if not audit_logger.handlers:
    audit_log_path = os.getenv("AUDIT_LOG_PATH")
    if audit_log_path:
        log_handler = logging.FileHandler(audit_log_path)
    else:
        log_handler = logging.StreamHandler()
        
    formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s')
    log_handler.setFormatter(formatter)
    audit_logger.addHandler(log_handler)

# ── Audit helper ──────────────────────────────
def write_audit(db, username: str, action: str, target: str = "", detail: str = ""):
    db.add(AuditLog(username=username, action=action, target=target, detail=detail))
    audit_logger.info("Audit Event", extra={
        "audit_username": username,
        "audit_action": action,
        "audit_target": target,
        "audit_detail": detail
    })
    # caller is responsible for commit


# ── Cached lookups ────────────────────────────
@lru_cache(maxsize=1)
def get_static_lookups():
    from contextlib import contextmanager
    with contextmanager(get_db)() as s:
        sch_map  = {sch.name: sch.id for sch in s.query(ScholarshipType).all()}
        colleges = [c[0] for c in s.query(Student.college).distinct().all() if c[0]]
        years    = [y[0] for y in s.query(Transaction.academic_year).distinct().all() if y[0]]
        
        # حماية بسيطة لو years رجعت فاضية
        if not years:
            from config import DEFAULT_YEAR
            years = [DEFAULT_YEAR]
            
        return sch_map, colleges, years
