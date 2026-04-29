import os
import re
import base64
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Date, Boolean, LargeBinary
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func, text
from datetime import datetime
from fpdf import FPDF
import io

# =======================================================
# 1. Database Configuration
# =======================================================
DB_URL = st.secrets["DB_URL"]
DEFAULT_YEAR = 2026

engine = create_engine(DB_URL, pool_size=5, max_overflow=10, pool_pre_ping=True)
Base = declarative_base()

# =======================================================
# 2. Database Models
# =======================================================
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

Session = sessionmaker(bind=engine)
session = Session()

try:
    sch_map = {sch.name: sch.id for sch in session.query(ScholarshipType).all()}
    all_colleges = [c[0] for c in session.query(Student.college).distinct().all() if c[0]]
    available_years = [y[0] for y in session.query(Transaction.academic_year).distinct().all() if y[0]] or [DEFAULT_YEAR]
except:
    sch_map = {}
    all_colleges = []
    available_years = [DEFAULT_YEAR]

# =======================================================
# 3. Core Helper: Auto-Discount Transactions
# =======================================================
def get_student_scholarships(student_id, term, academic_year):
    results = (
        session.query(StudentScholarship, ScholarshipType)
        .join(ScholarshipType, StudentScholarship.scholarship_type_id == ScholarshipType.id)
        .filter(
            StudentScholarship.student_id == student_id,
            StudentScholarship.term == term,
            StudentScholarship.academic_year == academic_year,
            StudentScholarship.is_active == True
        )
        .all()
    )
    return [
        {
            'scholarship_type_id': ss.scholarship_type_id,
            'name': st_type.name,
            'percentage': ss.percentage
        }
        for ss, st_type in results
    ]

def build_auto_discount_transactions(student_id, gross_amount, term, academic_year, entry_date, ref_start, batch_id=None):
    scholarships = get_student_scholarships(student_id, term, academic_year)
    if not scholarships:
        return []

    discount_txs = []
    accumulated_pct = 0.0
    counter = ref_start

    for sch in scholarships:
        pct = sch['percentage']
        requested_pct = pct * 100.0 if pct <= 1.0 else pct

        if requested_pct <= 0:
            continue

        available_pct = max(0.0, 100.0 - accumulated_pct)
        actual_pct = min(requested_pct, available_pct)
        accumulated_pct += actual_pct

        credit_val = gross_amount * (actual_pct / 100.0)
        desc = f"Scholarship: {sch['name']} ({actual_pct}%)"
        if actual_pct < requested_pct:
            desc += f" (Capped from {requested_pct}%)"

        tx = Transaction(
            reference_no=f"SCH-{counter:06d}",
            batch_id=batch_id,
            student_id=student_id,
            scholarship_type_id=sch['scholarship_type_id'],
            transaction_type='Discount',
            description=desc,
            hours_change=0.0,
            debit=0.0,
            credit=credit_val,
            entry_date=entry_date,
            term=term,
            academic_year=academic_year
        )
        discount_txs.append(tx)
        counter += 1

        if accumulated_pct >= 100.0:
            break

    return discount_txs

def get_retroactive_scholarship_tx(db_session, student_id, term, academic_year, sch_type_id, sch_name, requested_pct, current_counter, batch_id=None):
    tuition_types = ['Invoice', 'Bulk Invoices (Tuition)', 'Credit Hours Adjustment', 'Credit Hours Adjustments']
    
    net_billed = db_session.query(func.sum(Transaction.debit - Transaction.credit)).filter(
        Transaction.student_id == student_id,
        Transaction.term == term,
        Transaction.academic_year == academic_year,
        Transaction.transaction_type.in_(tuition_types)
    ).scalar() or 0.0

    if net_billed <= 0:
        return None, current_counter

    existing_other_txs = db_session.query(Transaction.description).filter(
        Transaction.student_id == student_id,
        Transaction.term == term,
        Transaction.academic_year == academic_year,
        Transaction.reference_no.like('SCH-%'),
        Transaction.scholarship_type_id != sch_type_id
    ).all()
    
    other_pct = 0.0
    for tx in existing_other_txs:
        m = re.search(r'\((\d+(\.\d+)?)%\)', tx[0])
        if m:
            other_pct += float(m.group(1))
            
    available_pct = max(0.0, 100.0 - other_pct)
    actual_pct = min(requested_pct, available_pct)

    target_discount = net_billed * (actual_pct / 100.0)
    
    existing_discount = db_session.query(func.sum(Transaction.credit - Transaction.debit)).filter(
        Transaction.student_id == student_id,
        Transaction.term == term,
        Transaction.academic_year == academic_year,
        Transaction.scholarship_type_id == sch_type_id,
        Transaction.reference_no.like('SCH-%')
    ).scalar() or 0.0

    diff = target_discount - existing_discount

    if abs(diff) > 0.01:
        desc = f"Retroactive: {sch_name} ({actual_pct}%)"
        if actual_pct < requested_pct:
            desc += f" (Capped from {requested_pct}%)"

        tx = Transaction(
            reference_no=f"SCH-{current_counter:06d}",
            batch_id=batch_id,
            student_id=student_id,
            scholarship_type_id=sch_type_id,
            transaction_type='Discount',
            description=desc,
            debit=abs(diff) if diff < 0 else 0.0,
            credit=diff if diff > 0 else 0.0,
            hours_change=0.0,
            entry_date=datetime.now().date(),
            term=term,
            academic_year=academic_year
        )
        return tx, current_counter + 1

    return None, current_counter

# =======================================================
# 4. Authentication & Helper Functions
# =======================================================
USERS = {
    "abdo_finance": "Finance2026",
    "fin_admin": "NU_2026"
}

if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False
if 'logged_in_user' not in st.session_state:
    st.session_state['logged_in_user'] = None
if 'sch_lookup_params' not in st.session_state:
    st.session_state['sch_lookup_params'] = None
if 'view_doc_id' not in st.session_state:
    st.session_state['view_doc_id'] = None

def login_form():
    st.markdown("<h2 style='text-align: center;'>🔒 Nile University Finance Login</h2>", unsafe_allow_html=True)
    with st.form("login_form"):
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        if submit:
            if user in USERS and USERS[user] == pwd:
                st.session_state['authenticated'] = True
                st.session_state['logged_in_user'] = user
                st.success(f"Welcome back, {user}!")
                st.rerun()
            else:
                st.error("Invalid Username or Password")

def get_next_ref_sequence(db_session):
    max_seq = 0
    refs = db_session.query(Transaction.reference_no).filter(Transaction.reference_no.isnot(None)).all()
    for (ref,) in refs:
        try:
            num = int(ref.split('-')[1])
            if num > max_seq:
                max_seq = num
        except:
            pass
    return max_seq

# =======================================================
# 5. PDF Generator
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
    headers = ["Ref No", "Date", "Term", "Year", "Type", "Description", "Debit", "Credit"]
    widths = [30, 25, 20, 15, 35, 90, 30, 30]
    for head, width in zip(headers, widths):
        pdf.cell(width, 10, head, 1, 0, 'C', True)
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
# 6. Main UI Layout
# =======================================================
st.set_page_config(page_title="Finance A/R System", layout="wide", page_icon="🏦")

if not st.session_state['authenticated']:
    login_form()
    st.stop()

col_title, col_logout = st.columns([0.8, 0.2], vertical_alignment="center")
with col_title:
    st.title("🏦 Nile University - Finance A/R System")
with col_logout:
    if st.button("🚪 Log out", use_container_width=True, key="main_logout"):
        st.session_state['authenticated'] = False
        st.session_state['logged_in_user'] = None
        st.rerun()

st.markdown("---")

if st.session_state.get('flash_msg'):
    st.success(st.session_state['flash_msg'])
    st.session_state['flash_msg'] = None

tab_search, tab_reg, tab1, tab2, tab3, tab_sch, tab_batch, tab_docs, tab4 = st.tabs([
    "🔍 Student Lookup",
    "👤 Registration",
    "📊 Operations",
    "📜 Statement & Search",
    "📤 Bulk Financials",
    "🎓 Scholarships",
    "🗑️ Batch Management",
    "📚 Policies & Docs",
    "📈 Management Reports"
])

