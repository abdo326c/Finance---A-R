import os
import re
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Date
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func, text
from datetime import datetime
from fpdf import FPDF
import io

# =======================================================
# 1. Database Configuration & Connection (Direct Link)
# =======================================================
DB_URL = "postgresql://postgres.njqjgvfvxtdxrabidkje:Finance01017043056@aws-0-eu-west-1.pooler.supabase.com:6543/postgres"
DEFAULT_YEAR = 2026

engine = create_engine(DB_URL)
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

class Transaction(Base):
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    reference_no = Column(String, unique=True)
    batch_id = Column(String, nullable=True)  # 💡 عمود الباتش الجديد
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

Session = sessionmaker(bind=engine)
session = Session()

# 💡 إضافة Nu Share أوتوماتيك لو مش موجودة
try:
    if not session.query(ScholarshipType).filter_by(name="Nu Share").first():
        session.add(ScholarshipType(name="Nu Share"))
        session.commit()
except Exception:
    session.rollback()

# جلب البيانات المساعدة لملء الفلاتر والاختيارات
try:
    sch_map = {sch.name: sch.id for sch in session.query(ScholarshipType).all()}
    all_colleges = [c[0] for c in session.query(Student.college).distinct().all() if c[0]]
    available_years = [y[0] for y in session.query(Transaction.academic_year).distinct().all() if y[0]] or [DEFAULT_YEAR]
except:
    sch_map = {}
    all_colleges = []
    available_years = [DEFAULT_YEAR]

# =======================================================
# 3. Authentication & Helper Functions
# =======================================================
USERS = {
    "abdo_finance": "Finance2026",
    "fin_admin": "NU_2026"
}

if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

def login_form():
    st.markdown("<h2 style='text-align: center;'>🔒 Nile University Finance Login</h2>", unsafe_allow_html=True)
    with st.form("login_form"):
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            if user in USERS and USERS[user] == pwd:
                st.session_state['authenticated'] = True
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
# 4. PDF Generator (Landscape Statement with Footer)
# =======================================================
class PDFStatement(FPDF):
    def footer(self):
        # 💡 الفوتر الجديد: يظهر أسفل كل صفحة
        self.set_y(-15)
        self.set_font("helvetica", "I", 10)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, "Finance Department  ||  A/R Team", 0, 0, 'C')

