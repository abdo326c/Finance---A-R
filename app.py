import os
import re
import base64
import hashlib
import time
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Date, Boolean, LargeBinary
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func, text
from datetime import datetime
from fpdf import FPDF
import io
from contextlib import contextmanager

# =======================================================
# 1. Centralized System Configuration
# =======================================================
VALID_TERMS = ["Fall", "Spring", "Summer"]
VALID_STATUSES = ["Active", "Inactive", "Graduated", "Program Withdraw", "Semester Withdraw"]
VALID_COLLEGES = ["ENG", "BBA", "IT_CS", "BIO_TECH"]
DEFAULT_YEAR = 2026

# =======================================================
# 2. Database Configuration & Connection 
# =======================================================
DB_URL = st.secrets.get("DB_URL", "sqlite:///finance.db")

@st.cache_resource
def get_db_engine():
    return create_engine(DB_URL, pool_size=10, max_overflow=20, pool_pre_ping=True)

engine = get_db_engine()
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()

# =======================================================
# 3. Database Models
# =======================================================
class SystemUser(Base):
    __tablename__ = 'system_users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="Editor")
    is_active = Column(Boolean, default=True)

class Student(Base):
    __tablename__ = 'students'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    college = Column(String)
    program = Column(String)
    birth_date = Column(Date)
    email = Column(String)
    mobile = Column(String)
    national_id = Column(String)
    nationality = Column(String)
    admit_year = Column(Integer)
    price_per_hr = Column(Float)

class ScholarshipType(Base):
    __tablename__ = 'scholarship_types'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True)

class StudentScholarship(Base):
    __tablename__ = 'student_scholarships'
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    scholarship_type_id = Column(Integer, ForeignKey('scholarship_types.id'), nullable=False)
    percentage = Column(Float, nullable=False)
    term = Column(String, nullable=False, default="Spring")
    academic_year = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)

class StudentStatus(Base):
    __tablename__ = 'student_statuses'
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    term = Column(String, nullable=False)
    academic_year = Column(Integer, nullable=False)
    status = Column(String, nullable=False)

class Transaction(Base):
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    reference_no = Column(String, unique=True)
    batch_id = Column(String, nullable=True)
    student_id = Column(Integer, ForeignKey('students.id'))
    scholarship_type_id = Column(Integer, ForeignKey('scholarship_types.id'), nullable=True)
    transaction_type = Column(String, nullable=False)
    description = Column(String)
    hours_change = Column(Float, default=0.0)
    debit = Column(Float, default=0)
    credit = Column(Float, default=0)
    entry_date = Column(Date, nullable=False)
    term = Column(String, nullable=False)
    academic_year = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class DeletedBatchLog(Base):
    __tablename__ = 'deleted_batch_logs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String, nullable=False)
    transaction_type = Column(String)
    record_count = Column(Integer)
    total_debit = Column(Float)
    total_credit = Column(Float)
    deleted_by = Column(String)
    deleted_at = Column(DateTime, server_default=func.now())

class PolicyDocument(Base):
    __tablename__ = 'policy_documents'
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    academic_year = Column(String, nullable=False)
    file_name = Column(String, nullable=False)
    file_data = Column(LargeBinary, nullable=False)
    uploaded_by = Column(String)
    uploaded_at = Column(DateTime, server_default=func.now())

Base.metadata.create_all(engine)

# إنشاء الحسابات الافتراضية
with get_db() as db:
    if not db.query(SystemUser).first():
        db.add(SystemUser(username="fin_admin", password_hash=hash_pw("NU_2026"), role="Admin", is_active=True))
        db.add(SystemUser(username="abdo_finance", password_hash=hash_pw("Finance2026"), role="Editor", is_active=True))
        db.commit()

@st.cache_data(ttl=3600)
def get_static_lookups():
    with get_db() as s:
        s_map = {sch.name: sch.id for sch in s.query(ScholarshipType).all()}
        colleges = [c[0] for c in s.query(Student.college).distinct().all() if c[0]]
        years = [y[0] for y in s.query(Transaction.academic_year).distinct().all() if y[0]] or [DEFAULT_YEAR]
        return s_map, colleges, years

try:
    sch_map, all_colleges, available_years = get_static_lookups()
except:
    sch_map, all_colleges, available_years = {}, [], [DEFAULT_YEAR]

# =======================================================
# 4. Core Helper Functions (Including New UX Helpers)
# =======================================================
def get_student_scholarships(db_session, student_id, term, academic_year):
    results = db_session.query(StudentScholarship, ScholarshipType).join(ScholarshipType).filter(
        StudentScholarship.student_id == student_id, StudentScholarship.term == term,
        StudentScholarship.academic_year == academic_year, StudentScholarship.is_active == True
    ).all()
    return [{'scholarship_type_id': ss.scholarship_type_id, 'name': st_type.name, 'percentage': ss.percentage} for ss, st_type in results]

def build_auto_discount_transactions(db_session, student_id, gross_amount, term, academic_year, entry_date, ref_start, batch_id=None):
    scholarships = get_student_scholarships(db_session, student_id, term, academic_year)
    if not scholarships: return []
    
    discount_txs, accumulated_pct, counter = [], 0.0, ref_start
    for sch in scholarships:
        pct = sch['percentage']
        requested_pct = pct * 100.0 if pct <= 1.0 else pct
        if requested_pct <= 0: continue
        actual_pct = min(requested_pct, max(0.0, 100.0 - accumulated_pct))
        accumulated_pct += actual_pct
        credit_val = gross_amount * (actual_pct / 100.0)
        desc = f"Scholarship: {sch['name']} ({actual_pct}%)" + (f" (Capped from {requested_pct}%)" if actual_pct < requested_pct else "")

        discount_txs.append(Transaction(
            reference_no=f"SCH-{counter:06d}", batch_id=batch_id, student_id=student_id, scholarship_type_id=sch['scholarship_type_id'], 
            transaction_type='Discount', description=desc, hours_change=0.0, debit=0.0, credit=credit_val, entry_date=entry_date, term=term, academic_year=academic_year
        ))
        counter += 1
        if accumulated_pct >= 100.0: break
    return discount_txs

def get_retroactive_scholarship_tx(db_session, student_id, term, academic_year, sch_type_id, sch_name, requested_pct, current_counter, batch_id=None):
    net_billed = db_session.query(func.sum(Transaction.debit - Transaction.credit)).filter(
        Transaction.student_id == student_id, Transaction.term == term, Transaction.academic_year == academic_year, 
        Transaction.transaction_type.in_(['Invoice', 'Bulk Invoices (Tuition)', 'Credit Hours Adjustment', 'Credit Hours Adjustments'])
    ).scalar() or 0.0

    if net_billed <= 0: return None, current_counter

    existing_other_txs = db_session.query(Transaction.description).filter(
        Transaction.student_id == student_id, Transaction.term == term, Transaction.academic_year == academic_year, 
        Transaction.reference_no.like('SCH-%'), Transaction.scholarship_type_id != sch_type_id
    ).all()

    other_pct = sum([float(re.search(r'\((\d+(\.\d+)?)%\)', tx[0]).group(1)) for tx in existing_other_txs if re.search(r'\((\d+(\.\d+)?)%\)', tx[0])])
    actual_pct = min(requested_pct, max(0.0, 100.0 - other_pct))
    target_discount = net_billed * (actual_pct / 100.0)

    existing_discount = db_session.query(func.sum(Transaction.credit - Transaction.debit)).filter(
        Transaction.student_id == student_id, Transaction.term == term, Transaction.academic_year == academic_year, 
        Transaction.scholarship_type_id == sch_type_id, Transaction.reference_no.like('SCH-%')
    ).scalar() or 0.0

    diff = target_discount - existing_discount
    if abs(diff) > 0.01:
        desc = f"Retroactive: {sch_name} ({actual_pct}%)" + (f" (Capped from {requested_pct}%)" if actual_pct < requested_pct else "")
        return Transaction(
            reference_no=f"SCH-{current_counter:06d}", batch_id=batch_id, student_id=student_id, scholarship_type_id=sch_type_id, 
            transaction_type='Discount', description=desc, debit=abs(diff) if diff < 0 else 0.0, credit=diff if diff > 0 else 0.0,
            hours_change=0.0, entry_date=datetime.now().date(), term=term, academic_year=academic_year
        ), current_counter + 1
    return None, current_counter

def enforce_scholarship_cap(db_session, student_id, term, academic_year):
    active_schs = db_session.query(StudentScholarship, ScholarshipType).join(ScholarshipType).filter(
        StudentScholarship.student_id == student_id, StudentScholarship.term == term,
        StudentScholarship.academic_year == academic_year, StudentScholarship.is_active == True
    ).order_by(StudentScholarship.id.asc()).all()
    if not active_schs: return []
    
    deactivated_names, running_pct = [], 0.0
    for ss, st_type in active_schs:
        pct = ss.percentage * 100.0 if ss.percentage <= 1.0 else ss.percentage
        if running_pct + pct > 100.0:
            ss.is_active = False
            deactivated_names.append(st_type.name)
        else: running_pct += pct
    return deactivated_names

# دالة تلوين الأرصدة السالبة باللون الأحمر
def highlight_negatives(val):
    try:
        v = float(str(val).replace(',', ''))
        return 'color: #d32f2f; font-weight: bold;' if v < 0 else ''
    except:
        return ''

# =======================================================
# 5. Authentication Setup & Session Timeout
# =======================================================
if 'authenticated' not in st.session_state: st.session_state['authenticated'] = False
if 'logged_in_user' not in st.session_state: st.session_state['logged_in_user'] = None
if 'user_role' not in st.session_state: st.session_state['user_role'] = None
if 'lookup_id' not in st.session_state: st.session_state['lookup_id'] = 0
if 'last_activity' not in st.session_state: st.session_state['last_activity'] = time.time()

def login_form():
    # 1. إضافة مسافات فاضية فوق عشان ننزل المربع لمنتصف الشاشة رأسياً
    st.markdown("<br><br><br><br>", unsafe_allow_html=True)
    
    # 2. تقسيم الشاشة لـ 3 أعمدة (الأول 30% فاضي، التاني 40% للفورم، التالت 30% فاضي)
    col1, col2, col3 = st.columns([1.5, 2, 1.5])
    
    with col2:
        # حطينا العنوان جوه العمود عشان يتوسط مع المربع
        st.markdown("<h2 style='text-align: center; color: #004a99;'>🔒 Finance Login</h2>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            user = st.text_input("Username")
            pwd = st.text_input("Password", type="password")
            
            st.markdown("<br>", unsafe_allow_html=True) # مسافة صغيرة قبل الزرار
            
            # خليت الزرار ياخد عرض المربع كله عشان يبقى شكله مودرن
            if st.form_submit_button("🚀 Login", use_container_width=True):
                with get_db() as db:
                    # فحص اليوزر (بدون حساسية لحالة الأحرف)
                    db_user = db.query(SystemUser).filter(
                        func.lower(SystemUser.username) == user.lower(), 
                        SystemUser.is_active == True
                    ).first()
                    
                    if db_user and db_user.password_hash == hash_pw(pwd):
                        st.session_state['authenticated'] = True
                        st.session_state['logged_in_user'] = db_user.username
                        st.session_state['user_role'] = db_user.role
                        st.session_state['last_activity'] = time.time()
                        st.rerun()
                    else:
                        st.error("❌ Invalid Username/Password, or Account is Disabled")

def get_next_ref_sequence(db_session):
    max_seq = 0
    refs = db_session.query(Transaction.reference_no).filter(Transaction.reference_no.isnot(None)).all()
    for (ref,) in refs:
        try:
            num = int(ref.split('-')[1])
            if num > max_seq: max_seq = num
        except: pass
    return max_seq

# =======================================================
# 6. PDF Generator
# =======================================================
class PDFStatement(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 10)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, "Finance Department  ||  A/R Team", 0, 0, 'C')