# -------------------------------------------------------
# TAB 0: Student Lookup
# -------------------------------------------------------
with tab_search:
    st.subheader("🔍 Student Data Explorer")

    if 'lookup_id' not in st.session_state:
        st.session_state['lookup_id'] = 0

    with st.form("lookup_search_form", clear_on_submit=False):
        search_id_raw = st.text_input("Enter Student ID to lookup profile:", placeholder="e.g. 26100123")
        lookup_submitted = st.form_submit_button("🔍 Lookup Profile")

    if lookup_submitted:
        st.session_state['lookup_id'] = int(search_id_raw) if search_id_raw.strip().isdigit() else 0

    search_lookup_id = st.session_state['lookup_id']

    if search_lookup_id > 0:
        student = session.query(Student).filter_by(id=search_lookup_id).first()
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
            st.subheader("🎓 Active Scholarships (All Terms)")
            
            student_schs_all = session.query(StudentScholarship, ScholarshipType).join(
                ScholarshipType, StudentScholarship.scholarship_type_id == ScholarshipType.id
            ).filter(
                StudentScholarship.student_id == search_lookup_id, 
                StudentScholarship.is_active == True
            ).order_by(StudentScholarship.academic_year.desc(), StudentScholarship.term).all()
            
            if student_schs_all:
                df_schs = pd.DataFrame([{
                    "Term": ss.term,
                    "Year": ss.academic_year,
                    "Scholarship": st_type.name,
                    "Percentage": f"{ss.percentage * 100 if ss.percentage <= 1 else ss.percentage:.1f}%"
                } for ss, st_type in student_schs_all])
                st.dataframe(df_schs, use_container_width=True, hide_index=True)
            else:
                st.info("No active scholarships found for this student.")

            st.markdown("---")
            edit_mode = st.toggle("🔓 Unlock Edit Mode")
            if edit_mode:
                st.warning("⚠️ **CRITICAL WARNING:** You are modifying Master Data.")
                with st.form("edit_form"):
                    col_e1, col_e2, col_e3 = st.columns(3)
                    e_name = col_e1.text_input("Full Name", value=student.name if student.name else "")
                    e_college = col_e2.text_input("College", value=student.college if student.college else "")
                    e_price = col_e3.number_input("Price Per Hr (EGP)", value=float(student.price_per_hr) if student.price_per_hr else 0.0, step=100.0)
                    col_e4, col_e5, col_e6 = st.columns(3)
                    e_email = col_e4.text_input("Email", value=student.email if student.email else "")
                    e_mobile = col_e5.text_input("Mobile", value=student.mobile if student.mobile else "")
                    e_program = col_e6.text_input("Program", value=student.program if student.program else "")
                    if st.form_submit_button("💾 Save Changes"):
                        try:
                            student.name = e_name
                            student.college = e_college.upper()
                            student.price_per_hr = e_price
                            student.email = e_email
                            student.mobile = e_mobile
                            student.program = e_program
                            session.commit()
                            st.session_state['flash_msg'] = "✅ Student master data updated successfully!"
                            st.rerun()
                        except Exception as e:
                            session.rollback()
                            st.error(f"❌ Error: {e}")
        else:
            st.warning("⚠️ No student found with this ID.")

    st.markdown("---")
    st.subheader("📥 Export Master Data")
    all_students = session.query(Student).all()
    if all_students:
        df_all_students = pd.DataFrame([{
            "Student ID": s.id, "Full Name": s.name, "College Code": s.college,
            "Program": s.program, "Price Per Hour (EGP)": s.price_per_hr,
            "University Email": s.email, "Mobile Number": s.mobile,
            "National ID": s.national_id, "Nationality": s.nationality,
            "Birth Date": s.birth_date, "Admit Year": s.admit_year
        } for s in all_students])
        buf_all = io.BytesIO()
        df_all_students.to_excel(buf_all, index=False)
        st.download_button(
            label="📥 Export All Students to Excel",
            data=buf_all.getvalue(),
            file_name=f"NU_Students_MasterData_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

# -------------------------------------------------------
# TAB 0.5: Registration
# -------------------------------------------------------
with tab_reg:
    st.subheader("👤 New Student Registration")
    reg_mode = st.radio("Registration Type:", ["Manual Entry", "Bulk Upload (Excel)"], horizontal=True)

    if reg_mode == "Manual Entry":
        with st.form("manual_reg", clear_on_submit=True):
            st.markdown("💡 **Valid College Codes:** `ENG`, `BBA`, `IT_CS`, `Bio_Tech`")
            col_s1, col_s2, col_s3 = st.columns(3)
            n_id = col_s1.number_input("Student ID", value=None, placeholder="(e.g., 26100123)", step=1, format="%d")
            n_name = col_s2.text_input("Full Name *")
            n_college = col_s3.text_input("College Code *")
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
            submitted_reg = st.form_submit_button("💾 Register Student")
            if submitted_reg:
                if n_id is None or not n_name or not n_college:
                    st.error("⚠️ Student ID, Name, and College are required fields!")
                else:
                    exists = session.query(Student).filter_by(id=n_id).first()
                    if exists:
                        st.error("⚠️ Student ID already exists!")
                    else:
                        try:
                            new_s = Student(
                                id=n_id, name=n_name, college=n_college.upper(),
                                program=n_program, price_per_hr=n_price, email=n_email,
                                mobile=n_mobile, national_id=n_nat_id, nationality=n_nationality,
                                admit_year=n_admit, birth_date=n_dob
                            )
                            session.add(new_s)
                            session.commit()
                            st.session_state['flash_msg'] = f"✅ Student '{n_name}' has been registered!"
                            st.rerun()
                        except Exception as e:
                            session.rollback()
                            st.error(f"❌ Error: {e}")
    else:
        std_ex = {
            "ID": 26100123, "Name": "Ahmed Ali", "College": "ENG",
            "Program": "Computer Eng", "Price Per Hr": 4600.0,
            "Email": "ahmed@nu.edu.eg", "Mobile": "01000000000",
            "National ID": "29901010000000", "Nationality": "Egyptian",
            "Admit Year": DEFAULT_YEAR, "Birth Date": "2005-01-01"
        }
        buf_std = io.BytesIO()
        pd.DataFrame([std_ex]).to_excel(buf_std, index=False)
        st.download_button(label="📥 Download Students Template", data=buf_std.getvalue(), file_name="Template_Bulk_Students.xlsx")
        u_std = st.file_uploader("Upload Students Excel", type=['xlsx'])
        if u_std and st.button("🚀 Process Bulk Registration"):
            with st.spinner("Registering students..."):
                df_std = pd.read_excel(u_std)
                existing_ids = {s[0] for s in session.query(Student.id).all()}
                new_students = []
                for _, r in df_std.iterrows():
                    sid = int(r.get('ID', 0)) if pd.notnull(r.get('ID')) else 0
                    if sid > 0 and sid not in existing_ids:
                        bd_raw = r.get('Birth Date')
                        bd_clean = pd.to_datetime(bd_raw, errors='coerce').date() if pd.notnull(bd_raw) else None
                        new_students.append(Student(
                            id=sid, name=str(r.get('Name', 'Unknown')),
                            college=str(r.get('College', 'N/A')).upper(),
                            program=str(r.get('Program', '')), price_per_hr=float(r.get('Price Per Hr', 0.0)),
                            email=str(r.get('Email', '')), mobile=str(r.get('Mobile', '')),
                            national_id=str(r.get('National ID', '')), nationality=str(r.get('Nationality', 'Egyptian')),
                            admit_year=int(r.get('Admit Year', DEFAULT_YEAR)), birth_date=bd_clean
                        ))
                if new_students:
                    try:
                        session.add_all(new_students)
                        session.commit()
                        st.session_state['flash_msg'] = f"✅ Successfully registered {len(new_students)} new students!"
                        st.rerun()
                    except Exception as e:
                        session.rollback()
                        st.error(f"❌ Upload failed: {e}")
                else:
                    st.warning("⚠️ No new students added.")

# -------------------------------------------------------
# TAB 1: Manual Operations
# -------------------------------------------------------
with tab1:
    st.subheader("Post Manual Transaction")

    a_t = st.selectbox(
        "Select Action Type",
        ["Payment Receipt", "Credit Hours Adjustment", "Other Fees", "General Adjustment"],
        index=0
    )

    with st.form(f"manual_tx_form_{a_t}", clear_on_submit=True):
        sid_raw = st.text_input("Student ID", placeholder="Enter ID (e.g., 18100523)...")
        c1, c2, c3 = st.columns(3)
        ed = c1.date_input("Date")
        et = c2.selectbox("Term", ["Fall", "Spring", "Summer"])
        ey = c3.number_input("Year", value=DEFAULT_YEAR)

        if a_t == "Payment Receipt":
            b_n = st.text_input("Bank Name")
            b_r = st.text_input("Ref No")
            amt = st.number_input("Amount Paid", min_value=0.0)

        elif a_t == "Credit Hours Adjustment":
            h = st.number_input("Hours Delta (+/-)")
            st.info("💡 Note: System will automatically calculate and apply/revert scholarships based on the student's active configuration for this term.")

        elif a_t == "Other Fees":
            amt = st.number_input("Fee Amount")
            dsc_input = st.text_input("Description")
            
        elif a_t == "General Adjustment":
            col_ga1, col_ga2 = st.columns(2)
            dr_input = col_ga1.number_input("Debit Amount (EGP)", min_value=0.0)
            cr_input = col_ga2.number_input("Credit Amount (EGP)", min_value=0.0)
            dsc_input = st.text_input("Description")

        submitted_tx = st.form_submit_button("🚀 Process Transaction")

        if submitted_tx:
            sid = int(sid_raw) if sid_raw.strip().isdigit() else 0
            if sid == 0:
                st.error("Please enter a valid Student ID.")
            else:
                s_d = session.query(Student).filter_by(id=sid).first()
                if not s_d:
                    st.error("Student ID not found! Please register the student first.")
                else:
                    rate = s_d.price_per_hr if s_d else 0.0
                    dr, cr = 0.0, 0.0
                    dsc = ""
                    pfx = "TX"
                    h_change = 0.0
                    extra_txs = []  

                    m_id = get_next_ref_sequence(session)

                    if a_t == "Payment Receipt":
                        pfx = "PAY"
                        cr = amt
                        dsc = f"Bank: {b_n} | Ref: {b_r}"

                    elif a_t == "Credit Hours Adjustment":
                        pfx = "ADJ"
                        val = abs(h * rate)
                        dr = val if h > 0 else 0
                        cr = val if h < 0 else 0
                        dsc = f"Adj: {h} CH @ {rate:,.2f}"
                        h_change = h

                        extra_txs = build_auto_discount_transactions(
                            student_id=sid,
                            gross_amount=val,
                            term=et,
                            academic_year=int(ey),
                            entry_date=ed,
                            ref_start=m_id + 2,
                            batch_id=None
                        )
                        if h < 0:
                            for t in extra_txs:
                                t.debit, t.credit = t.credit, t.debit

                    elif a_t == "Other Fees":
                        pfx = "INV"
                        dr = amt
                        dsc = dsc_input
                        
                    elif a_t == "General Adjustment":
                        pfx = "TXN"
                        dr = dr_input
                        cr = cr_input
                        dsc = dsc_input

                    new_tx = Transaction(
                        reference_no=f"{pfx}-{m_id+1:06d}",
                        student_id=sid,
                        scholarship_type_id=None,
                        transaction_type=a_t,
                        description=dsc,
                        debit=dr,
                        credit=cr,
                        hours_change=h_change,
                        entry_date=ed,
                        term=et,
                        academic_year=ey
                    )
                    session.add(new_tx)

                    for t in extra_txs:
                        session.add(t)

                    session.commit()
                    auto_info = f" + {len(extra_txs)} auto discount(s)" if extra_txs else ""
                    st.session_state['flash_msg'] = f"✅ Posted: {new_tx.reference_no} for {s_d.name}{auto_info}!"
                    st.rerun()

# -------------------------------------------------------
# TAB 2: Transaction Search & Statement
# -------------------------------------------------------
with tab2:
    st.subheader("Transaction Search & Statement of Account")
    st.markdown("💡 *Leave Student ID blank and enter a Bank Ref or System Ref to search globally.*")

    if 'stmt_search_params' not in st.session_state:
        st.session_state['stmt_search_params'] = None

    with st.form("stmt_search_form", clear_on_submit=False):
        col_t1, col_t2, col_t3 = st.columns(3)
        search_r = col_t1.text_input("Student ID", placeholder="e.g., 25100120")
        sys_ref_search = col_t2.text_input("System Ref No", placeholder="e.g., INV-004751")
        bank_ref_search = col_t3.text_input("Bank Ref / Description", placeholder="e.g., 12345 or CIB")
        f1, f2, f3 = st.columns(3)
        df_r = f1.date_input("Date Range", [])
        s_t = f2.multiselect("Terms", ["Fall", "Spring", "Summer"])
        s_y = f3.multiselect("Years", available_years)
        search_btn = st.form_submit_button("🔍 Search Transactions")

    if search_btn:
        st.session_state['stmt_search_params'] = {
            'sid': int(search_r) if search_r.strip().isdigit() else 0,
            'sys': sys_ref_search, 'bank': bank_ref_search,
            'dates': df_r, 'terms': s_t, 'years': s_y
        }

    if st.session_state.get('stmt_search_params'):
        p = st.session_state['stmt_search_params']
        if p['sid'] > 0 or p['sys'] or p['bank'] or len(p['dates']) == 2 or p['terms'] or p['years']:
            q = session.query(Transaction, Student).join(Student, Transaction.student_id == Student.id)
            if p['sid'] > 0:
                q = q.filter(Transaction.student_id == p['sid'])
            if p['sys']:
                q = q.filter(Transaction.reference_no.ilike(f"%{p['sys']}%"))
            if p['bank']:
                q = q.filter(Transaction.description.ilike(f"%{p['bank']}%"))
            if len(p['dates']) == 2:
                q = q.filter(Transaction.entry_date.between(p['dates'][0], p['dates'][1]))
            if p['terms']:
                q = q.filter(Transaction.term.in_(p['terms']))
            if p['years']:
                q = q.filter(Transaction.academic_year.in_(p['years']))

            res = q.order_by(Transaction.entry_date.desc()).all()
            df_display = None
            if res:
                df_display = pd.DataFrame([{
                    "Student ID": s.id, "Name": s.name, "Ref No": t.reference_no,
                    "Date": t.entry_date, "Term": t.term, "Year": t.academic_year,
                    "Type": t.transaction_type, "Description": t.description,
                    "Debit": f"{t.debit:,.2f}", "Credit": f"{t.credit:,.2f}"
                } for t, s in res])
                st.table(df_display)

                if p['sid'] > 0:
                    total_debit = sum(t.debit for t, s in res)
                    total_credit = sum(t.credit for t, s in res)
                    net = total_debit - total_credit
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Total Debit", f"{total_debit:,.2f} EGP")
                    m2.metric("Total Credit", f"{total_credit:,.2f} EGP")
                    m3.metric("Net Balance Due", f"{net:,.2f} EGP")
                    df_pdf = pd.DataFrame([{
                        "Ref No": t.reference_no, "Date": t.entry_date, "Term": t.term,
                        "Year": t.academic_year, "Type": t.transaction_type,
                        "Description": t.description,
                        "Debit": f"{t.debit:,.2f}", "Credit": f"{t.credit:,.2f}"
                    } for t, s in res])
                    b1, b2 = st.columns(2)
                    with b1:
                        student_name = res[0][1].name
                        pdf_data = create_pdf(p['sid'], student_name, df_pdf, net, total_debit, total_credit)
                        st.download_button(
                            label="📄 Download PDF Statement", data=pdf_data,
                            file_name=f"SOA_{p['sid']}.pdf", use_container_width=True
                        )
                    with b2:
                        df_export = df_display.copy()
                        df_export.loc[len(df_export)] = {
                            "Student ID": "", "Name": "", "Ref No": "", "Date": "", "Term": "",
                            "Year": "", "Type": "", "Description": "TOTALS",
                            "Debit": f"{total_debit:,.2f}", "Credit": f"{total_credit:,.2f}"
                        }
                        excel_buf = io.BytesIO()
                        df_export.to_excel(excel_buf, index=False)
                        st.download_button(
                            label="📗 Download Excel Sheet", data=excel_buf.getvalue(),
                            file_name=f"SOA_{p['sid']}.xlsx", use_container_width=True
                        )
            else:
                st.warning("⚠️ No transactions found matching these criteria.")

# -------------------------------------------------------
# TAB 3: Bulk Financial Operations
# -------------------------------------------------------
with tab3:
    st.subheader("Bulk Financial Operations")

    b_t = st.radio(
        "Type:",
        ["Bulk Payments", "Bulk Invoices (Tuition)", "Bulk Other Fees",
         "Credit Hours Adjustments", "Update Student Rates", "General Adjustments"],
        horizontal=True
    )

    st.warning("⚠️ **IMPORTANT:** DELETE the Example Row (ID: 0) before uploading.")

    ex = {
        "Bulk Payments": {"ID": 0, "Bank Name": "Bank", "Bank Ref": "REF123", "Amount": 0.0, "Date": "2026-04-17", "Term": "Spring", "Year": DEFAULT_YEAR},
        "Bulk Invoices (Tuition)": {"ID": 0, "Hours": 15.0, "Date": "2026-04-17", "Term": "Spring", "Year": DEFAULT_YEAR},
        "Bulk Other Fees": {"ID": 0, "Fee Amount": 1500.0, "Description": "Bus Subscription", "Date": "2026-04-17", "Term": "Spring", "Year": DEFAULT_YEAR},
        "Credit Hours Adjustments": {"ID": 0, "Hours_Delta": 3.0, "Date": "2026-04-17", "Term": "Spring", "Year": DEFAULT_YEAR},
        "Update Student Rates": {"ID": 0, "New_Price_Per_Hr": 5500.0},
        "General Adjustments": {"ID": 0, "Debit": 0.0, "Credit": 0.0, "Date": "2026-04-17", "Term": "Spring", "Year": DEFAULT_YEAR, "Description": "DELETE"}
    }

    buf_t = io.BytesIO()
    pd.DataFrame([ex[b_t]]).to_excel(buf_t, index=False)
    st.download_button(label="📥 Download Template", data=buf_t.getvalue(), file_name=f"Tpl_{b_t}.xlsx")

    u_f = st.file_uploader("Upload Excel File", type=['xlsx'])

    if u_f and st.button("🚀 Run Bulk Process"):
        with st.spinner("Processing..."):
            current_batch_id = f"BCH-{datetime.now().strftime('%y%m%d-%H%M%S')}"
            df_b = pd.read_excel(u_f)
            df_b.columns = [str(c).strip() for c in df_b.columns]
            numeric_columns = ['Amount', 'Hours', 'Hours_Delta', 'Fee Amount', 'Debit', 'Credit', 'New_Price_Per_Hr']
            for col in numeric_columns:
                if col in df_b.columns:
                    df_b[col] = pd.to_numeric(df_b[col].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0.0)

            if b_t == "Update Student Rates":
                for _, r in df_b.iterrows():
                    r_id = int(r.get('ID', 0))
                    if r_id != 0:
                        session.query(Student).filter(Student.id == r_id).update({"price_per_hr": float(r['New_Price_Per_Hr'])})
                session.commit()
                st.session_state['flash_msg'] = "✅ Rates Updated!"
                st.rerun()
            else:
                m_id = get_next_ref_sequence(session)
                rts = {s.id: s.price_per_hr for s in session.query(Student).all()}
                bulk_l = []
                tx_counter = 1

                for i, r in df_b.iterrows():
                    sid = int(r.get('ID', 0)) if pd.notnull(r.get('ID')) else 0
                    if sid == 0 or sid not in rts:
                        continue

                    rt = rts[sid]
                    dr, cr = 0.0, 0.0
                    pfx = "TX"
                    h_change = 0.0
                    raw_desc = str(r.get('Description', '')).strip()
                    dsc = b_t if not raw_desc or raw_desc in ['0', '0.0', 'nan'] else raw_desc
                    term_val = str(r.get('Term', 'Spring'))
                    year_val = int(r.get('Year', DEFAULT_YEAR)) if pd.notnull(r.get('Year')) else DEFAULT_YEAR

                    if b_t == "Bulk Payments":
                        pfx = "PAY"
                        cr = float(str(r.get('Amount', 0)).replace(',', '').strip() or 0.0)
                        dsc = f"Bank: {r.get('Bank Name')} | Ref: {r.get('Bank Ref')}"

                    elif b_t == "Bulk Invoices (Tuition)":
                        h = float(str(r.get('Hours', 15.0)).replace(',', '').strip() or 0.0)
                        pfx = "INV"
                        dr = h * rt
                        dsc = f"Tuition Invoice ({h} CH)"
                        h_change = h

                    elif b_t == "Bulk Other Fees":
                        pfx = "INV"
                        dr = float(str(r.get('Fee Amount', 0)).replace(',', '').strip() or 0.0)
                        dsc = raw_desc if raw_desc and raw_desc not in ['0', '0.0', 'nan'] else "Other Fee"

                    elif b_t == "Credit Hours Adjustments":
                        h = float(str(r.get('Hours_Delta', 0)).replace(',', '').strip() or 0.0)
                        pfx = "ADJ"
                        v = abs(h * rt)
                        dr = v if h > 0 else 0
                        cr = v if h < 0 else 0
                        dsc = f"Adj {h} CH"
                        h_change = h

                    elif b_t == "General Adjustments":
                        pfx = "TXN"
                        dr = float(str(r.get('Debit', 0)).replace(',', '').strip() or 0.0)
                        cr = float(str(r.get('Credit', 0)).replace(',', '').strip() or 0.0)

                    new_bulk_tx = Transaction(
                        reference_no=f"{pfx}-{m_id+tx_counter:06d}",
                        batch_id=current_batch_id,
                        student_id=sid, scholarship_type_id=None,
                        transaction_type=b_t, description=dsc,
                        debit=dr, credit=cr, hours_change=h_change,
                        entry_date=pd.to_datetime(r.get('Date')).date(),
                        term=term_val, academic_year=year_val
                    )
                    bulk_l.append(new_bulk_tx)
                    tx_counter += 1

                    if b_t in ["Bulk Invoices (Tuition)", "Credit Hours Adjustments"]:
                        inv_amount = dr if b_t == "Bulk Invoices (Tuition)" else v
                        auto_discounts = build_auto_discount_transactions(
                            student_id=sid,
                            gross_amount=inv_amount,
                            term=term_val,
                            academic_year=year_val,
                            entry_date=pd.to_datetime(r.get('Date')).date(),
                            ref_start=m_id + tx_counter,
                            batch_id=current_batch_id
                        )
                        if b_t == "Credit Hours Adjustments" and h_change < 0:
                            for t in auto_discounts:
                                t.debit, t.credit = t.credit, t.debit

                        bulk_l.extend(auto_discounts)
                        tx_counter += len(auto_discounts)

                if bulk_l:
                    session.bulk_save_objects(bulk_l)
                    session.commit()
                    st.session_state['flash_msg'] = f"✅ Batch {current_batch_id} Successfully Posted!"
                    st.rerun()

# -------------------------------------------------------
# TAB: Scholarships Management
# -------------------------------------------------------
with tab_sch:
    st.subheader("🎓 Student Scholarships Management")
    st.markdown("Manage permanent scholarships linked to each student and their respective terms.")

    sch_action = st.radio("Action:", ["View / Edit", "Add Scholarship", "Bulk Upload Scholarships", "📊 Scholarships Report"], horizontal=True)

    if sch_action == "View / Edit":
        with st.form("sch_lookup_form", clear_on_submit=False):
            sch_sid_raw = st.text_input("Student ID:", placeholder="e.g. 25100120")
            col_a, col_b = st.columns(2)
            sch_term = col_a.selectbox("Term:", ["Fall", "Spring", "Summer"])
            sch_year = col_b.number_input("Academic Year:", value=DEFAULT_YEAR, step=1)
            sch_search_btn = st.form_submit_button("🔍 Load Scholarships")

        if sch_search_btn:
            if sch_sid_raw.strip().isdigit():
                st.session_state['sch_lookup_params'] = {
                    'sid': int(sch_sid_raw),
                    'term': sch_term,
                    'year': int(sch_year)
                }
            else:
                st.session_state['sch_lookup_params'] = None
                st.warning("⚠️ Invalid Student ID.")

        if st.session_state.get('sch_lookup_params'):
            p = st.session_state['sch_lookup_params']
            sch_sid = p['sid']
            sch_term = p['term']
            sch_year = p['year']
            
            student = session.query(Student).filter_by(id=sch_sid).first()
            if not student:
                st.warning("⚠️ Student not found.")
            else:
                st.info(f"Student: **{student.name}** | Term: {sch_term} {sch_year}")
                student_schs = session.query(StudentScholarship, ScholarshipType).join(
                    ScholarshipType, StudentScholarship.scholarship_type_id == ScholarshipType.id
                ).filter(
                    StudentScholarship.student_id == sch_sid,
                    StudentScholarship.term == sch_term,
                    StudentScholarship.academic_year == sch_year
                ).all()

                if student_schs:
                    for ss, st_type in student_schs:
                        pct_display = ss.percentage * 100 if ss.percentage <= 1.0 else ss.percentage
                        c_1, c_2, c_3 = st.columns([4, 2, 2])
                        c_1.write(f"**{st_type.name}**")
                        c_2.write(f"{pct_display:.1f}%")
                        status = "✅ Active" if ss.is_active else "🔴 Inactive"
                        c_3.write(status)
                        
                        with st.expander(f"⚙️ Manage '{st_type.name}' Mode"):
                            if ss.is_active:
                                st.info("⏸️ **Option 1: Stop Future Discounts Only** \n Prevents this discount on future invoices. Past invoices remain unchanged.")
                                if st.button("Stop Future Only", key=f"stop_fut_{ss.id}"):
                                    ss.is_active = False
                                    session.commit()
                                    st.session_state['flash_msg'] = "✅ Scholarship stopped for future transactions."
                                    st.rerun()
                                
                                st.markdown("---")
                                if st.session_state.get('logged_in_user') == 'fin_admin':
                                    st.error("🛑 **Option 2: Stop & Reverse Past (Admin Only)** \n Stops future discounts AND reverses past discounts by posting a debit adjustment to the student's account.")
                                    confirm_rev = st.checkbox(f"⚠️ I understand this alters previous financial balances for this term.", key=f"chk_rev_{ss.id}")
                                    if st.button("Stop & Reverse Past", key=f"stop_rev_{ss.id}"):
                                        if confirm_rev:
                                            ss.is_active = False
                                            session.commit()
                                            m_id = get_next_ref_sequence(session)
                                            retro_tx, _ = get_retroactive_scholarship_tx(
                                                session, sch_sid, sch_term, sch_year, ss.scholarship_type_id, st_type.name, 0.0, m_id + 1
                                            )
                                            if retro_tx:
                                                session.add(retro_tx)
                                                session.commit()
                                                st.session_state['flash_msg'] = "✅ Scholarship stopped AND past discounts reversed successfully!"
                                            else:
                                                st.session_state['flash_msg'] = "✅ Scholarship stopped (No past transactions found to reverse)."
                                            st.rerun()
                                        else:
                                            st.warning("⚠️ You must check the confirmation box.")
                                else:
                                    st.error("🔒 **Admin Access Required:** Only 'fin_admin' can reverse past discounts.")
                            else:
                                st.info("▶️ **Activate Scholarship** \n Enables discount and retroactively applies it to existing invoices in this term.")
                                if st.button("Activate Scholarship", key=f"act_{ss.id}"):
                                    ss.is_active = True
                                    session.commit()
                                    m_id = get_next_ref_sequence(session)
                                    effective_pct = ss.percentage * 100.0 if ss.percentage <= 1.0 else ss.percentage
                                    retro_tx, _ = get_retroactive_scholarship_tx(
                                        session, sch_sid, sch_term, sch_year, ss.scholarship_type_id, st_type.name, effective_pct, m_id + 1
                                    )
                                    if retro_tx:
                                        session.add(retro_tx)
                                        session.commit()
                                        st.session_state['flash_msg'] = "✅ Scholarship Activated & retroactively applied to invoices."
                                    else:
                                        st.session_state['flash_msg'] = "✅ Scholarship Activated successfully."
                                    st.rerun()
                        st.write("")
                else:
                    st.info("No scholarships found for this student in the selected term/year.")

    elif sch_action == "Add Scholarship":
        with st.form("add_sch_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            add_sid = col1.number_input("Student ID:", min_value=1, step=1)
            add_term = col2.selectbox("Term:", ["Fall", "Spring", "Summer"])
            add_year = col3.number_input("Academic Year:", value=DEFAULT_YEAR, step=1)
            
            add_type = st.selectbox("Scholarship Type:", list(sch_map.keys()))
            add_pct = st.number_input("Percentage (e.g. 60 for 60%):", min_value=0.0, max_value=100.0, step=5.0)
            add_btn = st.form_submit_button("➕ Add Scholarship")

            if add_btn:
                student = session.query(Student).filter_by(id=add_sid).first()
                if not student:
                    st.error("❌ Student not found!")
                else:
                    existing = session.query(StudentScholarship).filter_by(
                        student_id=add_sid,
                        scholarship_type_id=sch_map[add_type],
                        term=add_term,
                        academic_year=add_year
                    ).first()

                    if existing:
                        existing.percentage = add_pct
                        existing.is_active = True
                        session.commit()
                        msg = f"✅ Updated scholarship '{add_type}' for {student.name}."
                    else:
                        new_sch = StudentScholarship(
                            student_id=add_sid,
                            scholarship_type_id=sch_map[add_type],
                            percentage=add_pct,
                            term=add_term,
                            academic_year=add_year,
                            is_active=True
                        )
                        session.add(new_sch)
                        session.commit()
                        msg = f"✅ Added scholarship '{add_type}' ({add_pct}%) for {student.name}."

                    m_id = get_next_ref_sequence(session)
                    effective_pct = add_pct * 100.0 if add_pct <= 1.0 else add_pct
                    
                    retro_tx, _ = get_retroactive_scholarship_tx(
                        session, add_sid, add_term, add_year, sch_map[add_type], add_type, effective_pct, m_id + 1
                    )
                    if retro_tx:
                        session.add(retro_tx)
                        session.commit()
                        msg += " (Retroactive discount automatically applied to existing invoices!)"
                    
                    st.session_state['flash_msg'] = msg
                    st.rerun()

    elif sch_action == "Bulk Upload Scholarships":
        st.info("💡 Upload scholarships for multiple students at once. (Ensure exact match of Scholarship Name and Term).")
        st.error("🛑 **CRITICAL WARNING:** The 'Scholarship Name' in your Excel file MUST MATCH EXACTLY as written below (including spaces, caps, and the '%' sign).")
        st.markdown("📋 **Available Scholarships (Hover over any name and click the 📋 Copy icon on the right):**")
        
        sch_names = list(sch_map.keys())
        cols = st.columns(3)
        for i, name in enumerate(sch_names):
            with cols[i % 3]:
                st.code(name, language=None)
                
        sch_template = {
            "Student ID": 26100123, 
            "Scholarship Name": sch_names[0] if sch_names else "SCH: ...", 
            "Percentage": 60.0, 
            "Term": "Spring", 
            "Academic Year": DEFAULT_YEAR
        }
        buf_sch = io.BytesIO()
        pd.DataFrame([sch_template]).to_excel(buf_sch, index=False)
        st.download_button(label="📥 Download Template", data=buf_sch.getvalue(), file_name="Template_Scholarships.xlsx")

        u_sch = st.file_uploader("Upload Scholarships Excel", type=['xlsx'])
        if u_sch and st.button("🚀 Upload Scholarships"):
            with st.spinner("Processing & applying retroactive discounts..."):
                df_sch = pd.read_excel(u_sch)
                df_sch.columns = [str(c).strip() for c in df_sch.columns]
                
                uploaded_data = []
                added, updated, skipped = 0, 0, 0
                
                for _, r in df_sch.iterrows():
                    sid = int(r.get('Student ID', 0)) if pd.notnull(r.get('Student ID')) else 0
                    s_name = str(r.get('Scholarship Name', '')).strip()
                    pct = float(r.get('Percentage', 0))
                    trm = str(r.get('Term', 'Spring')).strip()
                    yr = int(r.get('Academic Year', DEFAULT_YEAR))
                    s_type_id = sch_map.get(s_name)

                    if sid <= 0 or not s_type_id or pct <= 0:
                        skipped += 1
                        continue

                    existing = session.query(StudentScholarship).filter_by(
                        student_id=sid, scholarship_type_id=s_type_id, term=trm, academic_year=yr
                    ).first()

                    if existing:
                        existing.percentage = pct
                        existing.is_active = True
                        updated += 1
                    else:
                        session.add(StudentScholarship(
                            student_id=sid, scholarship_type_id=s_type_id,
                            percentage=pct, term=trm, academic_year=yr, is_active=True
                        ))
                        added += 1
                        
                    uploaded_data.append((sid, s_type_id, s_name, pct, trm, yr))

                session.commit()
                
                m_id = get_next_ref_sequence(session)
                curr_c = m_id + 1
                retro_txs = []
                batch_id = f"BCH-SCH-{datetime.now().strftime('%y%m%d-%H%M%S')}"
                
                for sid, s_type_id, s_name, pct, trm, yr in uploaded_data:
                    effective_pct = pct * 100.0 if pct <= 1.0 else pct
                    r_tx, curr_c = get_retroactive_scholarship_tx(
                        session, sid, trm, yr, s_type_id, s_name, effective_pct, curr_c, batch_id
                    )
                    if r_tx:
                        retro_txs.append(r_tx)
                
                retro_msg = ""
                if retro_txs:
                    session.bulk_save_objects(retro_txs)
                    session.commit()
                    retro_msg = f" | Applied {len(retro_txs)} retroactive discount entries to existing invoices."
                
                st.session_state['flash_msg'] = f"✅ Done! Added: {added} | Updated: {updated} | Skipped: {skipped}{retro_msg}"
                st.rerun()
                
    elif sch_action == "📊 Scholarships Report":
        st.markdown("💡 **Comprehensive report showing configured scholarship percentages for each student and actual amounts applied in their statement.**")
        
        if st.button("📂 Generate Scholarship Report"):
            with st.spinner("Compiling comprehensive report..."):
                sql = text("""
                    SELECT 
                        s.id AS "Student ID", 
                        s.name AS "Student Name", 
                        s.college AS "College",
                        ss.term AS "Term", 
                        ss.academic_year AS "Year", 
                        st.name AS "Scholarship Name", 
                        ss.percentage AS "Configured %",
                        CASE WHEN ss.is_active THEN 'Active' ELSE 'Inactive' END AS "Status",
                        COALESCE((
                            SELECT SUM(t.debit - t.credit) 
                            FROM transactions t 
                            WHERE t.student_id = s.id AND t.term = ss.term AND t.academic_year = ss.academic_year 
                            AND t.transaction_type IN ('Invoice', 'Bulk Invoices (Tuition)', 'Credit Hours Adjustment', 'Credit Hours Adjustments')
                        ), 0) AS "Total Tuition Billed (EGP)",
                        COALESCE((
                            SELECT SUM(t.credit - t.debit) 
                            FROM transactions t 
                            WHERE t.student_id = s.id AND t.term = ss.term AND t.academic_year = ss.academic_year AND t.reference_no LIKE 'SCH-%'
                        ), 0) AS "Actual Discount Applied (EGP)"
                    FROM student_scholarships ss
                    JOIN students s ON ss.student_id = s.id
                    JOIN scholarship_types st ON ss.scholarship_type_id = st.id
                    ORDER BY ss.academic_year DESC, ss.term, s.id
                """)
                
                res = session.execute(sql).fetchall()
                if res:
                    df_rep = pd.DataFrame(res, columns=["Student ID", "Student Name", "College", "Term", "Year", "Scholarship Name", "Configured %", "Status", "Total Tuition Billed (EGP)", "Actual Discount Applied (EGP)"])
                    
                    st.dataframe(df_rep.style.format({
                        "Configured %": "{:.1f}", 
                        "Total Tuition Billed (EGP)": "{:,.2f}", 
                        "Actual Discount Applied (EGP)": "{:,.2f}"
                    }), use_container_width=True)
                    
                    buf_rep = io.BytesIO()
                    df_rep.to_excel(buf_rep, index=False)
                    st.download_button(
                        label="📗 Download Excel Report", 
                        data=buf_rep.getvalue(), 
                        file_name=f"Scholarships_Report_{datetime.now().strftime('%Y%m%d')}.xlsx", 
                        use_container_width=True
                    )
                else:
                    st.info("⚠️ No scholarships configured in the system yet.")

# -------------------------------------------------------
# TAB 5: Batch Management
# -------------------------------------------------------
with tab_batch:
    st.subheader("🗑️ Batch Management")
    st.markdown("💡 *Manage uploaded batches, view history, or perform administrative rollbacks.*")

    batch_action = st.radio(
        "Action:",
        ["📂 View Active Batches", "📥 Export Batch Details", "🗑️ Delete Batch (Admin Only)", "📜 Deleted Batches History"],
        horizontal=True
    )

    batch_summary = session.query(
        Transaction.batch_id, Transaction.transaction_type,
        func.count(Transaction.id).label("record_count"),
        func.sum(Transaction.debit).label("total_debit"),
        func.sum(Transaction.credit).label("total_credit"),
        func.max(Transaction.created_at).label("upload_date")
    ).filter(Transaction.batch_id.isnot(None)).group_by(
        Transaction.batch_id, Transaction.transaction_type
    ).order_by(func.max(Transaction.created_at).desc()).all()

    if batch_action == "📂 View Active Batches":
        if not batch_summary:
            st.info("No active batches found in the system.")
        else:
            df_batches = pd.DataFrame([{
                "Batch ID": b.batch_id, "Type": b.transaction_type,
                "Records": b.record_count,
                "Total Debit": f"{b.total_debit:,.2f}",
                "Total Credit": f"{b.total_credit:,.2f}",
                "Uploaded At": b.upload_date.strftime('%Y-%m-%d %H:%M:%S') if b.upload_date else "N/A"
            } for b in batch_summary])
            st.dataframe(df_batches, use_container_width=True)

    elif batch_action == "📥 Export Batch Details":
        if not batch_summary:
            st.info("No active batches available to export.")
        else:
            st.markdown("💡 **Select a batch to download all its detailed transactions in an Excel file.**")
            unique_batches = list(pd.Series([b.batch_id for b in batch_summary]).unique())
            
            selected_export_batch = st.selectbox("Select Batch ID to Export:", unique_batches)
            
            if selected_export_batch:
                with st.spinner("Preparing batch data..."):
                    sql = text("""
                        SELECT 
                            t.reference_no AS "Ref No",
                            s.id AS "Student ID",
                            s.name AS "Student Name",
                            t.transaction_type AS "Type",
                            t.description AS "Description",
                            t.entry_date AS "Date",
                            t.term AS "Term",
                            t.academic_year AS "Year",
                            t.hours_change AS "Hours",
                            t.debit AS "Debit",
                            t.credit AS "Credit"
                        FROM transactions t
                        JOIN students s ON t.student_id = s.id
                        WHERE t.batch_id = :b_id
                        ORDER BY t.id ASC
                    """)
                    res = session.execute(sql, {"b_id": selected_export_batch}).fetchall()
                    
                    if res:
                        df_export = pd.DataFrame(res, columns=["Ref No", "Student ID", "Student Name", "Type", "Description", "Date", "Term", "Year", "Hours", "Debit", "Credit"])
                        
                        st.dataframe(df_export.style.format({
                            "Hours": "{:,.1f}", "Debit": "{:,.2f}", "Credit": "{:,.2f}"
                        }), use_container_width=True)
                        
                        buf = io.BytesIO()
                        df_export.to_excel(buf, index=False)
                        
                        st.download_button(
                            label="📗 Download Batch Excel File",
                            data=buf.getvalue(),
                            file_name=f"Batch_Export_{selected_export_batch}.xlsx",
                            use_container_width=True
                        )
                    else:
                        st.warning("No records found for this batch.")

    elif batch_action == "🗑️ Delete Batch (Admin Only)":
        if st.session_state.get('logged_in_user') == 'fin_admin':
            if not batch_summary:
                st.info("No active batches available to delete.")
            else:
                st.error("🛑 **DANGER ZONE: Batch Deletion**")
                st.warning("Deleting a batch will permanently remove all associated transactions. This action will be securely logged.")
                
                unique_batches = list(pd.Series([b.batch_id for b in batch_summary]).unique())
                
                with st.form("delete_batch_form"):
                    batch_to_delete = st.selectbox("Select Batch ID to Delete:", unique_batches)
                    confirm_delete = st.checkbox(f"⚠️ I confirm that I want to permanently delete all records in '{batch_to_delete}'")
                    
                    if st.form_submit_button("🗑️ Delete Batch"):
                        if confirm_delete:
                            try:
                                batch_records = [b for b in batch_summary if b.batch_id == batch_to_delete]
                                total_recs = sum(b.record_count for b in batch_records)
                                tot_deb = sum(b.total_debit for b in batch_records)
                                tot_cred = sum(b.total_credit for b in batch_records)
                                b_types = " & ".join(list(set(b.transaction_type for b in batch_records)))

                                log_entry = DeletedBatchLog(
                                    batch_id=batch_to_delete,
                                    transaction_type=b_types,
                                    record_count=total_recs,
                                    total_debit=tot_deb,
                                    total_credit=tot_cred,
                                    deleted_by=st.session_state.get('logged_in_user')
                                )
                                session.add(log_entry)
                                
                                deleted_count = session.query(Transaction).filter(Transaction.batch_id == batch_to_delete).delete()
                                session.commit()
                                st.session_state['flash_msg'] = f"✅ Deleted {deleted_count} records from batch {batch_to_delete}. Action securely logged."
                                st.rerun()
                            except Exception as e:
                                session.rollback()
                                st.error(f"❌ Error deleting batch: {e}")
                        else:
                            st.warning("⚠️ You must check the confirmation box to delete the batch.")
        else:
            st.error("🔒 **Access Denied:** Only System Administrators ('fin_admin') have permission to delete batches.")

    elif batch_action == "📜 Deleted Batches History":
        deleted_logs = session.query(DeletedBatchLog).order_by(DeletedBatchLog.deleted_at.desc()).all()
        if deleted_logs:
            df_logs = pd.DataFrame([{
                "Batch ID": log.batch_id,
                "Type(s)": log.transaction_type,
                "Records": log.record_count,
                "Total Debit": f"{log.total_debit:,.2f}",
                "Total Credit": f"{log.total_credit:,.2f}",
                "Deleted By": log.deleted_by,
                "Deleted At": log.deleted_at.strftime('%Y-%m-%d %H:%M:%S')
            } for log in deleted_logs])
            st.dataframe(df_logs, use_container_width=True)
        else:
            st.info("No deleted batches history found.")

# -------------------------------------------------------
# TAB 7: Policies & Docs
# -------------------------------------------------------
with tab_docs:
    st.subheader("📚 University Financial Policies & Documents")
    st.markdown("💡 *View, download, and manage official university financial policies and guidelines.*")

    doc_action = st.radio("Action:", ["📂 View & Download", "📤 Upload New Document (Admin Only)"], horizontal=True)

    if doc_action == "📂 View & Download":
        available_doc_years = [y[0] for y in session.query(PolicyDocument.academic_year).distinct().all()]
        
        if "2022/2023" not in available_doc_years: available_doc_years.append("2022/2023")
        if "2025/2026" not in available_doc_years: available_doc_years.append("2025/2026")
        
        sel_doc_year = st.selectbox("Filter by Academic Year:", sorted(set(available_doc_years), reverse=True))
        
        # 💡 تم عكس الترتيب هنا: عرض ملفات الـ PDF الأصلية أولاً
        st.markdown("### 🗄️ Original Uploaded PDF Files")
        docs = session.query(PolicyDocument).filter_by(academic_year=sel_doc_year).order_by(PolicyDocument.uploaded_at.desc()).all()
        
        if docs:
            for doc in docs:
                with st.container():
                    c1, c2, c3, c4 = st.columns([4, 1, 1, 1])
                    c1.markdown(f"📄 **{doc.title}**<br><small>Uploaded by {doc.uploaded_by} on {doc.uploaded_at.strftime('%Y-%m-%d')}</small>", unsafe_allow_html=True)
                    
                    if c2.button("👁️ View PDF", key=f"view_{doc.id}"):
                        st.session_state['view_doc_id'] = doc.id
                        
                    c3.download_button("⬇️ Download PDF", data=doc.file_data, file_name=doc.file_name, mime="application/pdf", key=f"dl_{doc.id}")
                    
                    if st.session_state.get('logged_in_user') == 'fin_admin':
                        if c4.button("🗑️ Delete", key=f"del_{doc.id}"):
                            session.delete(doc)
                            session.commit()
                            st.session_state['flash_msg'] = f"✅ Document '{doc.title}' deleted successfully."
                            if st.session_state.get('view_doc_id') == doc.id:
                                st.session_state['view_doc_id'] = None
                            st.rerun()
                    else:
                        c4.write("") 
                        
            st.markdown("---")
            
            if st.session_state.get('view_doc_id'):
                doc_to_view = session.query(PolicyDocument).get(st.session_state['view_doc_id'])
                if doc_to_view:
                    st.markdown(f"### 👀 Viewing PDF: {doc_to_view.title}")
                    if st.button("❌ Close Document Reader"):
                        st.session_state['view_doc_id'] = None
                        st.rerun()
                        
                    base64_pdf = base64.b64encode(doc_to_view.file_data).decode('utf-8')
                    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf"></iframe>'
                    st.markdown(pdf_display, unsafe_allow_html=True)
        else:
            st.warning("⚠️ No original PDF document has been uploaded for this academic year yet. Admins can upload it from the 'Upload New Document' tab.")

        st.markdown("---")

        # 💡 عرض التفريغ الرقمي (Digital Extraction) ثانياً
        st.markdown("### 📊 Extracted Digital Policy")
        if sel_doc_year == "2022/2023":
            st.success("✨ Digital extraction available for this academic year based on the official policy document.")
            
            with st.expander("📌 1. Undergraduate Tuition Fees (New Students - Fall 22)", expanded=True):
                df_new_tuition = pd.DataFrame({
                    "College / Program": ["Engineering (ENGR)", "Computer Science (CS)", "Business (BBA)", "Biotechnology"],
                    "Egyptian Price / Credit Hour (EGP)": ["3,450", "3,450", "3,450", "3,450"],
                    "Total per Year (EGP) (24-36 ch)": ["95,148", "78,176", "71,600", "69,576"],
                    "Non-Egyptian (Per Year in USD)": ["$12,018", "$9,867", "$8,982", "$8,729"]
                })
                st.table(df_new_tuition)
            
            with st.expander("📌 2. Undergraduate Tuition Fees (Continuing Students)"):
                df_cont_tuition = pd.DataFrame({
                    "College / Program": ["Engineering (ENGR)", "Computer Science (CS)", "Business (BBA)", "Biotechnology"],
                    "Egyptian Price / Credit Hour (EGP)": ["3,360", "3,360", "3,360", "3,360"],
                    "Total per Year (EGP) (24-36 ch)": ["92,666", "76,138", "69,730", "67,760"],
                    "Non-Egyptian (Per Year in USD)": ["$11,704", "$9,610", "$8,747", "$8,500"]
                })
                st.table(df_cont_tuition)

            with st.expander("📌 3. Freshman Merit Scholarships (High School % Requirement)"):
                df_scholarships = pd.DataFrame({
                    "Category": ["1st Category (30%)", "2nd Category (15%)", "3rd Category (0%)"],
                    "ENGR": ["Above 90%", "85% to 90%", "Below 85%"],
                    "CS": ["Above 85%", "75% to 85%", "Below 75%"],
                    "BBA": ["Above 85%", "75% to 85%", "Below 75%"],
                    "BioTech": ["Above 85%", "75% to 85%", "Below 75%"]
                })
                st.table(df_scholarships)
                st.info("💡 Note: 5% extra scholarship is granted for excellence in sports.")

            with st.expander("📌 4. Maintenance of Scholarship in Subsequent Years (GPA)"):
                df_maint_sch = pd.DataFrame({
                    "Category": ["100% Scholarship", "1st Category (40%)", "2nd Category (20%)", "3rd Category (0%)"],
                    "Cumulative GPA Required": ["4.0", "3.8 to less than 4.0", "3.5 to less than 3.8", "Below 3.5"]
                })
                st.table(df_maint_sch)

            with st.expander("📌 5. Postgraduate (PG) Tuition"):
                df_pg = pd.DataFrame({
                    "Graduate Program": ["ITCS, EAS, MOT", "EMBA"],
                    "Egyptian (Price / CH)": ["3,000 EGP", "3,500 EGP"],
                    "Non-Egyptian (Price / CH)": ["6,000 EGP", "7,000 EGP"]
                })
                st.table(df_pg)
            
            st.info("💡 **Compulsory Extra Fees (All UG Students):** Activities & Student Union = 600 EGP (Annual).")

        elif sel_doc_year == "2025/2026":
            st.success("✨ Digital extraction available for this academic year based on the official policy document.")

            with st.expander("📌 1. Undergraduate Tuition Fees (New Students - Fall 25)", expanded=True):
                df_new_25 = pd.DataFrame({
                    "College / Program": ["EAS (Engineering)", "ITCS (Computer Science)", "SBA (Business)", "STCH (Biotech)"],
                    "Egyptian Price / Credit Hour (EGP)": ["4,600", "4,600", "3,625", "4,370"],
                    "Total per Year (EGP)": ["165,600", "165,600", "123,250", "152,950"],
                    "Non-Egyptian (Per Year in USD)": ["$6,646", "$6,646", "$5,133", "$6,185"]
                })
                st.table(df_new_25)

            with st.expander("📌 2. Undergraduate Tuition Fees (Continuing Students)"):
                st.markdown("**Joined in 2024:**")
                df_cont_24 = pd.DataFrame({
                    "College / Program": ["EAS (Engineering)", "ITCS (Computer Science)", "SBA (Business)", "STCH (Biotech)"],
                    "Egyptian Price / Credit Hour (EGP)": ["4,431", "4,431", "3,623", "4,368"]
                })
                st.table(df_cont_24)

                st.markdown("**Joined in 2023:**")
                df_cont_23 = pd.DataFrame({
                    "College / Program": ["EAS (Engineering)", "ITCS (Computer Science)", "SBA (Business)", "STCH (Biotech)"],
                    "Egyptian Price / Credit Hour (EGP)": ["4,023", "3,584", "3,482", "3,518"]
                })
                st.table(df_cont_23)

                st.markdown("**Joined in 2022 & Before:**")
                df_cont_22 = pd.DataFrame({
                    "College / Program": ["EAS (Engineering)", "ITCS (Computer Science)", "SBA (Business)", "STCH (Biotech)"],
                    "Egyptian Price / Credit Hour (EGP)": ["3,848", "3,340", "3,065", "2,977"]
                })
                st.table(df_cont_22)

            with st.expander("📌 3. Freshman Merit Scholarships (High School % Requirement)"):
                df_scholarships_25 = pd.DataFrame({
                    "Category": ["Special (100%)", "1st Category (50%)", "2nd Category (40%)", "3rd Category (20%)", "4th Category (0%)"],
                    "EAS / ITCS": ["Top 500", "90% & above", "85% to 90%", "80% to 85%", "Below 80%"],
                    "SBA / STCH": ["Top 500", "80% & above", "75% to 80%", "70% to 75%", "Below 70%"]
                })
                st.table(df_scholarships_25)
                st.info("💡 Note: 100% Scholarship is also offered to 20 top STEM students. 5% extra for sports. 10% for siblings/Gov employees.")

            with st.expander("📌 4. Maintenance of Scholarship in Subsequent Years (GPA)"):
                df_maint_sch_25 = pd.DataFrame({
                    "Category": ["100% Scholarship", "1st Category (50%)", "2nd Category (40%)", "3rd Category (20%)", "4th Category (0%)"],
                    "Cumulative GPA Required": ["4.00", "3.90 to less than 4.00", "3.80 to less than 3.90", "3.50 to less than 3.80", "Below 3.50"]
                })
                st.table(df_maint_sch_25)

            with st.expander("📌 5. Postgraduate (PG) Tuition"):
                df_pg_25 = pd.DataFrame({
                    "Graduate Program": ["ITCS, EAS, MOT, etc.", "EMBA"],
                    "Egyptian (Price / CH)": ["3,000 EGP", "3,500 EGP"],
                    "Non-Egyptian (Price / CH)": ["200 USD", "235 USD"]
                })
                st.table(df_pg_25)

            st.info("💡 **Compulsory Extra Fees (All UG Students):** Activities & Student Union = 1000 EGP (Annual).")

        else:
            st.info("📌 Digital extraction is not yet available for this year. Please refer to the attached PDF above.")

    elif doc_action == "📤 Upload New Document (Admin Only)":
        if st.session_state.get('logged_in_user') == 'fin_admin':
            with st.form("upload_doc_form", clear_on_submit=True):
                doc_title = st.text_input("Document Title *", placeholder="e.g., Financial Policy 2025/2026")
                
                year_options = [f"{y}/{y+1}" for y in range(2020, 2030)]
                doc_year = st.selectbox("Academic Year *", year_options, index=5) 
                
                doc_file = st.file_uploader("Select PDF File *", type=['pdf'])
                
                submit_doc = st.form_submit_button("📤 Upload Document")
                
                if submit_doc:
                    if not doc_title or not doc_file:
                        st.error("⚠️ Title and PDF file are required.")
                    else:
                        try:
                            file_bytes = doc_file.read()
                            new_doc = PolicyDocument(
                                title=doc_title,
                                academic_year=doc_year,
                                file_name=doc_file.name,
                                file_data=file_bytes,
                                uploaded_by=st.session_state.get('logged_in_user')
                            )
                            session.add(new_doc)
                            session.commit()
                            st.session_state['flash_msg'] = f"✅ Document '{doc_title}' uploaded successfully!"
                            st.rerun()
                        except Exception as e:
                            session.rollback()
                            st.error(f"❌ Upload failed: {e}")
        else:
            st.error("🔒 **Access Denied:** Only System Administrators ('fin_admin') can upload official documents.")

# -------------------------------------------------------
# TAB 8: Management Reports
# -------------------------------------------------------
with tab4:
    st.subheader("📈 Financial Management Reports")

    if 'report_params' not in st.session_state:
        st.session_state['report_params'] = None

    with st.form("reports_filter_form", clear_on_submit=False):
        col_f1, col_f2, col_f3 = st.columns(3)
        sel_col = col_f1.multiselect("Filter by College", all_colleges)
        sel_term = col_f2.multiselect("Filter by Term", ["Fall", "Spring", "Summer"])
        sel_year = col_f3.multiselect("Filter by Year", available_years)
        
        col_f4, col_f5 = st.columns([1, 2])
        sel_dates = col_f4.date_input("Date Range (For Period Closing)", [])
        rep_v = col_f5.radio("Format:", ["Accounting Summary", "Full Detailed Log", "Period Closing (Activity Summary)"], horizontal=True)
        
        gen_btn = st.form_submit_button("📂 Generate Report Data")

    if gen_btn:
        st.session_state['report_params'] = {
            'col': sel_col, 'term': sel_term, 'year': sel_year, 
            'dates': sel_dates, 'format': rep_v
        }

    if st.session_state.get('report_params'):
        p = st.session_state['report_params']
        with st.spinner("Processing Data..."):
            if p['format'] == "Accounting Summary":
                sql = text("""
                    SELECT
                        s.id AS "ID",
                        s.name AS "Student Name",
                        s.college AS "College",
                        s.email AS "Email",
                        s.price_per_hr AS "Price/Hr",
                        COALESCE(SUM(t.hours_change), 0) AS "Reg. Hours",
                        COALESCE(SUM(CASE WHEN t.transaction_type IN ('Invoice', 'Bulk Invoices (Tuition)') THEN t.debit ELSE 0 END), 0) AS "Tuition Billed",
                        COALESCE(SUM(CASE WHEN t.transaction_type IN ('Other Fees', 'Bulk Other Fees') THEN t.debit ELSE 0 END), 0) AS "Other Fees",
                        COALESCE(SUM(CASE WHEN t.transaction_type IN ('Discount', 'Bulk Scholarships') THEN t.credit - t.debit ELSE 0 END), 0) AS "Discounts",
                        COALESCE(SUM(CASE WHEN t.transaction_type IN ('Payment Receipt', 'Bulk Payments') THEN t.credit - t.debit ELSE 0 END), 0) AS "Payments",
                        COALESCE(SUM(CASE WHEN t.transaction_type IN ('Credit Hours Adjustment', 'Credit Hours Adjustments', 'General Adjustment', 'General Adjustments') THEN t.debit - t.credit ELSE 0 END), 0) AS "Adjustments",
                        COALESCE(SUM(t.debit) - SUM(t.credit), 0) AS "Balance"
                    FROM students s
                    LEFT JOIN transactions t ON s.id = t.student_id
                        AND (:t_cnt = 0 OR t.term IN :trms)
                        AND (:y_cnt = 0 OR t.academic_year IN :yrs)
                    WHERE (:c_cnt = 0 OR s.college IN :cls)
                    GROUP BY s.id, s.name, s.college, s.email, s.price_per_hr
                    ORDER BY s.id
                """)
                params = {
                    "c_cnt": len(p['col']), "cls": tuple(p['col']) if p['col'] else ('',),
                    "t_cnt": len(p['term']), "trms": tuple(p['term']) if p['term'] else ('',),
                    "y_cnt": len(p['year']), "yrs": tuple(p['year']) if p['year'] else (-1,)
                }
                res = session.execute(sql, params).fetchall()
                df = pd.DataFrame(res, columns=["ID", "Student Name", "College", "Email", "Price/Hr", "Reg. Hours", "Tuition Billed", "Other Fees", "Discounts", "Payments", "Adjustments", "Balance"])
                st.dataframe(df.style.format({
                    "Price/Hr": "{:,.2f}", "Reg. Hours": "{:,.1f}", "Tuition Billed": "{:,.2f}", "Other Fees": "{:,.2f}",
                    "Discounts": "{:,.2f}", "Payments": "{:,.2f}", "Adjustments": "{:,.2f}", "Balance": "{:,.2f}"
                }), use_container_width=True)

            elif p['format'] == "Period Closing (Activity Summary)":
                if len(p['dates']) != 2:
                    st.warning("⚠️ Please select a Date Range (Start Date & End Date) to generate the Period Closing report.")
                else:
                    st.info(f"💡 Showing NET ACTIVITIES strictly occurring between **{p['dates'][0]}** and **{p['dates'][1]}**.")
                    sql = text("""
                        SELECT
                            s.id AS "ID",
                            s.name AS "Student Name",
                            s.college AS "College",
                            COALESCE(SUM(t.hours_change), 0) AS "CH Changed",
                            COALESCE(SUM(CASE WHEN t.transaction_type IN ('Invoice', 'Bulk Invoices (Tuition)') THEN t.debit ELSE 0 END), 0) AS "Tuition Billed",
                            COALESCE(SUM(CASE WHEN t.transaction_type IN ('Other Fees', 'Bulk Other Fees') THEN t.debit ELSE 0 END), 0) AS "Other Fees",
                            COALESCE(SUM(CASE WHEN t.transaction_type IN ('Discount', 'Bulk Scholarships') THEN t.credit - t.debit ELSE 0 END), 0) AS "New Discounts",
                            COALESCE(SUM(CASE WHEN t.transaction_type IN ('Payment Receipt', 'Bulk Payments') THEN t.credit - t.debit ELSE 0 END), 0) AS "Payments Received",
                            COALESCE(SUM(CASE WHEN t.transaction_type IN ('Credit Hours Adjustment', 'Credit Hours Adjustments', 'General Adjustment', 'General Adjustments') THEN t.debit - t.credit ELSE 0 END), 0) AS "Adjustments",
                            COALESCE(SUM(t.debit) - SUM(t.credit), 0) AS "Net Period Change"
                        FROM transactions t
                        JOIN students s ON t.student_id = s.id
                        WHERE (:c_cnt = 0 OR s.college IN :cls)
                          AND (:t_cnt = 0 OR t.term IN :trms)
                          AND (:y_cnt = 0 OR t.academic_year IN :yrs)
                          AND t.entry_date >= :s_date AND t.entry_date <= :e_date
                        GROUP BY s.id, s.name, s.college
                        HAVING COALESCE(SUM(t.debit), 0) > 0 OR COALESCE(SUM(t.credit), 0) > 0
                        ORDER BY s.id
                    """)
                    params = {
                        "c_cnt": len(p['col']), "cls": tuple(p['col']) if p['col'] else ('',),
                        "t_cnt": len(p['term']), "trms": tuple(p['term']) if p['term'] else ('',),
                        "y_cnt": len(p['year']), "yrs": tuple(p['year']) if p['year'] else (-1,),
                        "s_date": p['dates'][0], "e_date": p['dates'][1]
                    }
                    res = session.execute(sql, params).fetchall()
                    if res:
                        df = pd.DataFrame(res, columns=["ID", "Student Name", "College", "CH Changed", "Tuition Billed", "Other Fees", "New Discounts", "Payments Received", "Adjustments", "Net Period Change"])
                        st.dataframe(df.style.format({
                            "CH Changed": "{:,.1f}", "Tuition Billed": "{:,.2f}", "Other Fees": "{:,.2f}",
                            "New Discounts": "{:,.2f}", "Payments Received": "{:,.2f}", 
                            "Adjustments": "{:,.2f}", "Net Period Change": "{:,.2f}"
                        }), use_container_width=True)
                    else:
                        df = pd.DataFrame()
                        st.warning("No financial activity found in the selected date range.")

            else:
                sql = text("""
                    SELECT t.student_id, s.name, s.college, t.reference_no, t.entry_date,
                           t.term, t.academic_year, t.description, t.hours_change AS "Hours",
                           t.debit, t.credit
                    FROM transactions t
                    JOIN students s ON t.student_id = s.id
                    WHERE (:c_cnt = 0 OR s.college IN :cls)
                      AND (:t_cnt = 0 OR t.term IN :trms)
                      AND (:y_cnt = 0 OR t.academic_year IN :yrs)
                      AND (:has_dates = 0 OR (t.entry_date >= :s_date AND t.entry_date <= :e_date))
                    ORDER BY t.student_id, t.entry_date DESC
                """)
                params = {
                    "c_cnt": len(p['col']), "cls": tuple(p['col']) if p['col'] else ('',),
                    "t_cnt": len(p['term']), "trms": tuple(p['term']) if p['term'] else ('',),
                    "y_cnt": len(p['year']), "yrs": tuple(p['year']) if p['year'] else (-1,),
                    "has_dates": 1 if len(p['dates']) == 2 else 0,
                    "s_date": p['dates'][0] if len(p['dates']) == 2 else None,
                    "e_date": p['dates'][1] if len(p['dates']) == 2 else None
                }
                res = session.execute(sql, params).fetchall()
                df = pd.DataFrame(res, columns=["ID", "Student Name", "College", "Ref No", "Date", "Term", "Year", "Description", "Hours", "Debit", "Credit"])
                st.dataframe(df.style.format({"Hours": "{:,.1f}", "Debit": "{:,.2f}", "Credit": "{:,.2f}"}), use_container_width=True)

            if not df.empty:
                buf = io.BytesIO()
                df.to_excel(buf, index=False)
                st.download_button(
                    label="📗 Download Excel Report", data=buf.getvalue(),
                    file_name=f"Management_Report_{p['format'].replace(' ', '_')}.xlsx", use_container_width=True
                )