def create_pdf(sid, student_name, df, net_balance):
    pdf = PDFStatement(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    
    pdf.set_font("helvetica", 'B', 16)
    pdf.cell(0, 15, "Nile University - Student Statement of Account", ln=True, align='C')
    
    pdf.set_font("helvetica", '', 11)
    pdf.cell(0, 7, f"Student: {student_name} ({sid})", ln=True, align='L')
    pdf.cell(0, 7, f"Report Date: {datetime.now().strftime('%d-%b-%Y')}", ln=True, align='L')
    pdf.ln(5)
    
    # Table Header
    pdf.set_fill_color(52, 73, 94)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", 'B', 10)
    
    headers = ["Ref No", "Date", "Term", "Year", "Type", "Description", "Debit", "Credit"]
    widths = [30, 25, 20, 15, 35, 90, 30, 30]
    
    for head, width in zip(headers, widths):
        pdf.cell(width, 10, head, 1, 0, 'C', True)
    pdf.ln()
    
    # Table Rows
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", '', 9)
    for _, row in df.iterrows():
        pdf.cell(30, 8, str(row['Ref No']), 1)
        pdf.cell(25, 8, str(row['Date']), 1)
        pdf.cell(20, 8, str(row['Term']), 1)
        pdf.cell(15, 8, str(row['Year']), 1)
        pdf.cell(35, 8, str(row['Type'])[:18], 1)
        pdf.cell(90, 8, str(row['Description'])[:55], 1)
        
        debit_val = str(row['Debit']).replace(',', '')
        credit_val = str(row['Credit']).replace(',', '')
        
        pdf.cell(30, 8, debit_val, 1, 0, 'R')
        pdf.cell(30, 8, credit_val, 1, 1, 'R')
        
    pdf.ln(8)
    pdf.set_font("helvetica", 'B', 14)
    pdf.cell(0, 10, f"NET BALANCE: {net_balance:,.2f} EGP", ln=True, align='R')
    
    return bytes(pdf.output())

# =======================================================
# 5. Main UI Layout
# =======================================================
st.set_page_config(page_title="Finance A/R System", layout="wide", page_icon="🏦")

if not st.session_state['authenticated']:
    login_form()
    st.stop()

if 'flash_msg' not in st.session_state:
    st.session_state['flash_msg'] = None

# Header Area
col_title, col_logout = st.columns([0.8, 0.2], vertical_alignment="center")
with col_title:
    st.title("🏦 Nile University - Finance A/R System")
with col_logout:
    if st.button("🚪 Log out", use_container_width=True, key="main_logout"):
        st.session_state['authenticated'] = False
        st.rerun()

st.markdown("---")

if st.session_state['flash_msg']:
    st.success(st.session_state['flash_msg'])
    st.session_state['flash_msg'] = None

tab_search, tab_reg, tab1, tab2, tab3, tab_batch, tab4 = st.tabs([
    "🔍 Student Lookup", 
    "👤 Registration", 
    "📊 Operations", 
    "📜 Statement & Search", 
    "📤 Bulk Financials",
    "🗑️ Batch Management", 
    "📈 Management Reports"
])

# -------------------------------------------------------
# TAB 0: Student Lookup & Export (Live / No Form)
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
                            st.error(f"❌ Error updating student: {e}")
        else:
            st.warning("⚠️ No student found with this ID.")
            
    st.markdown("---")
    st.subheader("📥 Export Master Data")
    
    all_students = session.query(Student).all()
    if all_students:
        df_all_students = pd.DataFrame([{
            "Student ID": s.id,
            "Full Name": s.name,
            "College Code": s.college,
            "Program": s.program,
            "Price Per Hour (EGP)": s.price_per_hr,
            "University Email": s.email,
            "Mobile Number": s.mobile,
            "National ID": s.national_id,
            "Nationality": s.nationality,
            "Birth Date": s.birth_date,
            "Admit Year": s.admit_year
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
# TAB 0.5: Registration (With Clear Cache)
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
                                id=n_id, 
                                name=n_name, 
                                college=n_college.upper(), 
                                program=n_program, 
                                price_per_hr=n_price, 
                                email=n_email, 
                                mobile=n_mobile, 
                                national_id=n_nat_id, 
                                nationality=n_nationality, 
                                admit_year=n_admit, 
                                birth_date=n_dob
                            )
                            session.add(new_s)
                            session.commit()
                            st.session_state['flash_msg'] = f"✅ Student '{n_name}' has been registered! Form cleared automatically."
                            st.rerun()
                        except Exception as e:
                            session.rollback()
                            st.error(f"❌ Error: {e}")
    else:
        std_ex = {
            "ID": 26100123, 
            "Name": "Ahmed Ali", 
            "College": "ENG", 
            "Program": "Computer Eng", 
            "Price Per Hr": 4600.0, 
            "Email": "ahmed@nu.edu.eg", 
            "Mobile": "01000000000", 
            "National ID": "29901010000000", 
            "Nationality": "Egyptian", 
            "Admit Year": DEFAULT_YEAR, 
            "Birth Date": "2005-01-01"
        }
        buf_std = io.BytesIO()
        pd.DataFrame([std_ex]).to_excel(buf_std, index=False)
        
        st.download_button(
            label="📥 Download Students Template", 
            data=buf_std.getvalue(), 
            file_name="Template_Bulk_Students.xlsx"
        )
        
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
                            id=sid, 
                            name=str(r.get('Name', 'Unknown')), 
                            college=str(r.get('College', 'N/A')).upper(), 
                            program=str(r.get('Program', '')), 
                            price_per_hr=float(r.get('Price Per Hr', 0.0)), 
                            email=str(r.get('Email', '')), 
                            mobile=str(r.get('Mobile', '')), 
                            national_id=str(r.get('National ID', '')), 
                            nationality=str(r.get('Nationality', 'Egyptian')), 
                            admit_year=int(r.get('Admit Year', DEFAULT_YEAR)), 
                            birth_date=bd_clean
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
                    st.warning("⚠️ No new students added. Ensure the IDs are correct and not already registered.")

# -------------------------------------------------------
# TAB 1: Manual Operations (With Clear Cache)
# -------------------------------------------------------
with tab1:
    st.subheader("Post Manual Transaction")
    
    a_t = st.selectbox(
        "Select Action Type", 
        ["Payment Receipt", "Apply Scholarship", "Credit Hours Adjustment", "Other Fees"], 
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
            
        elif a_t == "Apply Scholarship":
            s_n = st.selectbox("Scholarship Category", list(sch_map.keys()))
            pct = st.number_input("Percentage %")
            
        elif a_t == "Credit Hours Adjustment":
            h = st.number_input("Hours Delta (+/-)")
            
        elif a_t == "Other Fees":
            amt = st.number_input("Fee Amount")
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
                    dr = 0.0
                    cr = 0.0
                    dsc = ""
                    sch_id = None
                    pfx = "TX"
                    h_change = 0.0 
                    
                    if a_t == "Payment Receipt":
                        pfx = "PAY"
                        cr = amt
                        dsc = f"Bank: {b_n} | Ref: {b_r}"
                        
                    elif a_t == "Apply Scholarship":
                        pfx = "SCH"
                        sch_id = sch_map.get(s_n)
                        
                        registered_hours = session.query(func.sum(Transaction.hours_change)).filter(
                            Transaction.student_id == sid, 
                            Transaction.term == et, 
                            Transaction.academic_year == ey
                        ).scalar() or 0.0
                        
                        if registered_hours <= 0:
                            st.error(f"⚠️ Cannot apply scholarship! {s_d.name} has NO registered hours for {et} {ey}. Post Tuition Invoice first.")
                            st.stop()

                        existing_pct = 0.0
                        existing_txs = session.query(Transaction.description).filter(
                            Transaction.student_id == sid, 
                            Transaction.term == et, 
                            Transaction.academic_year == ey, 
                            Transaction.reference_no.like('SCH-%')
                        ).all()
                        
                        for tx in existing_txs:
                            m = re.search(r'\((\d+(\.\d+)?)%\)', tx[0])
                            if m: 
                                existing_pct += float(m.group(1))
                                
                        available_pct = max(0.0, 100.0 - existing_pct)
                        actual_pct = min(pct, available_pct)
                        
                        cr = (registered_hours * rate * (actual_pct / 100))
                        dsc = f"Scholarship: {s_n} ({actual_pct}%)"
                        if actual_pct < pct:
                            dsc += f" (Capped from {pct}%)"
                            
                    elif a_t == "Credit Hours Adjustment":
                        pfx = "ADJ"
                        val = abs(h * rate)
                        dr = val if h > 0 else 0
                        cr = val if h < 0 else 0
                        dsc = f"Adj: {h} CH @ {rate:,.2f}"
                        h_change = h 
                        
                    elif a_t == "Other Fees":
                        pfx = "INV"
                        dr = amt
                        dsc = dsc_input

                    m_id = get_next_ref_sequence(session)
                    
                    new_tx = Transaction(
                        reference_no=f"{pfx}-{m_id+1:06d}", 
                        student_id=sid, 
                        scholarship_type_id=sch_id, 
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
                    session.commit()
                    
                    st.session_state['flash_msg'] = f"✅ Successfully Posted Transaction: {new_tx.reference_no} for {s_d.name}!"
                    st.rerun()

# -------------------------------------------------------
# TAB 2: Transaction Search & Statement (Live)
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
            'sys': sys_ref_search,
            'bank': bank_ref_search,
            'dates': df_r,
            'terms': s_t,
            'years': s_y
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
                    "Student ID": s.id, 
                    "Name": s.name, 
                    "Ref No": t.reference_no, 
                    "Date": t.entry_date, 
                    "Term": t.term, 
                    "Year": t.academic_year, 
                    "Type": t.transaction_type, 
                    "Description": t.description, 
                    "Debit": f"{t.debit:,.2f}", 
                    "Credit": f"{t.credit:,.2f}"
                } for t, s in res])
                
                st.table(df_display)
                
                if p['sid'] > 0:
                    net = sum(t.debit for t, s in res) - sum(t.credit for t, s in res)
                    st.metric("Net Balance Due", f"{net:,.2f} EGP")
                    
                    df_pdf = pd.DataFrame([{
                        "Ref No": t.reference_no, 
                        "Date": t.entry_date, 
                        "Term": t.term, 
                        "Year": t.academic_year, 
                        "Type": t.transaction_type, 
                        "Description": t.description, 
                        "Debit": f"{t.debit:,.2f}", 
                        "Credit": f"{t.credit:,.2f}"
                    } for t, s in res])
                    
                    b1, b2 = st.columns(2)
                    with b1:
                        student_name = res[0][1].name
                        pdf_data = create_pdf(p['sid'], student_name, df_pdf, net)
                        st.download_button(
                            label="📄 Download PDF Statement", 
                            data=pdf_data, 
                            file_name=f"SOA_{p['sid']}.pdf", 
                            use_container_width=True
                        )
                    with b2:
                        excel_buf = io.BytesIO()
                        df_display.to_excel(excel_buf, index=False)
                        st.download_button(
                            label="📗 Download Excel Sheet", 
                            data=excel_buf.getvalue(), 
                            file_name=f"SOA_{p['sid']}.xlsx", 
                            use_container_width=True
                        )
            else:
                st.info("💡 You are viewing global search results. To generate a PDF Statement with Balance, please search using a specific Student ID.")
                if df_display is not None:
                    excel_buf = io.BytesIO()
                    df_display.to_excel(excel_buf, index=False)
                    st.download_button(
                        label="📗 Download Search Results (Excel)", 
                        data=excel_buf.getvalue(), 
                        file_name="Transaction_Search.xlsx", 
                        use_container_width=True
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
        ["Bulk Payments", "Bulk Scholarships", "Bulk Invoices (Tuition)", "Bulk Other Fees", "Credit Hours Adjustments", "Update Student Rates", "General Adjustments"], 
        horizontal=True
    )
    
    if b_t == "Bulk Scholarships":
        st.error("🛑 **CRITICAL WARNING:** The 'Scholarship Name' in your Excel file MUST MATCH EXACTLY as written below (including spaces, caps, and the '%' sign). Any typo will cause the system to skip the discount.")
        st.markdown("📋 **Available Scholarships (Hover over any name and click the 📋 Copy icon on the right):**")
        
        sch_names = list(sch_map.keys())
        cols = st.columns(3)
        for i, name in enumerate(sch_names):
            with cols[i % 3]:
                st.code(name, language=None)
                
    st.warning("⚠️ **IMPORTANT:** DELETE the Example Row (ID: 0) before uploading.")
    
    ex = {
        "Bulk Payments": {"ID": 0, "Bank Name": "Bank", "Bank Ref": "REF123", "Amount": 0.0, "Date": "2026-04-17", "Term": "Spring", "Year": DEFAULT_YEAR},
        "Bulk Scholarships": {"ID": 0, "Scholarship Name": "Name", "Percentage": 0.0, "Date": "2026-04-17", "Term": "Spring", "Year": DEFAULT_YEAR},
        "Bulk Invoices (Tuition)": {"ID": 0, "Hours": 15.0, "Date": "2026-04-17", "Term": "Spring", "Year": DEFAULT_YEAR},
        "Bulk Other Fees": {"ID": 0, "Fee Amount": 1500.0, "Description": "Bus Subscription", "Date": "2026-04-17", "Term": "Spring", "Year": DEFAULT_YEAR},
        "Credit Hours Adjustments": {"ID": 0, "Hours_Delta": 3.0, "Date": "2026-04-17", "Term": "Spring", "Year": DEFAULT_YEAR},
        "Update Student Rates": {"ID": 0, "New_Price_Per_Hr": 5500.0},
        "General Adjustments": {"ID": 0, "Debit": 0.0, "Credit": 0.0, "Date": "2026-04-17", "Term": "Spring", "Year": DEFAULT_YEAR, "Description": "DELETE"}
    }
    
    buf_t = io.BytesIO()
    pd.DataFrame([ex[b_t]]).to_excel(buf_t, index=False)
    st.download_button(
        label="📥 Download Template", 
        data=buf_t.getvalue(), 
        file_name=f"Tpl_{b_t}.xlsx"
    )
    
    u_f = st.file_uploader("Upload Excel File", type=['xlsx'])
    
    if u_f and st.button("🚀 Run Bulk Process"):
        with st.spinner("Processing..."):
            # 💡 توليد رقم الباتش الجديد
            current_batch_id = f"BCH-{datetime.now().strftime('%y%m%d-%H%M%S')}"
            
            df_b = pd.read_excel(u_f)
            
            df_b.columns = [str(c).strip() for c in df_b.columns]
            numeric_columns = ['Amount', 'Percentage', 'Hours', 'Hours_Delta', 'Fee Amount', 'Debit', 'Credit', 'New_Price_Per_Hr']
            for col in numeric_columns:
                if col in df_b.columns:
                    df_b[col] = pd.to_numeric(df_b[col].astype(str).str.replace(',', '').str.replace('%', '').str.strip(), errors='coerce').fillna(0.0)

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
                term_pct_cache = {}
                
                tx_counter = 1 
                
                for i, r in df_b.iterrows():
                    sid = int(r.get('ID', 0)) if pd.notnull(r.get('ID')) else 0
                    if sid == 0 or sid not in rts: 
                        continue
                        
                    rt = rts[sid]
                    dr = 0.0
                    cr = 0.0
                    pfx = "TX"
                    s_id = None
                    h_change = 0.0 
                    
                    raw_desc = str(r.get('Description', '')).strip()
                    dsc = b_t if not raw_desc or raw_desc in ['0', '0.0', 'nan'] else raw_desc
                    
                    if b_t == "Bulk Payments":
                        pfx = "PAY"
                        cr = float(str(r.get('Amount', 0)).replace(',', '').strip() or 0.0)
                        dsc = f"Bank: {r.get('Bank Name')} | Ref: {r.get('Bank Ref')}"
                        
                    elif b_t == "Bulk Scholarships":
                        pfx = "SCH"
                        s_n = str(r.get('Scholarship Name', ''))
                        s_id = sch_map.get(s_n)
                        
                        term_val = str(r.get('Term'))
                        year_val = int(r.get('Year'))
                        
                        registered_hours = session.query(func.sum(Transaction.hours_change)).filter(
                            Transaction.student_id == sid, 
                            Transaction.term == term_val, 
                            Transaction.academic_year == year_val
                        ).scalar() or 0.0
                        
                        if registered_hours <= 0:
                            continue  
                            
                        cache_key = (sid, term_val, year_val)
                        if cache_key not in term_pct_cache:
                            epct = 0.0
                            existing_txs = session.query(Transaction.description).filter(
                                Transaction.student_id == sid, 
                                Transaction.term == term_val, 
                                Transaction.academic_year == year_val, 
                                Transaction.reference_no.like('SCH-%')
                            ).all()
                            for tx in existing_txs:
                                m = re.search(r'\((\d+(\.\d+)?)%\)', tx[0])
                                if m: 
                                    epct += float(m.group(1))
                            term_pct_cache[cache_key] = epct
                            
                        requested_pct = float(str(r.get('Percentage', 0)).replace(',', '').strip() or 0.0)
                        available_pct = max(0.0, 100.0 - term_pct_cache[cache_key])
                        actual_pct = min(requested_pct, available_pct)
                        term_pct_cache[cache_key] += actual_pct
                        
                        cr = (registered_hours * rt * (actual_pct / 100))
                        dsc = f"Sch: {s_n} ({actual_pct}%)"
                        if actual_pct < requested_pct:
                            dsc += f" (Capped from {requested_pct}%)"
                            
                    elif b_t == "Bulk Invoices (Tuition)":
                        h = float(str(r.get('Hours', 15.0)).replace(',', '').strip() or 0.0)
                        pfx = "INV"
                        dr = (h * rt)
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
                        batch_id=current_batch_id,  # 💡 تخزين رقم الباتش
                        student_id=sid, 
                        scholarship_type_id=s_id, 
                        transaction_type=b_t, 
                        description=dsc, 
                        debit=dr, 
                        credit=cr, 
                        hours_change=h_change, 
                        entry_date=pd.to_datetime(r.get('Date')).date(), 
                        term=str(r.get('Term')), 
                        academic_year=int(r.get('Year'))
                    )
                    bulk_l.append(new_bulk_tx)
                    tx_counter += 1
                    
                if bulk_l:
                    session.bulk_save_objects(bulk_l)
                    session.commit()
                    st.session_state['flash_msg'] = f"✅ Batch {current_batch_id} Successfully Posted!"
                    st.rerun()

# -------------------------------------------------------
# TAB 5: Batch Management (🗑️ نظام إدارة الباتشات الجديد)
# -------------------------------------------------------
with tab_batch:
    st.subheader("🗑️ Batch Management & Rollback")
    st.markdown("💡 *Here you can view all uploaded batches and safely delete an entire batch if an error occurred.*")
    
    # استخراج ملخص الباتشات من الداتا بيز
    batch_summary = session.query(
        Transaction.batch_id,
        Transaction.transaction_type,
        func.count(Transaction.id).label("record_count"),
        func.sum(Transaction.debit).label("total_debit"),
        func.sum(Transaction.credit).label("total_credit"),
        func.max(Transaction.created_at).label("upload_date")
    ).filter(Transaction.batch_id.isnot(None)).group_by(
        Transaction.batch_id, Transaction.transaction_type
    ).order_by(func.max(Transaction.created_at).desc()).all()
    
    if not batch_summary:
        st.info("No batches found in the system.")
    else:
        # عرض الباتشات في جدول شيك
        df_batches = pd.DataFrame([{
            "Batch ID": b.batch_id,
            "Type": b.transaction_type,
            "Records": b.record_count,
            "Total Debit": f"{b.total_debit:,.2f}",
            "Total Credit": f"{b.total_credit:,.2f}",
            "Uploaded At": b.upload_date.strftime('%Y-%m-%d %H:%M:%S') if b.upload_date else "N/A"
        } for b in batch_summary])
        
        st.dataframe(df_batches, use_container_width=True)
        
        st.markdown("---")
        st.error("🛑 **DANGER ZONE: Batch Deletion**")
        
        # فورم المسح مع حماية التأكيد الإجباري
        with st.form("delete_batch_form"):
            batch_to_delete = st.selectbox("Select Batch ID to Delete:", [b.batch_id for b in batch_summary])
            confirm_delete = st.checkbox(f"⚠️ I confirm that I want to permanently delete all records in '{batch_to_delete}'")
            
            if st.form_submit_button("🗑️ Delete Batch"):
                if confirm_delete:
                    try:
                        deleted_count = session.query(Transaction).filter(Transaction.batch_id == batch_to_delete).delete()
                        session.commit()
                        st.session_state['flash_msg'] = f"✅ Successfully deleted {deleted_count} records from batch {batch_to_delete}."
                        st.rerun()
                    except Exception as e:
                        session.rollback()
                        st.error(f"❌ Error deleting batch: {e}")
                else:
                    st.warning("⚠️ You must check the confirmation box to delete the batch.")

# -------------------------------------------------------
# TAB 6: Management Reports (Live)
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

        rep_v = st.radio("Format:", ["Accounting Summary", "Full Detailed Log"], horizontal=True)
        
        gen_btn = st.form_submit_button("📂 Generate Report Data")

    if gen_btn:
        st.session_state['report_params'] = {
            'col': sel_col,
            'term': sel_term,
            'year': sel_year,
            'format': rep_v
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
                        COALESCE(SUM(CASE WHEN t.reference_no LIKE 'INV-%' THEN t.debit ELSE 0 END), 0) AS "Invoices",
                        COALESCE(SUM(CASE WHEN t.reference_no LIKE 'SCH-%' THEN t.credit ELSE 0 END), 0) AS "Discounts", 
                        COALESCE(SUM(CASE WHEN t.reference_no LIKE 'PAY-%' THEN t.credit ELSE 0 END), 0) AS "Payments",
                        COALESCE(SUM(CASE WHEN t.reference_no LIKE 'ADJ-%' OR t.reference_no LIKE 'TXN-%' THEN t.debit - t.credit ELSE 0 END), 0) AS "Adjustments",
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
                df = pd.DataFrame(res, columns=["ID", "Student Name", "College", "Email", "Price/Hr", "Reg. Hours", "Invoices", "Discounts", "Payments", "Adjustments", "Balance"])
                
                st.dataframe(df.style.format({
                    "Price/Hr": "{:,.2f}", 
                    "Reg. Hours": "{:,.1f}", 
                    "Invoices": "{:,.2f}", 
                    "Discounts": "{:,.2f}", 
                    "Payments": "{:,.2f}", 
                    "Adjustments": "{:,.2f}", 
                    "Balance": "{:,.2f}"
                }), use_container_width=True)

            else:
                sql = text("""
                    SELECT 
                        t.student_id, 
                        s.name, 
                        s.college, 
                        t.reference_no, 
                        t.entry_date, 
                        t.term, 
                        t.academic_year, 
                        t.description, 
                        t.hours_change AS "Hours", 
                        t.debit, 
                        t.credit
                    FROM transactions t 
                    JOIN students s ON t.student_id = s.id
                    WHERE (:c_cnt = 0 OR s.college IN :cls) 
                      AND (:t_cnt = 0 OR t.term IN :trms) 
                      AND (:y_cnt = 0 OR t.academic_year IN :yrs)
                    ORDER BY t.student_id, t.entry_date DESC
                """)
                
                params = {
                    "c_cnt": len(p['col']), "cls": tuple(p['col']) if p['col'] else ('',), 
                    "t_cnt": len(p['term']), "trms": tuple(p['term']) if p['term'] else ('',), 
                    "y_cnt": len(p['year']), "yrs": tuple(p['year']) if p['year'] else (-1,)
                }
                
                res = session.execute(sql, params).fetchall()
                df = pd.DataFrame(res, columns=["ID", "Student Name", "College", "Ref No", "Date", "Term", "Year", "Description", "Hours", "Debit", "Credit"])
                
                st.dataframe(df.style.format({
                    "Hours": "{:,.1f}", 
                    "Debit": "{:,.2f}", 
                    "Credit": "{:,.2f}"
                }), use_container_width=True)
            
            buf = io.BytesIO()
            df.to_excel(buf, index=False)
            st.download_button(
                label="📗 Download Excel Report", 
                data=buf.getvalue(), 
                file_name="AR_Management_Report.xlsx", 
                use_container_width=True
            )