def create_pdf(sid, student_name, df, net_balance, total_debit, total_credit):
    pdf = PDFStatement(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("helvetica", 'B', 16)
    pdf.cell(0, 15, "Nile University - Student Statement of Account", ln=True, align='C')
    pdf.set_font("helvetica", '', 11)
    pdf.cell(0, 7, f"Student: {student_name} ({sid})", ln=True, align='L')
    pdf.cell(0, 7, f"Report Date: {datetime.now().strftime('%d-%b-%Y')}", ln=True, align='L')
    pdf.ln(5)
    
    pdf.set_fill_color(52, 73, 94)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", 'B', 10)
    
    headers, widths = ["Ref No", "Date", "Term", "Year", "Type", "Description", "Debit", "Credit"], [30, 25, 20, 15, 35, 90, 30, 30]
    for head, width in zip(headers, widths): pdf.cell(width, 10, head, 1, 0, 'C', True)
    pdf.ln()
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", '', 9)
    for _, row in df.iterrows():
        pdf.cell(30, 8, str(row['Ref No']), 1)
        pdf.cell(25, 8, str(row['Date']), 1)
        pdf.cell(20, 8, str(row['Term']), 1)
        pdf.cell(15, 8, str(row['Year']), 1)
        pdf.cell(35, 8, str(row['Type'])[:18], 1)
        pdf.cell(90, 8, str(row['Description'])[:55], 1)
        pdf.cell(30, 8, str(row['Debit']).replace(',', ''), 1, 0, 'R')
        pdf.cell(30, 8, str(row['Credit']).replace(',', ''), 1, 1, 'R')
        
    pdf.set_font("helvetica", 'B', 9)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(215, 8, "TOTALS", 1, 0, 'R', True)
    pdf.cell(30, 8, f"{total_debit:,.2f}", 1, 0, 'R', True)
    pdf.cell(30, 8, f"{total_credit:,.2f}", 1, 1, 'R', True)
    pdf.ln(8)
    
    pdf.set_font("helvetica", 'B', 14)
    pdf.cell(0, 10, f"NET BALANCE: {net_balance:,.2f} EGP", ln=True, align='R')
    return bytes(pdf.output())

# =======================================================
# 7. UI Configuration & Custom CSS
# =======================================================
st.set_page_config(page_title="Finance A/R System", layout="wide", page_icon="🏦", initial_sidebar_state="expanded")

hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden !important;}
footer {visibility: hidden !important;}
.stDeployButton {display:none !important;}

/* إخفاء الهيدر الافتراضي تماماً لعدم التشويش */
header[data-testid="stHeader"] {background: transparent !important;}

.block-container { padding-top: 2rem !important; padding-bottom: 1rem !important; }

/* --- Modern Sidebar Menu CSS --- */
[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child { display: none !important; }
[data-testid="stSidebar"] div[role="radiogroup"] > label {
    padding: 8px 12px; border-radius: 8px; margin-bottom: 4px;
    background-color: transparent; transition: all 0.2s ease; cursor: pointer; font-weight: 500;
}
[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
    background-color: #f0f2f6; transform: translateX(4px);
}
[data-testid="stSidebar"] div[role="radiogroup"] > label[data-baseweb="radio"] input:checked + div {
    background-color: #eaf1fa !important; color: #004a99 !important; font-weight: 700 !important; 
    border-left: 4px solid #004a99 !important; border-radius: 0px 8px 8px 0px !important; 
    padding: 8px 10px !important; width: 100% !important; 
}

/* --- Metrics and Buttons CSS --- */
[data-testid="stMetricValue"] { font-size: 32px !important; color: #004a99 !important; }
[data-testid="stMetric"] {
    background-color: #ffffff; padding: 25px; border-radius: 15px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05); border-left: 6px solid #004a99;
}
.stButton>button { border-radius: 8px; border: none; transition: all 0.3s; }
.stButton>button:hover { transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

if not st.session_state['authenticated']:
    login_form()
    st.stop()

# --- Session Timeout Logic (30 Minutes) ---
TIMEOUT_SECONDS = 30 * 60
current_time = time.time()
if current_time - st.session_state['last_activity'] > TIMEOUT_SECONDS:
    st.session_state['authenticated'] = False
    st.session_state['logged_in_user'] = None
    st.session_state['user_role'] = None
    st.warning("⚠️ Session expired due to inactivity (30m). Please login again.")
    st.stop()
else:
    st.session_state['last_activity'] = current_time

# =======================================================
# 8. Main App Framework & Sidebar
# =======================================================
st.markdown("<h3 style='color: #1f2937; margin-bottom: -15px;'>🏦 Nile University - Finance A/R System</h3>", unsafe_allow_html=True)
st.markdown("---")

# Toast Notifications الجديد (بدل st.success القديمة)
if st.session_state.get('flash_msg'):
    st.toast(st.session_state['flash_msg'], icon='✅')
    st.session_state['flash_msg'] = None

with st.sidebar:
    
    selected_tab = st.radio("Navigation", [
        "📊 Dashboard", "📜 Student Statement", "📈 Reports", "📚 Policies & Docs", 
        "🔍 Student Lookup", "📊 Operations", "📤 Bulk Financials", "🎓 Scholarships", 
        "👤 Registration", "🗑️ Batch Management", "⚙️ System Admin"
    ], label_visibility="collapsed")
    
    st.markdown("---")
    st.caption(f"👤 Logged in as: **{st.session_state.get('logged_in_user', 'Unknown')}**")
    st.markdown("<br>", unsafe_allow_html=True) 
    
    if st.button("🚪 Log out", use_container_width=True, key="sidebar_logout"):
        st.session_state['authenticated'] = False
        st.session_state['logged_in_user'] = None
        st.session_state['user_role'] = None
        st.rerun()

# =======================================================
# SECTION: Dashboard
# =======================================================
if selected_tab == "📊 Dashboard":
    dash_f1, dash_f2, dash_f3 = st.columns(3)
    dash_filter_term    = dash_f1.selectbox("Filter by Term:", ["All Terms"] + VALID_TERMS, key="dash_term")
    dash_filter_year    = dash_f2.selectbox("Filter by Year:", ["All Years"] + [str(y) for y in available_years], key="dash_year")
    dash_filter_college = dash_f3.selectbox("Filter by College:", ["All Colleges"] + VALID_COLLEGES, key="dash_college")

    st.markdown("<br>", unsafe_allow_html=True)

    with get_db() as db:
        base_q = db.query(Transaction).join(Student, Transaction.student_id == Student.id)
        status_q = db.query(StudentStatus).filter(StudentStatus.status == 'Active')
        student_q = db.query(Student)

        if dash_filter_term != "All Terms":
            base_q = base_q.filter(Transaction.term == dash_filter_term)
            status_q = status_q.filter(StudentStatus.term == dash_filter_term)

        if dash_filter_year != "All Years":
            yr_int = int(dash_filter_year)
            base_q = base_q.filter(Transaction.academic_year == yr_int)
            status_q = status_q.filter(StudentStatus.academic_year == yr_int)

        if dash_filter_college != "All Colleges":
            base_q = base_q.filter(Student.college == dash_filter_college)
            student_q = student_q.filter(Student.college == dash_filter_college)
            status_q = status_q.join(Student, StudentStatus.student_id == Student.id).filter(Student.college == dash_filter_college)

        gross_billed = base_q.filter(Transaction.transaction_type.in_(['Invoice', 'Bulk Invoices (Tuition)', 'Other Fees', 'Bulk Other Fees'])).with_entities(func.sum(Transaction.debit)).scalar() or 0.0
        total_discounts = base_q.filter(Transaction.transaction_type.in_(['Discount', 'Bulk Scholarships'])).with_entities(func.sum(Transaction.credit - Transaction.debit)).scalar() or 0.0
        total_payments = base_q.filter(Transaction.transaction_type.in_(['Payment Receipt', 'Bulk Payments'])).with_entities(func.sum(Transaction.credit - Transaction.debit)).scalar() or 0.0
        net_adjustments = base_q.filter(~Transaction.transaction_type.in_(['Invoice', 'Bulk Invoices (Tuition)', 'Other Fees', 'Bulk Other Fees', 'Discount', 'Bulk Scholarships', 'Payment Receipt', 'Bulk Payments'])).with_entities(func.sum(Transaction.debit - Transaction.credit)).scalar() or 0.0
        net_balance = base_q.with_entities(func.sum(Transaction.debit - Transaction.credit)).scalar() or 0.0

        total_students = student_q.count()
        active_count = status_q.distinct(StudentStatus.student_id).count()

    st.markdown("### 💰 Financial Summary")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.markdown(f"""<div style="background: linear-gradient(135deg, #1a73e8, #0d47a1); padding: 15px; border-radius: 12px; color: white; height: 110px;">
                <p style="margin: 0; font-size: 14px; opacity: 0.85;">📈 Gross Billed</p><h3 style="margin: 5px 0 0 0; font-size: 22px;">{gross_billed:,.0f}</h3></div>""", unsafe_allow_html=True)
    with kpi2:
        st.markdown(f"""<div style="background: linear-gradient(135deg, #e53935, #b71c1c); padding: 15px; border-radius: 12px; color: white; height: 110px;">
                <p style="margin: 0; font-size: 14px; opacity: 0.85;">🎓 Total Scholarships</p><h3 style="margin: 5px 0 0 0; font-size: 22px;">{total_discounts:,.0f}</h3></div>""", unsafe_allow_html=True)
    with kpi3:
        st.markdown(f"""<div style="background: linear-gradient(135deg, #00897b, #004d40); padding: 15px; border-radius: 12px; color: white; height: 110px;">
                <p style="margin: 0; font-size: 14px; opacity: 0.85;">💳 Total Payments</p><h3 style="margin: 5px 0 0 0; font-size: 22px;">{total_payments:,.0f}</h3></div>""", unsafe_allow_html=True)
    with kpi4:
        adj_color_start = "#fb8c00" if net_adjustments >= 0 else "#757575"
        adj_color_end   = "#e65100" if net_adjustments >= 0 else "#424242"
        st.markdown(f"""<div style="background: linear-gradient(135deg, {adj_color_start}, {adj_color_end}); padding: 15px; border-radius: 12px; color: white; height: 110px;">
                <p style="margin: 0; font-size: 14px; opacity: 0.85;">⚙️ Net Adjustments</p><h3 style="margin: 5px 0 0 0; font-size: 22px;">{net_adjustments:,.0f}</h3></div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    kpi5, kpi6, kpi7 = st.columns(3)
    with kpi5:
        net_color_start = "#2e7d32" if net_balance >= 0 else "#b71c1c"
        net_color_end   = "#1b5e20" if net_balance >= 0 else "#7f0000"
        st.markdown(f"""<div style="background: linear-gradient(135deg, {net_color_start}, {net_color_end}); padding: 20px; border-radius: 12px; color: white; height: 120px;">
                <p style="margin: 0; font-size: 16px; opacity: 0.85;">⚖️ Net Balance Due</p><h2 style="margin: 8px 0 0 0; font-size: 28px;">{net_balance:,.0f} EGP</h2></div>""", unsafe_allow_html=True)
    with kpi6:
        st.markdown(f"""<div style="background: linear-gradient(135deg, #5e35b1, #311b92); padding: 20px; border-radius: 12px; color: white; height: 120px;">
                <p style="margin: 0; font-size: 16px; opacity: 0.85;">👥 Total Students</p><h2 style="margin: 8px 0 0 0; font-size: 28px;">{total_students:,}</h2></div>""", unsafe_allow_html=True)
    with kpi7:
        st.markdown(f"""<div style="background: linear-gradient(135deg, #f57c00, #e65100); padding: 20px; border-radius: 12px; color: white; height: 120px;">
                <p style="margin: 0; font-size: 16px; opacity: 0.85;">✅ Active Students</p><h2 style="margin: 8px 0 0 0; font-size: 28px;">{active_count:,}</h2></div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")
    
    st.markdown("### 📋 Revenue Breakdown by College")
    with get_db() as db:
        college_sql = text("""
            SELECT s.college AS "College", COUNT(DISTINCT s.id) AS "Students",
                COALESCE(SUM(CASE WHEN t.transaction_type IN ('Invoice','Bulk Invoices (Tuition)') THEN t.debit ELSE 0 END), 0) AS "Tuition Billed (EGP)",
                COALESCE(SUM(CASE WHEN t.transaction_type IN ('Discount','Bulk Scholarships') THEN t.credit - t.debit ELSE 0 END), 0) AS "Discounts (EGP)",
                COALESCE(SUM(CASE WHEN t.transaction_type IN ('Payment Receipt','Bulk Payments') THEN t.credit ELSE 0 END), 0) AS "Payments (EGP)",
                COALESCE(SUM(t.debit) - SUM(t.credit), 0) AS "Net Balance (EGP)"
            FROM students s LEFT JOIN transactions t ON s.id = t.student_id
                AND (:term_filter = 'All Terms' OR t.term = :term_filter) AND (:year_filter = 'All Years' OR t.academic_year = :year_val)
            WHERE (:college_filter = 'All Colleges' OR s.college = :college_filter)
            GROUP BY s.college ORDER BY s.college
        """)
        df_college = pd.read_sql(college_sql, con=engine, params={
            "term_filter": dash_filter_term, "year_filter": dash_filter_year,
            "year_val": int(dash_filter_year) if dash_filter_year != "All Years" else 0, "college_filter": dash_filter_college
        })

        if not df_college.empty:
            totals_row = {
                "College": "🔢 TOTAL", "Students": df_college["Students"].sum(), "Tuition Billed (EGP)": df_college["Tuition Billed (EGP)"].sum(),
                "Discounts (EGP)": df_college["Discounts (EGP)"].sum(), "Payments (EGP)": df_college["Payments (EGP)"].sum(), "Net Balance (EGP)": df_college["Net Balance (EGP)"].sum()
            }
            df_college_display = pd.concat([df_college, pd.DataFrame([totals_row])], ignore_index=True)

            # تلوين الأرصدة السالبة في الداشبورد
            st.dataframe(
                df_college_display.style.format({
                    "Tuition Billed (EGP)": "{:,.2f}", "Discounts (EGP)": "{:,.2f}", "Payments (EGP)": "{:,.2f}", "Net Balance (EGP)": "{:,.2f}"
                }).map(highlight_negatives, subset=["Net Balance (EGP)"]).apply(lambda x: ['font-weight: bold; background-color: #f0f4ff' if x.name == len(df_college_display)-1 else '' for _ in x], axis=1),
                use_container_width=True, hide_index=True
            )
            
            buf_dash = io.BytesIO()
            df_college.to_excel(buf_dash, index=False)
            st.download_button("📗 Download College Report (Excel)", data=buf_dash.getvalue(), file_name=f"Dashboard_Report_{datetime.now().strftime('%Y%m%d')}.xlsx")
        else:
            st.info("⚠️ No financial data found for the selected filters.")

    st.markdown("---")
    if gross_billed > 0:
        discount_pct, collection_pct = (total_discounts / gross_billed) * 100, (total_payments / gross_billed) * 100
        st.markdown("### 📐 Key Ratios")
        ratio1, ratio2 = st.columns(2)
        with ratio1: st.metric("🎓 Discount Rate (Scholarships / Gross Billed)", f"{discount_pct:.1f}%", f"{total_discounts:,.0f} EGP in discounts")
        with ratio2: st.metric("💳 Collection Rate (Payments / Gross Billed)", f"{collection_pct:.1f}%", f"{total_payments:,.0f} EGP collected")

# =======================================================
# SECTION: Student Statement
# =======================================================
elif selected_tab == "📜 Student Statement":
    st.subheader("Transaction Search & Statement of Account")
    st.markdown("💡 Leave Student ID blank and enter a Bank Ref or System Ref to search globally.")
    
    if 'stmt_search_params' not in st.session_state: st.session_state['stmt_search_params'] = None

    with st.form("stmt_search_form", clear_on_submit=False):
        col_t1, col_t2, col_t3 = st.columns(3)
        default_stmt_id = str(st.session_state.get('lookup_id', '')) if st.session_state.get('lookup_id', 0) > 0 else ""
        search_r = col_t1.text_input("Student ID", value=default_stmt_id, placeholder="e.g., 26100123")
        sys_ref_search = col_t2.text_input("System Ref No", placeholder="e.g., INV-004751")
        bank_ref_search = col_t3.text_input("Bank Ref / Description", placeholder="e.g., 12345 or CIB")
        
        f1, f2, f3 = st.columns(3)
        df_r = f1.date_input("Date Range", [])
        s_t = f2.multiselect("Terms", VALID_TERMS)
        s_y = f3.multiselect("Years", available_years)
        
        if st.form_submit_button("🔍 Search Transactions"):
            st.session_state['stmt_search_params'] = {
                'sid': int(search_r) if search_r.strip().isdigit() else 0, 'sys': sys_ref_search, 'bank': bank_ref_search, 
                'dates': df_r, 'terms': s_t, 'years': s_y
            }

    if st.session_state.get('stmt_search_params'):
        p = st.session_state['stmt_search_params']
        if p['sid'] > 0 or p['sys'] or p['bank'] or len(p['dates']) == 2 or p['terms'] or p['years']:
            with get_db() as db:
                q = db.query(Transaction, Student).join(Student, Transaction.student_id == Student.id)
                if p['sid'] > 0: q = q.filter(Transaction.student_id == p['sid'])
                if p['sys']: q = q.filter(Transaction.reference_no.ilike(f"%{p['sys']}%"))
                if p['bank']: q = q.filter(Transaction.description.ilike(f"%{p['bank']}%"))
                if len(p['dates']) == 2: q = q.filter(Transaction.entry_date.between(p['dates'][0], p['dates'][1]))
                if p['terms']: q = q.filter(Transaction.term.in_(p['terms']))
                if p['years']: q = q.filter(Transaction.academic_year.in_(p['years']))

                res = q.order_by(Transaction.entry_date.desc()).limit(5000).all()
                if res:
                    df_display = pd.DataFrame([{
                        "Student ID": s.id, "Name": s.name, "Ref No": t.reference_no, "Date": t.entry_date, "Term": t.term, 
                        "Year": t.academic_year, "Type": t.transaction_type, "Description": t.description, "Debit": t.debit, "Credit": t.credit 
                    } for t, s in res])
                    
                    st.dataframe(df_display, use_container_width=True, column_config={
                        "Debit": st.column_config.NumberColumn("Debit", format="%,.2f"), "Credit": st.column_config.NumberColumn("Credit", format="%,.2f")
                    })

                    if p['sid'] > 0:
                        total_debit = sum(t.debit for t, s in res)
                        total_credit = sum(t.credit for t, s in res)
                        net = total_debit - total_credit
                        
                        m1, m2, m3 = st.columns(3)
                        m1.metric("Total Debit", f"{total_debit:,.2f} EGP")
                        m2.metric("Total Credit", f"{total_credit:,.2f} EGP")
                        m3.metric("Net Balance Due", f"{net:,.2f} EGP")
                        
                        df_pdf = pd.DataFrame([{"Ref No": t.reference_no, "Date": t.entry_date, "Term": t.term, "Year": t.academic_year, "Type": t.transaction_type, "Description": t.description, "Debit": f"{t.debit:,.2f}", "Credit": f"{t.credit:,.2f}"} for t, s in res])
                        
                        b1, b2 = st.columns(2)
                        with b1:
                            pdf_data = create_pdf(p['sid'], res[0][1].name, df_pdf, net, total_debit, total_credit)
                            st.download_button("📄 Download PDF Statement", data=pdf_data, file_name=f"SOA_{p['sid']}.pdf", use_container_width=True)
                        with b2:
                            df_export = df_display.copy()
                            df_export.loc[len(df_export)] = {"Student ID": "", "Name": "", "Ref No": "", "Date": "", "Term": "", "Year": "", "Type": "", "Description": "TOTALS", "Debit": total_debit, "Credit": total_credit}
                            excel_buf = io.BytesIO()
                            df_export.to_excel(excel_buf, index=False)
                            st.download_button("📗 Download Excel Sheet", data=excel_buf.getvalue(), file_name=f"SOA_{p['sid']}.xlsx", use_container_width=True)
                else: st.warning("⚠️ No transactions found matching these criteria.")

# =======================================================
# SECTION: Management Reports
# =======================================================
elif selected_tab == "📈 Reports":
    st.subheader("📈 Financial Management Reports")
    
    if 'report_params' not in st.session_state: st.session_state['report_params'] = None
        
    with st.form("reports_filter_form", clear_on_submit=False):
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        sel_col = col_f1.multiselect("Filter by College", VALID_COLLEGES) 
        sel_term = col_f2.multiselect("Filter by Term", VALID_TERMS)
        sel_year = col_f3.multiselect("Filter by Year", available_years)
        sel_status = col_f4.multiselect("Filter by Status", VALID_STATUSES)
        
        col_f5, col_f6 = st.columns([1, 2])
        sel_dates = col_f5.date_input("Date Range", [])
        rep_v = col_f6.radio("Format: ", ["Accounting Summary", "Full Detailed Log", "Period Closing (Activity Summary)", "Student Academic Status Report"], horizontal=True)
        
        if st.form_submit_button("📂 Generate Report Data"):
            st.session_state['report_params'] = {'col': sel_col, 'term': sel_term, 'year': sel_year, 'status': sel_status, 'dates': sel_dates, 'format': rep_v}

    if st.session_state.get('report_params'):
        p = st.session_state['report_params']
        with st.spinner("Processing High-Speed Data Report..."):
            
            if p['format'] == "Student Academic Status Report":
                sql = text('SELECT s.id AS "Student ID", s.name AS "Student Name", s.college AS "College", s.program AS "Program", ss.term AS "Term", ss.academic_year AS "Year", ss.status AS "Academic Status" FROM student_statuses ss JOIN students s ON ss.student_id = s.id WHERE (:c_cnt = 0 OR s.college IN :cls) AND (:t_cnt = 0 OR ss.term IN :trms) AND (:y_cnt = 0 OR ss.academic_year IN :yrs) AND (:s_cnt = 0 OR ss.status IN :stats) ORDER BY ss.academic_year DESC, ss.term, s.college, s.id')
                params = {"c_cnt": len(p['col']), "cls": tuple(p['col']) if p['col'] else ('',), "t_cnt": len(p['term']), "trms": tuple(p['term']) if p['term'] else ('',), "y_cnt": len(p['year']), "yrs": tuple(p['year']) if p['year'] else (-1,), "s_cnt": len(p['status']), "stats": tuple(p['status']) if p['status'] else ('',)}
                df = pd.read_sql(sql, con=engine, params=params)
                if not df.empty: st.dataframe(df, use_container_width=True)
                else: st.warning("No status history found matching the selected criteria.")
                    
            elif p['format'] == "Accounting Summary":
                sql = text("""
                    SELECT s.id AS "ID", s.name AS "Student Name", s.college AS "College", s.email AS "Email", 
                        COALESCE((SELECT status FROM student_statuses WHERE student_id = s.id ORDER BY id DESC LIMIT 1), 'Not Set') AS "Current Status", s.price_per_hr AS "Price/Hr", 
                        COALESCE(SUM(t.hours_change), 0) AS "Reg. Hours", COALESCE(SUM(CASE WHEN t.transaction_type IN ('Invoice', 'Bulk Invoices (Tuition)') THEN t.debit ELSE 0 END), 0) AS "Tuition Billed", 
                        COALESCE(SUM(CASE WHEN t.transaction_type IN ('Other Fees', 'Bulk Other Fees') THEN t.debit ELSE 0 END), 0) AS "Other Fees", COALESCE(SUM(CASE WHEN t.transaction_type IN ('Discount', 'Bulk Scholarships') THEN t.credit - t.debit ELSE 0 END), 0) AS "Discounts", 
                        COALESCE(SUM(CASE WHEN t.transaction_type IN ('Payment Receipt', 'Bulk Payments') THEN t.credit - t.debit ELSE 0 END), 0) AS "Payments", COALESCE(SUM(CASE WHEN t.transaction_type IN ('Credit Hours Adjustment', 'Credit Hours Adjustments', 'General Adjustment', 'General Adjustments') THEN t.debit - t.credit ELSE 0 END), 0) AS "Adjustments", 
                        COALESCE(SUM(t.debit) - SUM(t.credit), 0) AS "Balance" 
                    FROM students s LEFT JOIN transactions t ON s.id = t.student_id AND (:t_cnt = 0 OR t.term IN :trms) AND (:y_cnt = 0 OR t.academic_year IN :yrs) 
                    WHERE (:c_cnt = 0 OR s.college IN :cls) AND (:s_cnt = 0 OR COALESCE((SELECT status FROM student_statuses WHERE student_id = s.id ORDER BY id DESC LIMIT 1), 'Not Set') IN :stats)
                    GROUP BY s.id, s.name, s.college, s.email, s.price_per_hr ORDER BY s.id
                """)
                params = {"c_cnt": len(p['col']), "cls": tuple(p['col']) if p['col'] else ('',), "t_cnt": len(p['term']), "trms": tuple(p['term']) if p['term'] else ('',), "y_cnt": len(p['year']), "yrs": tuple(p['year']) if p['year'] else (-1,), "s_cnt": len(p['status']), "stats": tuple(p['status']) if p['status'] else ('',)}
                df = pd.read_sql(sql, con=engine, params=params)
                if not df.empty:
                    # إضافة سطر المجموع وتلوين السالب
                    totals_row = pd.Series(dtype=object)
                    totals_row['Student Name'] = "🔢 TOTAL"
                    for col in ["Reg. Hours", "Tuition Billed", "Other Fees", "Discounts", "Payments", "Adjustments", "Balance"]:
                        totals_row[col] = df[col].sum()
                    df_display = pd.concat([df, pd.DataFrame([totals_row])], ignore_index=True)

                    st.dataframe(df_display.style.format({
                        "Price/Hr": "{:,.2f}", "Reg. Hours": "{:,.1f}", "Tuition Billed": "{:,.2f}", "Other Fees": "{:,.2f}", 
                        "Discounts": "{:,.2f}", "Payments": "{:,.2f}", "Adjustments": "{:,.2f}", "Balance": "{:,.2f}"
                    }).map(highlight_negatives, subset=["Balance"]).apply(lambda x: ['background-color: #f0f4ff; font-weight: bold' if x.name == len(df_display)-1 else '' for _ in x], axis=1), use_container_width=True)
                else: st.warning("No data found matching the selected criteria.")

            elif p['format'] == "Period Closing (Activity Summary)":
                if len(p['dates']) != 2: st.warning("⚠️ Please select a Date Range.")
                else:
                    sql = text("""
                        SELECT s.id AS "ID", s.name AS "Student Name", s.college AS "College", COALESCE((SELECT status FROM student_statuses WHERE student_id = s.id ORDER BY id DESC LIMIT 1), 'Not Set') AS "Current Status", 
                            COALESCE(SUM(t.hours_change), 0) AS "CH Changed", COALESCE(SUM(CASE WHEN t.transaction_type IN ('Invoice', 'Bulk Invoices (Tuition)') THEN t.debit ELSE 0 END), 0) AS "Tuition Billed", 
                            COALESCE(SUM(CASE WHEN t.transaction_type IN ('Other Fees', 'Bulk Other Fees') THEN t.debit ELSE 0 END), 0) AS "Other Fees", COALESCE(SUM(CASE WHEN t.transaction_type IN ('Discount', 'Bulk Scholarships') THEN t.credit - t.debit ELSE 0 END), 0) AS "New Discounts", 
                            COALESCE(SUM(CASE WHEN t.transaction_type IN ('Payment Receipt', 'Bulk Payments') THEN t.credit - t.debit ELSE 0 END), 0) AS "Payments Received", COALESCE(SUM(CASE WHEN t.transaction_type IN ('Credit Hours Adjustment', 'Credit Hours Adjustments', 'General Adjustment', 'General Adjustments') THEN t.debit - t.credit ELSE 0 END), 0) AS "Adjustments", 
                            COALESCE(SUM(t.debit) - SUM(t.credit), 0) AS "Net Period Change" 
                        FROM transactions t JOIN students s ON t.student_id = s.id 
                        WHERE (:c_cnt = 0 OR s.college IN :cls) AND (:t_cnt = 0 OR t.term IN :trms) AND (:y_cnt = 0 OR t.academic_year IN :yrs) AND (:s_cnt = 0 OR COALESCE((SELECT status FROM student_statuses WHERE student_id = s.id ORDER BY id DESC LIMIT 1), 'Not Set') IN :stats)
                          AND t.entry_date >= :s_date AND t.entry_date <= :e_date 
                        GROUP BY s.id, s.name, s.college HAVING COALESCE(SUM(t.debit), 0) > 0 OR COALESCE(SUM(t.credit), 0) > 0 ORDER BY s.id
                    """)
                    params = {"c_cnt": len(p['col']), "cls": tuple(p['col']) if p['col'] else ('',), "t_cnt": len(p['term']), "trms": tuple(p['term']) if p['term'] else ('',), "y_cnt": len(p['year']), "yrs": tuple(p['year']) if p['year'] else (-1,), "s_cnt": len(p['status']), "stats": tuple(p['status']) if p['status'] else ('',), "s_date": p['dates'][0], "e_date": p['dates'][1]}
                    df = pd.read_sql(sql, con=engine, params=params)
                    if not df.empty:
                        # إضافة الإجماليات والتلوين
                        totals_row = pd.Series(dtype=object)
                        totals_row['Student Name'] = "🔢 TOTAL"
                        for col in ["CH Changed", "Tuition Billed", "Other Fees", "New Discounts", "Payments Received", "Adjustments", "Net Period Change"]:
                            totals_row[col] = df[col].sum()
                        df_display = pd.concat([df, pd.DataFrame([totals_row])], ignore_index=True)
                        st.dataframe(df_display.style.format({
                            "CH Changed": "{:,.1f}", "Tuition Billed": "{:,.2f}", "Other Fees": "{:,.2f}", "New Discounts": "{:,.2f}", 
                            "Payments Received": "{:,.2f}", "Adjustments": "{:,.2f}", "Net Period Change": "{:,.2f}"
                        }).map(highlight_negatives, subset=["Net Period Change"]).apply(lambda x: ['background-color: #f0f4ff; font-weight: bold' if x.name == len(df_display)-1 else '' for _ in x], axis=1), use_container_width=True)
                    else: st.warning("No financial activity found in the selected date range.")

            else:
                sql = text("""SELECT t.student_id, s.name, s.college, COALESCE((SELECT status FROM student_statuses WHERE student_id = s.id ORDER BY id DESC LIMIT 1), 'Not Set') AS "Current Status", t.reference_no, t.entry_date, t.term, t.academic_year, t.description, t.hours_change AS "Hours", t.debit, t.credit FROM transactions t JOIN students s ON t.student_id = s.id WHERE (:c_cnt = 0 OR s.college IN :cls) AND (:t_cnt = 0 OR t.term IN :trms) AND (:y_cnt = 0 OR t.academic_year IN :yrs) AND (:s_cnt = 0 OR COALESCE((SELECT status FROM student_statuses WHERE student_id = s.id ORDER BY id DESC LIMIT 1), 'Not Set') IN :stats) AND (:has_dates = 0 OR (t.entry_date >= :s_date AND t.entry_date <= :e_date)) ORDER BY t.student_id, t.entry_date DESC""")
                params = {"c_cnt": len(p['col']), "cls": tuple(p['col']) if p['col'] else ('',), "t_cnt": len(p['term']), "trms": tuple(p['term']) if p['term'] else ('',), "y_cnt": len(p['year']), "yrs": tuple(p['year']) if p['year'] else (-1,), "s_cnt": len(p['status']), "stats": tuple(p['status']) if p['status'] else ('',), "has_dates": 1 if len(p['dates']) == 2 else 0, "s_date": p['dates'][0] if len(p['dates']) == 2 else None, "e_date": p['dates'][1] if len(p['dates']) == 2 else None}
                df = pd.read_sql(sql, con=engine, params=params)
                if not df.empty:
                    st.dataframe(df, use_container_width=True, column_config={"Hours": st.column_config.NumberColumn("Hours", format="%,.1f"), "debit": st.column_config.NumberColumn("Debit", format="%,.2f"), "credit": st.column_config.NumberColumn("Credit", format="%,.2f")})
                else: st.warning("No financial activity found in the selected criteria.")

            if 'df' in locals() and not df.empty:
                buf_rep_final = io.BytesIO()
                df.to_excel(buf_rep_final, index=False)
                st.download_button("📗 Download Excel Report", data=buf_rep_final.getvalue(), file_name=f"Management_Report_{p['format'].replace(' ', '_')}.xlsx", use_container_width=True)

# =======================================================
# SECTION: Policies & Docs
# =======================================================
elif selected_tab == "📚 Policies & Docs":
    st.subheader("📚 University Financial Policies & Documents")
    doc_action = st.radio("Action: ", ["📂 View & Download", "📤 Upload New Document (Admin Only)"], horizontal=True)

    if doc_action == "📂 View & Download":
        with get_db() as db:
            available_doc_years = [y[0] for y in db.query(PolicyDocument.academic_year).distinct().all()]
            if "2022/2023" not in available_doc_years: available_doc_years.append("2022/2023")
            if "2025/2026" not in available_doc_years: available_doc_years.append("2025/2026")
                
            sel_doc_year = st.selectbox("Filter by Academic Year:", sorted(set(available_doc_years), reverse=True))
            st.markdown("### 🗄️ Original Uploaded PDF Files")
            docs = db.query(PolicyDocument).filter_by(academic_year=sel_doc_year).order_by(PolicyDocument.uploaded_at.desc()).all()
            
            if docs:
                for doc in docs:
                    with st.container():
                        c1, c2, c3, c4 = st.columns([4, 1, 1, 1])
                        c1.markdown(f"📄 **{doc.title}** <br><small>Uploaded by {doc.uploaded_by} on {doc.uploaded_at.strftime('%Y-%m-%d')}</small>", unsafe_allow_html=True)
                        if c2.button("👁️ View PDF", key=f"view_{doc.id}"): st.session_state['view_doc_id'] = doc.id
                        c3.download_button("⬇️ Download PDF", data=doc.file_data, file_name=doc.file_name, mime="application/pdf", key=f"dl_{doc.id}")
                        
                        if st.session_state.get('user_role') == 'Admin':
                            if c4.button("🗑️ Delete", key=f"del_{doc.id}"):
                                db.delete(doc)
                                db.commit()
                                st.rerun()
                        else: c4.write(" ") 
                            
                st.markdown("---")
                if st.session_state.get('view_doc_id'):
                    doc_to_view = db.query(PolicyDocument).get(st.session_state['view_doc_id'])
                    if doc_to_view: 
                        st.markdown(f"### 👀 Viewing PDF: {doc_to_view.title}")
                        if st.button("❌ Close Document Reader"):
                            st.session_state['view_doc_id'] = None
                            st.rerun()
                        st.markdown(f'<iframe src="data:application/pdf;base64,{base64.b64encode(doc_to_view.file_data).decode("utf-8")}" width="100%" height="800" type="application/pdf"></iframe>', unsafe_allow_html=True)
            else: st.warning("⚠️ No original PDF document has been uploaded for this academic year yet.")

    elif doc_action == "📤 Upload New Document (Admin Only)":
        if st.session_state.get('user_role') == 'Admin':
            with st.form("upload_doc_form", clear_on_submit=True):
                doc_title = st.text_input("Document Title *", placeholder="e.g., Financial Policy 2025/2026")
                doc_year = st.selectbox("Academic Year *", [f"{y}/{y+1}" for y in range(2020, 2030)], index=5) 
                doc_file = st.file_uploader("Select PDF File *", type=['pdf'])
                
                if st.form_submit_button("📤 Upload Document"):
                    if not doc_title or not doc_file: st.error("⚠️ Title and PDF file are required.")
                    else:
                        with get_db() as db:
                            try:
                                db.add(PolicyDocument(title=doc_title, academic_year=doc_year, file_name=doc_file.name, file_data=doc_file.read(), uploaded_by=st.session_state.get('logged_in_user')))
                                db.commit()
                                st.session_state['flash_msg'] = f"✅ Document uploaded!"
                                st.rerun()
                            except Exception as e:
                                db.rollback()
                                st.error(f"❌ Upload failed: {e}")
        else: st.error("🔒 **Access Denied**: Only Admins can upload policies.")
# =======================================================
# SECTION: Student Lookup
# =======================================================
elif selected_tab == "🔍 Student Lookup":
    st.subheader("🔍 Student Data Explorer")

    with st.form("lookup_search_form", clear_on_submit=False):
        current_lookup = str(st.session_state.get('lookup_id', '')) if st.session_state.get('lookup_id', 0) > 0 else ""
        search_id_raw = st.text_input("Enter Student ID to lookup profile:", value=current_lookup, placeholder="e.g. 26100123")
        lookup_submitted = st.form_submit_button("🔍 Lookup Profile")

    if lookup_submitted:
        st.session_state['lookup_id'] = int(search_id_raw) if search_id_raw.strip().isdigit() else 0

    search_lookup_id = st.session_state.get('lookup_id', 0)

    if search_lookup_id > 0:
        with get_db() as db:
            student = db.query(Student).filter_by(id=search_lookup_id).first()
            if student:
                st.info(f"✅ Profile found for: **{student.name}**")
                c1, c2, c3 = st.columns(3)
                c1.metric("College", student.college)
                c2.metric("Program", student.program if student.program else "N/A")
                c3.metric("Price / Credit Hour", f"{student.price_per_hr:,.2f} EGP")

                with st.expander("📝 Full Personal Details", expanded=True):
                    info_col1, info_col2 = st.columns(2)
                    info_col1.write(f"**Email:** {student.email}")
                    info_col1.write(f"**Mobile:** {student.mobile}")
                    info_col1.write(f"**Admit Year:** {student.admit_year}")
                    info_col2.write(f"**National ID:** {student.national_id}")
                    info_col2.write(f"**Nationality:** {student.nationality}")
                    info_col2.write(f"**Birth Date:** {student.birth_date}")

                st.markdown("---")
                st.subheader("📌 Academic Status (Term-Based)")
                
                def color_status(val):
                    color_map = {
                        'Active': 'background-color: #d4edda; color: #155724; font-weight: bold; border-radius: 5px;',
                        'Semester Withdraw': 'background-color: #fff3cd; color: #856404; font-weight: bold; border-radius: 5px;',
                        'Inactive': 'background-color: #f8d7da; color: #721c24; font-weight: bold; border-radius: 5px;',
                        'Graduated': 'background-color: #d1ecf1; color: #0c5460; font-weight: bold; border-radius: 5px;',
                        'Program Withdraw': 'background-color: #e2e3e5; color: #383d41; font-weight: bold; border-radius: 5px;'
                    }
                    return color_map.get(val, '')

                student_statuses = db.query(StudentStatus).filter_by(student_id=search_lookup_id).order_by(StudentStatus.academic_year.desc(), StudentStatus.term).all()
                if student_statuses:
                    df_statuses = pd.DataFrame([{"Term": st_stat.term, "Academic Year": st_stat.academic_year, "Status": st_stat.status} for st_stat in student_statuses])
                    st.dataframe(df_statuses.style.map(color_status, subset=['Status']), use_container_width=True, hide_index=True)
                else: st.info("No academic status history recorded for this student yet.")
                
                with st.expander("⚙️ Update/Add Status for a Term"):
                    with st.form("status_update_form"):
                        col_stat1, col_stat2, col_stat3 = st.columns(3)
                        stat_term = col_stat1.selectbox("Term:", VALID_TERMS)
                        stat_year = col_stat2.number_input("Year:", value=DEFAULT_YEAR, step=1)
                        stat_value = col_stat3.selectbox("Status:", VALID_STATUSES)
                        
                        if st.form_submit_button("💾 Save Status"):
                            existing_status = db.query(StudentStatus).filter_by(student_id=search_lookup_id, term=stat_term, academic_year=stat_year).first()
                            if existing_status: existing_status.status = stat_value
                            else: db.add(StudentStatus(student_id=search_lookup_id, term=stat_term, academic_year=stat_year, status=stat_value))
                            db.commit()
                            st.session_state['flash_msg'] = f"Status updated to {stat_value} for {stat_term} {stat_year}."
                            st.rerun()

                st.markdown("---")
                with st.expander("🎓 Active Scholarships (All Terms)", expanded=False):
                    student_schs_all = db.query(StudentScholarship, ScholarshipType).join(ScholarshipType).filter(StudentScholarship.student_id == search_lookup_id).order_by(StudentScholarship.academic_year.desc(), StudentScholarship.term).all()
                    if student_schs_all:
                        df_schs = pd.DataFrame([{"Term": ss.term, "Year": ss.academic_year, "Scholarship": st_type.name, "Percentage": f"{ss.percentage * 100 if ss.percentage <= 1 else ss.percentage:.1f}%", "Status": "✅ Active" if ss.is_active else "❌ Inactive"} for ss, st_type in student_schs_all])
                        st.dataframe(df_schs, use_container_width=True, hide_index=True)
                    else: st.info("No scholarships found for this student.")

                st.markdown("---")
                if st.session_state.get('user_role') in ['Admin', 'Editor']:
                    edit_mode = st.toggle("🔓 Unlock Edit Mode")
                    if edit_mode:
                        st.warning("⚠️ **CRITICAL WARNING:** You are modifying Master Data.")
                        col_e1, col_e2, col_e3 = st.columns(3)
                        e_name = col_e1.text_input("Full Name", value=student.name if student.name else "")
                        try: current_col_idx = VALID_COLLEGES.index(str(student.college).strip().upper()) if student.college else 0
                        except ValueError: current_col_idx = 0
                        e_college = col_e2.selectbox("College", VALID_COLLEGES, index=current_col_idx)
                        e_price = col_e3.number_input("Price Per Hr (EGP)", value=float(student.price_per_hr) if student.price_per_hr else 0.0, step=100.0)
                        
                        col_e4, col_e5, col_e6 = st.columns(3)
                        e_email = col_e4.text_input("Email", value=student.email if student.email else "")
                        e_mobile = col_e5.text_input("Mobile", value=student.mobile if student.mobile else "")
                        e_program = col_e6.text_input("Program", value=student.program if student.program else "")
                        
                        if st.button("💾 Save Changes", type="primary"):
                            try:
                                student.name, student.college, student.price_per_hr, student.email, student.mobile, student.program = e_name, e_college, e_price, e_email, e_mobile, e_program
                                db.commit()
                                st.session_state['flash_msg'] = "Student master data updated successfully!"
                                st.rerun()
                            except Exception as e:
                                db.rollback()
                                st.error(f"❌ Error: {e}")
            else: st.warning("⚠️ No student found with this ID.")

# =======================================================
# SECTION: Manual Operations
# =======================================================
elif selected_tab == "📊 Operations":
    st.subheader("Post Manual Transaction")
    if st.session_state.get('user_role') not in ['Admin', 'Editor']:
        st.warning("🔒 **Access Denied**: Only Admins and Editors can post transactions.")
    else:
        a_t = st.selectbox("Select Action Type", ["Payment Receipt", "Credit Hours Adjustment", "Other Fees", "General Adjustment"], index=0)
        
        # حزام الأمان: التحذير من التكرار (Duplicate Warning)
        confirm_duplicate = st.checkbox("⚠️ Bypass Duplicate Check (Force Posting)")
        
        with st.form(f"manual_tx_form_{a_t}", clear_on_submit=True):
            default_ops_id = str(st.session_state.get('lookup_id', '')) if st.session_state.get('lookup_id', 0) > 0 else ""
            sid_raw = st.text_input("Student ID", value=default_ops_id, placeholder="Enter ID (e.g., 26100123)...")
            
            c1, c2, c3 = st.columns(3)
            ed = c1.date_input("Date")
            et = c2.selectbox("Term", VALID_TERMS)
            ey = c3.number_input("Year", value=DEFAULT_YEAR)

            if a_t == "Payment Receipt":
                b_n = st.text_input("Bank Name")
                b_r = st.text_input("Ref No")
                amt = st.number_input("Amount Paid", min_value=0.0)
            elif a_t == "Credit Hours Adjustment":
                h = st.number_input("Hours Delta (+/-)")
            elif a_t == "Other Fees":
                amt = st.number_input("Fee Amount")
                dsc_input = st.text_input("Description")
            elif a_t == "General Adjustment":
                col_ga1, col_ga2 = st.columns(2)
                dr_input = col_ga1.number_input("Debit Amount (EGP)", min_value=0.0)
                cr_input = col_ga2.number_input("Credit Amount (EGP)", min_value=0.0)
                dsc_input = st.text_input("Description")

            if st.form_submit_button("🚀 Process Transaction"):
                sid = int(sid_raw) if sid_raw.strip().isdigit() else 0
                if sid == 0:
                    st.error("Please enter a valid Student ID.")
                else:
                    with get_db() as db:
                        s_d = db.query(Student).filter_by(id=sid).first()
                        if not s_d:
                            st.error("Student ID not found! Please register the student first.")
                        else:
                            rate = s_d.price_per_hr if s_d else 0.0
                            dr, cr, dsc, pfx, h_change, extra_txs = 0.0, 0.0, "", "TX", 0.0, []
                            m_id = get_next_ref_sequence(db)

                            if a_t == "Payment Receipt": pfx, cr, dsc = "PAY", amt, f"Bank: {b_n} | Ref: {b_r}"
                            elif a_t == "Credit Hours Adjustment":
                                pfx, h_change = "ADJ", h
                                val = abs(h * rate)
                                dr, cr = (val, 0) if h > 0 else (0, val)
                                dsc = f"Adj: {h} CH @ {rate:,.2f}"
                                extra_txs = build_auto_discount_transactions(db, student_id=sid, gross_amount=val, term=et, academic_year=int(ey), entry_date=ed, ref_start=m_id + 2)
                                if h < 0:
                                    for t in extra_txs: t.debit, t.credit = t.credit, t.debit
                            elif a_t == "Other Fees": pfx, dr, dsc = "INV", amt, dsc_input
                            elif a_t == "General Adjustment": pfx, dr, cr, dsc = "TXN", dr_input, cr_input, dsc_input

                            # فحص التكرار (Duplicate Logic)
                            check_val = dr if dr > 0 else cr
                            duplicate = db.query(Transaction).filter(
                                Transaction.student_id == sid, Transaction.transaction_type == a_t, 
                                Transaction.entry_date == ed, (Transaction.debit == check_val) | (Transaction.credit == check_val)
                            ).first()

                            if duplicate and not confirm_duplicate and check_val > 0:
                                st.error(f"🛑 Duplicate Warning: A {a_t} of {check_val} EGP was already posted today for this student. Check the 'Bypass Duplicate Check' box if you really want to post it again.")
                            else:
                                new_tx = Transaction(reference_no=f"{pfx}-{m_id+1:06d}", student_id=sid, transaction_type=a_t, description=dsc, debit=dr, credit=cr, hours_change=h_change, entry_date=ed, term=et, academic_year=ey)
                                db.add(new_tx)
                                for t in extra_txs: db.add(t)
                                db.commit()
                                
                                auto_info = f" + {len(extra_txs)} auto discount(s)" if extra_txs else ""
                                st.session_state['flash_msg'] = f"Posted: {new_tx.reference_no} for {s_d.name}{auto_info}!"
                                st.rerun()

# =======================================================
# SECTION: Bulk Financial Operations
# =======================================================
elif selected_tab == "📤 Bulk Financials":
    st.subheader("Bulk Financial Operations")
    if st.session_state.get('user_role') not in ['Admin', 'Editor']:
        st.warning("🔒 **Access Denied**: Only Admins and Editors can run bulk operations.")
    else:
        b_t = st.radio("Type: ", ["Bulk Payments", "Bulk Invoices (Tuition)", "Bulk Other Fees", "Credit Hours Adjustments", "Update Student Rates", "General Adjustments"], horizontal=True)
        st.warning("⚠️ **IMPORTANT:** DELETE the Example Row (ID: 0) before uploading.")

        ex = {
            "Bulk Payments": {"ID": 0, "Bank Name": "Bank", "Bank Ref": "REF123", "Amount": 0.0, "Date": "2026-04-17", "Term": VALID_TERMS[1], "Year": DEFAULT_YEAR},
            "Bulk Invoices (Tuition)": {"ID": 0, "Hours": 15.0, "Date": "2026-04-17", "Term": VALID_TERMS[1], "Year": DEFAULT_YEAR},
            "Bulk Other Fees": {"ID": 0, "Fee Amount": 1500.0, "Description": "Bus Subscription", "Date": "2026-04-17", "Term": VALID_TERMS[1], "Year": DEFAULT_YEAR},
            "Credit Hours Adjustments": {"ID": 0, "Hours_Delta": 3.0, "Date": "2026-04-17", "Term": VALID_TERMS[1], "Year": DEFAULT_YEAR},
            "Update Student Rates": {"ID": 0, "New_Price_Per_Hr": 5500.0},
            "General Adjustments": {"ID": 0, "Debit": 0.0, "Credit": 0.0, "Date": "2026-04-17", "Term": VALID_TERMS[1], "Year": DEFAULT_YEAR, "Description": "DELETE"}
        }

        buf_t = io.BytesIO()
        pd.DataFrame([ex[b_t]]).to_excel(buf_t, index=False)
        st.download_button(label="📥 Download Template", data=buf_t.getvalue(), file_name=f"Tpl_{b_t}.xlsx")

        u_f = st.file_uploader("Upload Excel File", type=['xlsx'], key="bulk_upload")
        
        # حزام الأمان: معاينة الملف قبل رفعه للـ Database (Batch Preview)
        if u_f:
            df_b = pd.read_excel(u_f)
            df_b.columns = [str(c).strip() for c in df_b.columns]
            for col in ['Amount', 'Hours', 'Hours_Delta', 'Fee Amount', 'Debit', 'Credit', 'New_Price_Per_Hr']:
                if col in df_b.columns: df_b[col] = pd.to_numeric(df_b[col].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0.0)

            st.markdown("### 👀 Batch Preview (First 5 Rows)")
            st.dataframe(df_b.head(5), use_container_width=True)
            st.info(f"📄 Total Rows to Process: **{len(df_b)}**")

            if st.button("✅ Confirm & Run Batch", type="primary"):
                current_batch_id = f"BCH-{datetime.now().strftime('%y%m%d-%H%M%S')}"
                total_rows = len(df_b)
                progress_bar = st.progress(0)
                status_text = st.empty()

                with get_db() as db:
                    failed_records, success_count = [], 0
                    rts = {s.id: s.price_per_hr for s in db.query(Student).all()} 

                    if b_t == "Update Student Rates":
                        for i, r in df_b.iterrows():
                            r_id = int(r.get('ID', 0)) if pd.notnull(r.get('ID')) else 0
                            original_row = r.to_dict()
                            if r_id <= 0:
                                original_row['Error Reason'] = "Invalid Student ID"
                                failed_records.append(original_row)
                            elif r_id not in rts:
                                original_row['Error Reason'] = "Student ID not registered"
                                failed_records.append(original_row)
                            else:
                                db.query(Student).filter(Student.id == r_id).update({"price_per_hr": float(r['New_Price_Per_Hr'])})
                                success_count += 1
                            progress_bar.progress((i + 1) / total_rows)
                            status_text.text(f"Processing record {i+1} of {total_rows}...")
                                
                        if success_count > 0:
                            db.commit()
                            st.success(f"✅ Successfully updated rates for {success_count} students!")
                    else:
                        m_id = get_next_ref_sequence(db)
                        bulk_l, tx_counter = [], 1

                        for i, r in df_b.iterrows():
                            sid = int(r.get('ID', 0)) if pd.notnull(r.get('ID')) else 0
                            original_row = r.to_dict()
                            
                            if sid <= 0 or sid not in rts:
                                original_row['Error Reason'] = "Invalid or unregistered Student ID"
                                failed_records.append(original_row)
                                progress_bar.progress((i + 1) / total_rows)
                                continue

                            rt = rts[sid]
                            dr, cr, pfx, h_change = 0.0, 0.0, "TX", 0.0
                            raw_desc = str(r.get('Description', '')).strip()
                            dsc = b_t if not raw_desc or raw_desc in ['0', '0.0', 'nan'] else raw_desc
                            term_val = str(r.get('Term', VALID_TERMS[1]))
                            year_val = int(r.get('Year', DEFAULT_YEAR)) if pd.notnull(r.get('Year')) else DEFAULT_YEAR

                            if b_t == "Bulk Payments":
                                pfx, cr, dsc = "PAY", float(str(r.get('Amount', 0)).replace(',', '').strip() or 0.0), f"Bank: {r.get('Bank Name')} | Ref: {r.get('Bank Ref')}"
                            elif b_t == "Bulk Invoices (Tuition)":
                                h_change = float(str(r.get('Hours', 15.0)).replace(',', '').strip() or 0.0)
                                pfx, dr, dsc = "INV", h_change * rt, f"Tuition Invoice ({h_change} CH)"
                            elif b_t == "Bulk Other Fees":
                                pfx, dr, dsc = "INV", float(str(r.get('Fee Amount', 0)).replace(',', '').strip() or 0.0), raw_desc if raw_desc and raw_desc not in ['0', '0.0', 'nan'] else "Other Fee"
                            elif b_t == "Credit Hours Adjustments":
                                h_change = float(str(r.get('Hours_Delta', 0)).replace(',', '').strip() or 0.0)
                                pfx, dsc = "ADJ", f"Adj {h_change} CH"
                                v = abs(h_change * rt)
                                dr, cr = (v, 0) if h_change > 0 else (0, v)
                            elif b_t == "General Adjustments":
                                pfx, dr, cr = "TXN", float(str(r.get('Debit', 0)).replace(',', '').strip() or 0.0), float(str(r.get('Credit', 0)).replace(',', '').strip() or 0.0)

                            new_bulk_tx = Transaction(
                                reference_no=f"{pfx}-{m_id+tx_counter:06d}", batch_id=current_batch_id, student_id=sid, scholarship_type_id=None, transaction_type=b_t, description=dsc,
                                debit=dr, credit=cr, hours_change=h_change, entry_date=pd.to_datetime(r.get('Date', datetime.now())).date(), term=term_val, academic_year=year_val
                            )
                            bulk_l.append(new_bulk_tx)
                            success_count += 1
                            tx_counter += 1

                            if b_t in ["Bulk Invoices (Tuition)", "Credit Hours Adjustments"]:
                                inv_amount = dr if b_t == "Bulk Invoices (Tuition)" else v
                                auto_discounts = build_auto_discount_transactions(db, student_id=sid, gross_amount=inv_amount, term=term_val, academic_year=year_val, entry_date=pd.to_datetime(r.get('Date')).date(), ref_start=m_id + tx_counter, batch_id=current_batch_id)
                                if b_t == "Credit Hours Adjustments" and h_change < 0:
                                    for t in auto_discounts: t.debit, t.credit = t.credit, t.debit
                                bulk_l.extend(auto_discounts)
                                tx_counter += len(auto_discounts)

                            progress_bar.progress((i + 1) / total_rows)
                            status_text.text(f"Processing record {i+1} of {total_rows}...")

                        if bulk_l:
                            db.bulk_save_objects(bulk_l)
                            db.commit()
                            st.success(f"✅ Batch Posted! ({success_count} transactions)")

                status_text.empty()
                if failed_records:
                    st.error(f"⚠️ {len(failed_records)} records failed or were skipped.")
                    st.dataframe(pd.DataFrame(failed_records), use_container_width=True)
                    buf_err = io.BytesIO()
                    pd.DataFrame(failed_records).to_excel(buf_err, index=False)
                    st.download_button(label="⬇️ Download Error Report", data=buf_err.getvalue(), file_name=f"Failed_Transactions_{datetime.now().strftime('%Y%m%d%H%M')}.xlsx", use_container_width=True)

# =======================================================
# SECTION: Scholarships Management
# =======================================================
elif selected_tab == "🎓 Scholarships":
    st.subheader("🎓 Student Scholarships Management")
    if st.session_state.get('user_role') not in ['Admin', 'Editor']:
        st.warning("🔒 **Access Denied**: You can only view statements. You don't have permission to manage scholarships.")
    else:
        sch_action = st.radio("Action: ", ["View / Edit", "Add Scholarship", "Bulk Upload Scholarships", "🔄 Sync & Recalculate", "📊 Scholarships Report"], horizontal=True)

        if sch_action == "View / Edit":
            with st.form("sch_lookup_form", clear_on_submit=False):
                sch_sid_raw = st.text_input("Student ID:", placeholder="e.g. 26100123")
                col_a, col_b = st.columns(2)
                sch_term = col_a.selectbox("Term: ", VALID_TERMS)
                sch_year = col_b.number_input("Academic Year: ", value=DEFAULT_YEAR, step=1)
                
                if st.form_submit_button("🔍 Load Scholarships"):
                    st.session_state['sch_lookup_params'] = {'sid': int(sch_sid_raw) if sch_sid_raw.strip().isdigit() else 0, 'term': sch_term, 'year': int(sch_year)}

            if st.session_state.get('sch_lookup_params') and st.session_state['sch_lookup_params']['sid'] > 0:
                p = st.session_state['sch_lookup_params']
                with get_db() as db:
                    student = db.query(Student).filter_by(id=p['sid']).first()
                    if not student: st.warning("⚠️ Student not found.")
                    else:
                        st.info(f"Student: **{student.name}** | Term: {p['term']} {p['year']}")
                        student_schs = db.query(StudentScholarship, ScholarshipType).join(ScholarshipType).filter(StudentScholarship.student_id == p['sid'], StudentScholarship.term == p['term'], StudentScholarship.academic_year == p['year']).all()
                        
                        if student_schs:
                            for ss, st_type in student_schs:
                                pct_display = ss.percentage * 100 if ss.percentage <= 1.0 else ss.percentage
                                c_1, c_2, c_3 = st.columns([4, 2, 2])
                                c_1.write(f"**{st_type.name}**")
                                c_2.write(f"{pct_display:.1f}%")
                                c_3.write("✅ Active" if ss.is_active else "🔴 Inactive")
                                
                                with st.expander(f"⚙️ Manage '{st_type.name}'"):
                                    if ss.is_active:
                                        if st.button("Stop Future Only", key=f"stop_fut_{ss.id}"):
                                            ss.is_active = False
                                            db.commit()
                                            st.rerun()
                                        if st.session_state.get('user_role') == 'Admin':
                                            confirm_rev = st.checkbox(f"⚠️ Confirm Reverse", key=f"chk_rev_{ss.id}")
                                            if st.button("Stop & Reverse Past", key=f"stop_rev_{ss.id}") and confirm_rev:
                                                ss.is_active = False
                                                db.commit()
                                                r_tx, _ = get_retroactive_scholarship_tx(db, p['sid'], p['term'], p['year'], ss.scholarship_type_id, st_type.name, 0.0, get_next_ref_sequence(db)+1)
                                                if r_tx:
                                                    db.add(r_tx)
                                                    db.commit()
                                                st.rerun()
                                    else:
                                        if st.button("Activate Scholarship", key=f"act_{ss.id}"):
                                            ss.is_active = True
                                            db.commit()
                                            enforce_scholarship_cap(db, p['sid'], p['term'], p['year'])
                                            db.commit()
                                            if db.query(StudentScholarship.is_active).filter_by(id=ss.id).scalar():
                                                r_tx, _ = get_retroactive_scholarship_tx(db, p['sid'], p['term'], p['year'], ss.scholarship_type_id, st_type.name, ss.percentage * 100.0 if ss.percentage <= 1.0 else ss.percentage, get_next_ref_sequence(db)+1)
                                                if r_tx:
                                                    db.add(r_tx)
                                                    db.commit()
                                            st.rerun()
                        else: st.info("No scholarships found.")

        elif sch_action == "Add Scholarship":
            with st.form("add_sch_form", clear_on_submit=True):
                col1, col2, col3 = st.columns(3)
                add_sid = col1.number_input("Student ID:", min_value=1, step=1)
                add_term = col2.selectbox("Term: ", VALID_TERMS)
                add_year = col3.number_input("Academic Year:", value=DEFAULT_YEAR, step=1)
                add_type = st.selectbox("Scholarship Type:", list(sch_map.keys()))
                add_pct = st.number_input("Percentage:", min_value=0.0, max_value=100.0, step=5.0)
                
                if st.form_submit_button("➕ Add Scholarship"):
                    with get_db() as db:
                        if not db.query(Student).filter_by(id=add_sid).first(): st.error("❌ Student not found!")
                        else:
                            existing = db.query(StudentScholarship).filter_by(student_id=add_sid, scholarship_type_id=sch_map[add_type], term=add_term, academic_year=add_year).first()
                            if existing: existing.percentage, existing.is_active = add_pct, True
                            else: db.add(StudentScholarship(student_id=add_sid, scholarship_type_id=sch_map[add_type], percentage=add_pct, term=add_term, academic_year=add_year, is_active=True))
                            enforce_scholarship_cap(db, add_sid, add_term, add_year)
                            db.commit()
                            if db.query(StudentScholarship.is_active).filter_by(student_id=add_sid, scholarship_type_id=sch_map[add_type], term=add_term, academic_year=add_year).scalar():
                                r_tx, _ = get_retroactive_scholarship_tx(db, add_sid, add_term, add_year, sch_map[add_type], add_type, add_pct * 100.0 if add_pct <= 1.0 else add_pct, get_next_ref_sequence(db)+1)
                                if r_tx:
                                    db.add(r_tx)
                                    db.commit()
                            st.session_state['flash_msg'] = "Processed successfully!"
                            st.rerun()

        elif sch_action == "Bulk Upload Scholarships":
            st.info("💡 Ensure exact match of Scholarship Name.")
            sch_template = {"Student ID": 26100123, "Scholarship Name": list(sch_map.keys())[0] if sch_map else "SCH", "Percentage": 60.0, "Term": VALID_TERMS[1], "Academic Year": DEFAULT_YEAR}
            buf_sch_tpl = io.BytesIO()
            pd.DataFrame([sch_template]).to_excel(buf_sch_tpl, index=False)
            st.download_button(label="📥 Download Template", data=buf_sch_tpl.getvalue(), file_name="Template_Scholarships.xlsx")
            
            u_sch = st.file_uploader("Upload Scholarships Excel", type=['xlsx'])
            if u_sch and st.button("🚀 Upload Scholarships"):
                with st.spinner("Processing..."):
                    df_sch = pd.read_excel(u_sch)
                    df_sch.columns = [str(c).strip() for c in df_sch.columns]
                    
                    with get_db() as db:
                        uploaded_data, failed_records, processed_combos, valid_ids = [], [], set(), {s[0] for s in db.query(Student.id).all()}
                        for _, r in df_sch.iterrows():
                            sid = int(r.get('Student ID', 0)) if pd.notnull(r.get('Student ID')) else 0
                            s_name, pct, trm, yr = str(r.get('Scholarship Name', '')).strip(), float(r.get('Percentage', 0)), str(r.get('Term', VALID_TERMS[1])).strip(), int(r.get('Academic Year', DEFAULT_YEAR))
                            s_type_id = sch_map.get(s_name)
                            
                            if sid <= 0 or sid not in valid_ids or not s_type_id or pct <= 0:
                                failed_records.append(r.to_dict())
                                continue
                                
                            existing = db.query(StudentScholarship).filter_by(student_id=sid, scholarship_type_id=s_type_id, term=trm, academic_year=yr).first()
                            if existing: existing.percentage, existing.is_active = pct, True
                            else: db.add(StudentScholarship(student_id=sid, scholarship_type_id=s_type_id, percentage=pct, term=trm, academic_year=yr, is_active=True))
                            
                            uploaded_data.append((sid, s_type_id, s_name, pct, trm, yr))
                            processed_combos.add((sid, trm, yr))
                            
                        db.commit()
                        for sid, trm, yr in processed_combos: enforce_scholarship_cap(db, sid, trm, yr)
                        db.commit()

                        retro_txs, curr_c, batch_id = [], get_next_ref_sequence(db) + 1, f"BCH-SCH-{datetime.now().strftime('%y%m%d-%H%M%S')}"
                        for sid, s_type_id, s_name, pct, trm, yr in uploaded_data:
                            if db.query(StudentScholarship.is_active).filter_by(student_id=sid, scholarship_type_id=s_type_id, term=trm, academic_year=yr).scalar():
                                r_tx, curr_c = get_retroactive_scholarship_tx(db, sid, trm, yr, s_type_id, s_name, pct * 100.0 if pct <= 1.0 else pct, curr_c, batch_id)
                                if r_tx: retro_txs.append(r_tx)

                        if retro_txs:
                            db.bulk_save_objects(retro_txs)
                            db.commit()
                            
                        st.success(f"✅ Done! Added/Updated {len(uploaded_data)} | Retro Applied: {len(retro_txs)}")
                        if failed_records:
                            st.error(f"⚠️ {len(failed_records)} records failed.")
                            st.dataframe(pd.DataFrame(failed_records))
                            buf_err_sch = io.BytesIO()
                            pd.DataFrame(failed_records).to_excel(buf_err_sch, index=False)
                            st.download_button("⬇️ Download Errors", data=buf_err_sch.getvalue(), file_name="Failed_SCH.xlsx")

        elif sch_action == "🔄 Sync & Recalculate":
            st.info("💡 **Fix Missing Discounts:** Use this tool to scan a specific term and apply missing discounts retroactively if invoices were posted *after* scholarships.")
            with st.form("recalc_form"):
                c_r1, c_r2 = st.columns(2)
                r_term = c_r1.selectbox("Term to Scan:", VALID_TERMS)
                r_year = c_r2.number_input("Academic Year:", value=DEFAULT_YEAR, step=1)
                if st.form_submit_button("🚀 Run Auto-Sync"):
                    with st.spinner(f"Scanning and syncing {r_term} {r_year} records..."):
                        with get_db() as db:
                            active_schs = db.query(StudentScholarship, ScholarshipType).join(ScholarshipType).filter(StudentScholarship.term == r_term, StudentScholarship.academic_year == r_year, StudentScholarship.is_active == True).all()
                            if not active_schs: st.warning(f"No active scholarships found.")
                            else:
                                curr_c, batch_id, retro_txs = get_next_ref_sequence(db) + 1, f"BCH-SYNC-{datetime.now().strftime('%y%m%d-%H%M%S')}", []
                                for ss, st_type in active_schs:
                                    r_tx, curr_c = get_retroactive_scholarship_tx(db, ss.student_id, r_term, r_year, ss.scholarship_type_id, st_type.name, ss.percentage * 100.0 if ss.percentage <= 1.0 else ss.percentage, curr_c, batch_id)
                                    if r_tx: retro_txs.append(r_tx)
                                if retro_txs:
                                    db.bulk_save_objects(retro_txs)
                                    db.commit()
                                    st.success(f"✅ Sync Complete! Applied **{len(retro_txs)}** missing discount transactions.")
                                else: st.success("✅ Sync Complete! All discounts are perfectly aligned.")

        elif sch_action == "📊 Scholarships Report":
            if st.button("📂 Generate Scholarship Report"):
                with st.spinner("Compiling comprehensive report..."):
                    sql = text("""
                        SELECT s.id AS "Student ID", s.name AS "Student Name", s.college AS "College", ss.term AS "Term", ss.academic_year AS "Year", st.name AS "Scholarship Name", ss.percentage AS "Configured %", 
                            CASE WHEN ss.is_active THEN 'Active' ELSE 'Inactive' END AS "Status", 
                            COALESCE((SELECT SUM(t.debit - t.credit) FROM transactions t WHERE t.student_id = s.id AND t.term = ss.term AND t.academic_year = ss.academic_year AND t.transaction_type IN ('Invoice', 'Bulk Invoices (Tuition)', 'Credit Hours Adjustment', 'Credit Hours Adjustments')), 0) AS "Total Tuition Billed (EGP)", 
                            COALESCE((SELECT SUM(t.credit - t.debit) FROM transactions t WHERE t.student_id = s.id AND t.term = ss.term AND t.academic_year = ss.academic_year AND t.reference_no LIKE 'SCH-%' AND t.scholarship_type_id = ss.scholarship_type_id), 0) AS "Actual Discount Applied (EGP)" 
                        FROM student_scholarships ss JOIN students s ON ss.student_id = s.id JOIN scholarship_types st ON ss.scholarship_type_id = st.id 
                        ORDER BY ss.academic_year DESC, ss.term, s.id
                    """)
                    df_rep = pd.read_sql(sql, con=engine)
                    if not df_rep.empty:
                        st.dataframe(df_rep.style.format({"Configured %": "{:.1f}", "Total Tuition Billed (EGP)": "{:,.2f}", "Actual Discount Applied (EGP)": "{:,.2f}"}), use_container_width=True)
                        buf_rep = io.BytesIO()
                        df_rep.to_excel(buf_rep, index=False)
                        st.download_button(label="📗 Download Excel Report", data=buf_rep.getvalue(), file_name="Scholarships_Report.xlsx", use_container_width=True)
                    else: st.info("⚠️ No scholarships configured.")

# =======================================================
# SECTION: Registration
# =======================================================
elif selected_tab == "👤 Registration":
    st.subheader("👤 New Student Registration")
    if st.session_state.get('user_role') not in ['Admin', 'Editor']:
        st.warning("🔒 **Access Denied**: Only Admins and Editors can register new students.")
    else:
        reg_mode = st.radio("Registration Type:", ["Manual Entry", "Bulk Upload (Excel)"], horizontal=True)
        
        if reg_mode == "Manual Entry":
            with st.form("manual_reg", clear_on_submit=True):
                st.info(f"💡 **Valid College Codes:** `{', '.join(VALID_COLLEGES)}`")
                col_s1, col_s2, col_s3 = st.columns(3)
                n_id = col_s1.number_input("Student ID", value=None, placeholder="(e.g., 26100123)", step=1, format="%d")
                n_name = col_s2.text_input("Full Name *")
                n_college = col_s3.selectbox("College Code *", VALID_COLLEGES)
                
                col_s4, col_s5, col_s6 = st.columns(3)
                n_program = col_s4.text_input("Program")
                n_price = col_s5.number_input("Fixed Price Per Credit Hour (EGP) *", min_value=0.0, step=100.0, format="%.2f")
                n_email = col_s6.text_input("University Email")
                
                col_s7, col_s8, col_s9 = st.columns(3)
                n_mobile = col_s7.text_input("Mobile Number")
                n_nat_id = col_s8.text_input("National ID")
                n_nationality = col_s9.text_input("Nationality", value="Egyptian")
                
                col_s10, col_s11 = st.columns(2)
                n_dob = col_s10.date_input("Birth Date", min_value=datetime(1990, 1, 1), value=datetime(2005, 1, 1))
                n_admit = col_s11.number_input("Admit Year", value=DEFAULT_YEAR, step=1)
                
                if st.form_submit_button("💾 Register Student"):
                    if n_id is None or not n_name or not n_college: st.error("⚠️ Student ID, Name, and College are required fields!")
                    else:
                        with get_db() as db:
                            if db.query(Student).filter_by(id=n_id).first(): st.error("⚠️ Student ID already exists!")
                            else:
                                try:
                                    db.add(Student(id=n_id, name=n_name, college=n_college, program=n_program, price_per_hr=n_price, email=n_email, mobile=n_mobile, national_id=n_nat_id, nationality=n_nationality, admit_year=n_admit, birth_date=n_dob))
                                    db.commit()
                                    st.session_state['flash_msg'] = f"Student '{n_name}' has been registered!"
                                    st.rerun()
                                except Exception as e:
                                    db.rollback()
                                    st.error(f"❌ Error: {e}")
        else:
            std_ex = {"ID": 26100123, "Name": "Ahmed Ali", "College": "ENG", "Program": "Computer Eng", "Price Per Hr": 4600.0, "Email": "ahmed@nu.edu.eg", "Mobile": "01000000000", "National ID": "29901010000000", "Nationality": "Egyptian", "Admit Year": DEFAULT_YEAR, "Birth Date": "2005-01-01"}
            buf_std = io.BytesIO()
            pd.DataFrame([std_ex]).to_excel(buf_std, index=False)
            st.download_button(label="📥 Download Students Template", data=buf_std.getvalue(), file_name="Template_Bulk_Students.xlsx")
            
            u_std = st.file_uploader("Upload Students Excel", type=['xlsx'])
            if u_std and st.button("🚀 Process Bulk Registration"):
                df_std = pd.read_excel(u_std)
                df_std.columns = [str(c).strip() for c in df_std.columns]
                total_rows = len(df_std)
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                with get_db() as db:
                    existing_ids = {s[0] for s in db.query(Student.id).all()}
                    new_students, failed_records, success_count = [], [], 0
                    for i, r in df_std.iterrows():
                        sid = int(r.get('ID', 0)) if pd.notnull(r.get('ID')) else 0
                        row_dict = r.to_dict()
                        if sid <= 0 or sid in existing_ids:
                            row_dict['Error Reason'] = "Invalid or Duplicate ID"
                            failed_records.append(row_dict)
                            progress_bar.progress((i + 1) / total_rows)
                            continue
                            
                        raw_college = str(r.get('College', '')).strip().upper()
                        if raw_college not in VALID_COLLEGES:
                            row_dict['Error Reason'] = f"Invalid College. Allowed: {', '.join(VALID_COLLEGES)}"
                            failed_records.append(row_dict)
                            progress_bar.progress((i + 1) / total_rows)
                            continue
                            
                        bd_dt = pd.to_datetime(r.get('Birth Date'), errors='coerce')
                        new_students.append(Student(id=sid, name=str(r.get('Name', 'Unknown')), college=raw_college, program=str(r.get('Program', '')), price_per_hr=float(r.get('Price Per Hr', 0.0)), email=str(r.get('Email', '')), mobile=str(r.get('Mobile', '')), national_id=str(r.get('National ID', '')), nationality=str(r.get('Nationality', 'Egyptian')), admit_year=int(r.get('Admit Year', DEFAULT_YEAR)), birth_date=bd_dt.date() if pd.notna(bd_dt) else None))
                        success_count += 1
                        progress_bar.progress((i + 1) / total_rows)
                        status_text.text(f"Processing record {i+1} of {total_rows}...")
                        
                    if new_students:
                        try:
                            db.add_all(new_students)
                            db.commit()
                            st.success(f"✅ Successfully registered {success_count} new students!")
                        except Exception as e:
                            db.rollback()
                            st.error(f"❌ Database Error: {e}")
                    elif not failed_records: st.warning("⚠️ No data found.")
                        
                status_text.empty()
                if failed_records:
                    st.error(f"⚠️ {len(failed_records)} records failed or skipped.")
                    st.dataframe(pd.DataFrame(failed_records), use_container_width=True)
                    buf_err = io.BytesIO()
                    pd.DataFrame(failed_records).to_excel(buf_err, index=False)
                    st.download_button(label="⬇️ Download Error Report", data=buf_err.getvalue(), file_name=f"Failed_Registrations.xlsx", use_container_width=True)

# =======================================================
# SECTION: Batch Management
# =======================================================
elif selected_tab == "🗑️ Batch Management":
    st.subheader("🗑️ Batch Management")
    batch_action = st.radio("Action: ", ["📂 View Active Batches", "📥 Export Batch Details", "🗑️ Delete Batch (Admin Only)", "📜 Deleted Batches History"], horizontal=True)
    
    with get_db() as db:
        batch_summary = db.query(Transaction.batch_id, Transaction.transaction_type, func.count(Transaction.id).label("record_count"), func.sum(Transaction.debit).label("total_debit"), func.sum(Transaction.credit).label("total_credit"), func.max(Transaction.created_at).label("upload_date")).filter(Transaction.batch_id.isnot(None)).group_by(Transaction.batch_id, Transaction.transaction_type).order_by(func.max(Transaction.created_at).desc()).all()

        if batch_action == "📂 View Active Batches":
            if batch_summary:
                df_batches = pd.DataFrame([{"Batch ID": b.batch_id, "Type": b.transaction_type, "Records": b.record_count, "Total Debit": f"{b.total_debit:,.2f}", "Total Credit": f"{b.total_credit:,.2f}", "Uploaded At": b.upload_date.strftime('%Y-%m-%d %H:%M:%S') if b.upload_date else "N/A"} for b in batch_summary])
                st.dataframe(df_batches, use_container_width=True)
            else: st.info("No active batches found.")
                
        elif batch_action == "📥 Export Batch Details":
            if batch_summary:
                sel_batch = st.text_input("📝 Enter or Paste Batch ID to Export:", placeholder="e.g. BCH-260417-153000")
                if st.button("📥 Load Batch"):
                    sel_batch = sel_batch.strip()
                    if not sel_batch: st.warning("Please enter a valid Batch ID.")
                    else:
                        sql_batch = text('SELECT t.reference_no AS "Ref No", s.id AS "Student ID", s.name AS "Student Name", t.transaction_type AS "Type", t.description AS "Description", t.entry_date AS "Date", t.term AS "Term", t.academic_year AS "Year", t.hours_change AS "Hours", t.debit AS "Debit", t.credit AS "Credit" FROM transactions t JOIN students s ON t.student_id = s.id WHERE t.batch_id = :b_id ORDER BY t.id ASC')
                        df_ex = pd.read_sql(sql_batch, con=engine, params={"b_id": sel_batch})
                        if not df_ex.empty:
                            st.success(f"✅ Found {len(df_ex)} records for Batch: {sel_batch}")
                            st.dataframe(df_ex.style.format({"Hours": "{:,.1f}", "Debit": "{:,.2f}", "Credit": "{:,.2f}"}), use_container_width=True)
                            buf_ex_batch = io.BytesIO()
                            df_ex.to_excel(buf_ex_batch, index=False)
                            st.download_button(label="📗 Download Batch Excel File", data=buf_ex_batch.getvalue(), file_name=f"Batch_Export_{sel_batch}.xlsx", use_container_width=True)
                        else: st.error("❌ Batch ID not found.")
            else: st.info("No active batches available.")
                
        elif batch_action == "🗑️ Delete Batch (Admin Only)":
            if st.session_state.get('user_role') == 'Admin':
                if batch_summary:
                    with st.form("del_batch", clear_on_submit=True):
                        b_del = st.text_input("🗑️ Enter or Paste Batch ID to Delete:", placeholder="e.g. BCH-260417-153000")
                        confirm_checkbox = st.checkbox("⚠️ I confirm that I want to completely delete this exact Batch ID.")
                        if st.form_submit_button("🗑️ Delete Batch"):
                            b_del = b_del.strip()
                            if not b_del or not confirm_checkbox: st.error("⚠️ Please enter the Batch ID and confirm.")
                            else:
                                recs = [b for b in batch_summary if b.batch_id == b_del]
                                if not recs: st.error(f"❌ Batch ID '{b_del}' not found!")
                                else:
                                    try:
                                        db.add(DeletedBatchLog(batch_id=b_del, transaction_type=" & ".join(list(set(b.transaction_type for b in recs))), record_count=sum(b.record_count for b in recs), total_debit=sum(b.total_debit for b in recs), total_credit=sum(b.total_credit for b in recs), deleted_by=st.session_state.get('logged_in_user')))
                                        db.query(Transaction).filter(Transaction.batch_id == b_del).delete()
                                        db.commit()
                                        st.session_state['flash_msg'] = f"Successfully deleted batch {b_del}."
                                        st.rerun()
                                    except Exception as e:
                                        db.rollback()
                                        st.error(f"❌ Error: {e}")
            else: st.error("🔒 **Access Denied**: Only System Admins can delete batches.")
                
        elif batch_action == "📜 Deleted Batches History":
            deleted_logs = db.query(DeletedBatchLog).order_by(DeletedBatchLog.deleted_at.desc()).all()
            if deleted_logs: st.dataframe(pd.DataFrame([{"Batch ID": l.batch_id, "Type(s)": l.transaction_type, "Records": l.record_count, "Total Debit": f"{l.total_debit:,.2f}", "Total Credit": f"{l.total_credit:,.2f}", "Deleted By": l.deleted_by, "Deleted At": l.deleted_at.strftime('%Y-%m-%d %H:%M:%S')} for l in deleted_logs]), use_container_width=True)
            else: st.info("No deleted batches history found.")

# =======================================================
# SECTION: System Admin
# =======================================================
elif selected_tab == "⚙️ System Admin":
    st.subheader("⚙️ System Administration & Access Control")
    if st.session_state.get('user_role') != 'Admin':
        st.error("🔒 **Access Denied**: Only System Administrators can access User Management.")
    else:
        admin_action = st.radio("Action:", ["👥 Manage Users", "➕ Add New User", "🛠️ Database Fixes", "💾 System Backup"], horizontal=True)
        with get_db() as db:
            if admin_action == "👥 Manage Users":
                users = db.query(SystemUser).order_by(SystemUser.id).all()
                st.markdown("### 👨‍💻 Current System Users")
                for u in users:
                    with st.expander(f"👤 {u.username} - Role: {u.role} - Status: {'🟢 Active' if u.is_active else '🔴 Disabled'}"):
                        with st.form(f"edit_user_{u.id}"):
                            col_u1, col_u2, col_u3 = st.columns(3)
                            new_role = col_u1.selectbox("Role", ["Admin", "Editor", "Viewer"], index=["Admin", "Editor", "Viewer"].index(u.role))
                            new_status = col_u2.checkbox("Account Active", value=u.is_active)
                            new_pwd = col_u3.text_input("Reset Password (leave blank to keep current)", type="password")
                            if st.form_submit_button("💾 Save Changes"):
                                if new_pwd: u.password_hash = hash_pw(new_pwd)
                                u.role, u.is_active = new_role, new_status
                                db.commit()
                                st.success(f"✅ User '{u.username}' updated successfully!")
                                st.rerun()
                                
            elif admin_action == "➕ Add New User":
                with st.form("add_user_form"):
                    col_a1, col_a2 = st.columns(2)
                    n_user = col_a1.text_input("New Username *")
                    n_pwd = col_a2.text_input("Temporary Password *", type="password")
                    n_role = st.selectbox("Assign Role *", ["Admin", "Editor", "Viewer"], index=1)
                    
                    if st.form_submit_button("🚀 Create User"):
                        if not n_user or not n_pwd: st.error("⚠️ Username and Password are required!")
                        # حزام الأمان: التحقق من اليوزر بدون حساسية لحالة الأحرف
                        elif db.query(SystemUser).filter(func.lower(SystemUser.username) == n_user.lower()).first():
                            st.error("⚠️ Username already exists (Case-Insensitive). Choose another one.")
                        else:
                            db.add(SystemUser(username=n_user.strip(), password_hash=hash_pw(n_pwd), role=n_role, is_active=True))
                            db.commit()
                            st.session_state['flash_msg'] = f"User '{n_user}' created successfully!"
                            st.rerun()
                            
            elif admin_action == "🛠️ Database Fixes":
                st.markdown("### 🧹 Fix College Names (Data Cleansing)")
                if st.button("🚀 Run College Name Fix", type="primary"):
                    with st.spinner("Cleaning database..."):
                        fixed_count = 0
                        for s in db.query(Student).all():
                            if s.college and s.college != s.college.strip().upper():
                                s.college = s.college.strip().upper()
                                fixed_count += 1
                        if fixed_count > 0:
                            db.commit()
                            st.success(f"✅ Successfully fixed and merged {fixed_count} student records!")
                        else: st.success("✅ Database is already clean.")
                              
