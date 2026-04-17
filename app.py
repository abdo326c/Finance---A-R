import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Date
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func, text
from datetime import datetime
from fpdf import FPDF
import io

# =======================================================
# 1. Authentication Logic (Security First)
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

# =======================================================
# 2. Database Connection & Comprehensive Models
# =======================================================
DB_URL = "postgresql://postgres.njqjgvfvxtdxrabidkje:Finance01017043056@aws-0-eu-west-1.pooler.supabase.com:6543/postgres"
engine = create_engine(DB_URL)
Base = declarative_base()

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
    college_short = Column(String)
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
    student_id = Column(Integer, ForeignKey('students.id'))
    scholarship_type_id = Column(Integer, ForeignKey('scholarship_types.id'), nullable=True)
    transaction_type = Column(String, nullable=False) 
    description = Column(String)
    debit = Column(Float, default=0)
    credit = Column(Float, default=0)
    entry_date = Column(Date, nullable=False)
    term = Column(String, nullable=False)
    academic_year = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

Session = sessionmaker(bind=engine)
session = Session()

# جلب البيانات المساعدة مع حماية من الأخطاء
try:
    sch_map = {sch.name: sch.id for sch in session.query(ScholarshipType).all()}
    all_colleges = [c[0] for c in session.query(Student.college).distinct().all() if c[0]]
    available_years = [y[0] for y in session.query(Transaction.academic_year).distinct().all() if y[0]] or [2026]
except:
    sch_map = {}; all_colleges = []; available_years = [2026]

# =======================================================
# 3. PDF Generator (Landscape Professional Layout)
# =======================================================
def create_pdf(sid, student_name, df, net_balance):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("helvetica", 'B', 16)
    pdf.cell(0, 15, "Nile University - Official Statement of Account", ln=True, align='C')
    pdf.set_font("helvetica", '', 11)
    pdf.cell(0, 7, f"Student: {student_name} ({sid})", ln=True, align='L')
    pdf.cell(0, 7, f"Report Date: {datetime.now().strftime('%d-%b-%Y')}", ln=True, align='L')
    pdf.ln(5)
    pdf.set_fill_color(52, 73, 94); pdf.set_text_color(255, 255, 255); pdf.set_font("helvetica", 'B', 10)
    h = ["Ref No", "Date", "Term", "Year", "Type", "Description", "Debit", "Credit"]
    w = [30, 25, 20, 15, 35, 90, 30, 30]
    for head, width in zip(h, w): pdf.cell(width, 10, head, 1, 0, 'C', True)
    pdf.ln(); pdf.set_text_color(0, 0, 0); pdf.set_font("helvetica", '', 9)
    for _, r in df.iterrows():
        pdf.cell(30, 8, str(r['Ref No']), 1)
        pdf.cell(25, 8, str(r['Date']), 1)
        pdf.cell(20, 8, str(r['Term']), 1)
        pdf.cell(15, 8, str(r['Year']), 1)
        pdf.cell(35, 8, str(r['Type'])[:18], 1)
        pdf.cell(90, 8, str(r['Description'])[:55], 1)
        pdf.cell(30, 8, f"{float(r['Debit'].replace(',','')):,.2f}", 1, 0, 'R')
        pdf.cell(30, 8, f"{float(r['Credit'].replace(',','')):,.2f}", 1, 1, 'R')
    pdf.ln(8); pdf.set_font("helvetica", 'B', 14); pdf.cell(0, 10, f"NET BALANCE: {net_balance:,.2f} EGP", ln=True, align='R')
    return bytes(pdf.output())

# =======================================================
# 4. User Interface Layout
# =======================================================
st.set_page_config(page_title="Finance A/R System", layout="wide", page_icon="🏦")

if not st.session_state['authenticated']:
    login_form(); st.stop()

# Header Section
col_title, col_logout = st.columns([0.8, 0.2], vertical_alignment="center")
with col_title: st.title("🏦 Nile University - Finance A/R System")
with col_logout:
    if st.button("🚪 Log out", use_container_width=True, key="main_logout"):
        st.session_state['authenticated'] = False; st.rerun()

st.markdown("---")
tab1, tab2, tab3, tab4 = st.tabs(["📊 Operations", "📜 Statement", "📤 Bulk Operations", "📈 Management Reports"])

# --- Tab 1: Manual Operations ---
with tab1:
    st.subheader("Post Manual Transaction")
    sid_raw = st.text_input("Student ID", placeholder="Enter ID...", key="manual_id")
    sid = int(sid_raw) if sid_raw.strip().isdigit() else 0
    a_t = st.selectbox("Action", ["Payment Receipt", "Apply Scholarship", "Credit Hours Adjustment", "Other Fees"], index=1)
    c1, c2, c3 = st.columns(3); ed = c1.date_input("Date"); et = c2.selectbox("Term", ["Fall", "Spring", "Summer"]); ey = c3.number_input("Year", value=ed.year)
    
    dr, cr, dsc, sch_id, pfx = 0.0, 0.0, "", None, "TX"
    s_data = session.query(Student).filter_by(id=sid).first()
    
    if a_t == "Payment Receipt":
        pfx = "PAY"; b_n = st.text_input("Bank Name"); b_r = st.text_input("Ref No"); amt = st.number_input("Amount Paid", min_value=0.0)
        dsc, cr = f"Bank: {b_n} | Ref: {b_r}", amt
    elif a_t == "Apply Scholarship":
        pfx = "SCH"; s_n = st.selectbox("Scholarship Category", list(sch_map.keys())); sch_id = sch_map.get(s_n); pct = st.number_input("Percentage %")
        rate = s_data.price_per_hr if s_data else 0
        cr = (15 * rate * (pct/100)); dsc = f"Scholarship: {s_n} ({pct}%)"
    elif a_t == "Credit Hours Adjustment":
        pfx = "ADJ"; h = st.number_input("Hours Delta (+/-)"); rate = s_data.price_per_hr if s_data else 0
        val = abs(h * rate); dr, cr = (val if h > 0 else 0), (val if h < 0 else 0)
        dsc = f"Adj: {h} CH @ {rate:,.2f}"
    elif a_t == "Other Fees":
        pfx = "INV"; amt = st.number_input("Fee Amount"); dsc = st.text_input("Description"); dr = amt

    if st.button("🚀 Process Transaction"):
        if sid == 0 or not s_data: st.error("Please enter a valid/existing Student ID.")
        else:
            m_id = session.query(func.max(Transaction.id)).scalar() or 0
            new_tx = Transaction(reference_no=f"{pfx}-{m_id+1:06d}", student_id=sid, scholarship_type_id=sch_id, transaction_type=a_t, description=dsc, debit=dr, credit=cr, entry_date=ed, term=et, academic_year=ey)
            session.add(new_tx); session.commit(); st.success("Successfully Posted!"); st.rerun()

# --- Tab 2: Individual Statement ---
with tab2:
    st.subheader("Student Statement of Account")
    search_r = st.text_input("Search Student ID", key="s_search")
    search_id = int(search_r) if search_r.strip().isdigit() else 0
    if search_id > 0:
        s_obj = session.query(Student).filter_by(id=search_id).first()
        if s_obj:
            st.info(f"Student: **{s_obj.name}** | College: {s_obj.college} | Program: {s_obj.program}")
            q = session.query(Transaction).filter(Transaction.student_id == search_id).order_by(Transaction.entry_date.desc()).all()
            if q:
                df = pd.DataFrame([{"Ref No": r.reference_no, "Date": r.entry_date, "Term": r.term, "Year": r.academic_year, "Type": r.transaction_type, "Description": r.description, "Debit": f"{r.debit:,.2f}", "Credit": f"{r.credit:,.2f}"} for r in q])
                st.table(df); net = sum(r.debit for r in q) - sum(r.credit for r in q); st.metric("Net Balance Due", f"{net:,.2f} EGP")
                b1, b2 = st.columns(2)
                with b1: st.download_button("📄 PDF Statement", create_pdf(search_id, s_obj.name, df, net), f"SOA_{search_id}.pdf", use_container_width=True)
                with b2:
                    excel_buf = io.BytesIO(); df.to_excel(excel_buf, index=False)
                    st.download_button("📗 Excel Sheet", excel_buf.getvalue(), f"SOA_{search_id}.xlsx", use_container_width=True)

# --- Tab 3: Bulk Operations ---
with tab3:
    st.subheader("Bulk Operations Management")
    b_t = st.radio("Type:", ["Bulk Payments", "Bulk Scholarships", "Bulk Invoices (Tuition)", "Credit Hours Adjustments", "Update Student Rates", "General Adjustments"], horizontal=True)
    
    ex_cols = {
        "Bulk Payments": ["ID", "Bank Name", "Bank Ref", "Amount", "Date", "Term", "Year"],
        "Bulk Scholarships": ["ID", "Scholarship Name", "Percentage", "Date", "Term", "Year"],
        "Bulk Invoices (Tuition)": ["ID", "Hours", "Date", "Term", "Year"],
        "Credit Hours Adjustments": ["ID", "Hours_Delta", "Date", "Term", "Year"],
        "Update Student Rates": ["ID", "New_Price_Per_Hr"],
        "General Adjustments": ["ID", "Debit", "Credit", "Date", "Term", "Year", "Description"]
    }
    buf_t = io.BytesIO(); pd.DataFrame(columns=ex_cols[b_t]).to_excel(buf_t, index=False)
    st.download_button("📥 Download Template", buf_t.getvalue(), f"Tpl_{b_t}.xlsx")
    
    u_file = st.file_uploader("Upload Excel File", type=['xlsx'])
    if u_file:
        df_bulk = pd.read_excel(u_file)
        if st.button("🚀 Run Bulk Process"):
            with st.spinner("Processing Data..."):
                if b_t == "Update Student Rates":
                    for _, r in df_bulk.iterrows():
                        if int(r['ID']) != 0: session.query(Student).filter(Student.id == int(r['ID'])).update({"price_per_hr": float(r['New_Price_Per_Hr'])})
                else:
                    m_id = session.query(func.max(Transaction.id)).scalar() or 0
                    rts = {s.id: s.price_per_hr for s in session.query(Student).all()}
                    bulk_objs = []
                    for i, r in df_bulk.iterrows():
                        sid = int(r['ID'])
                        if sid == 0 or sid not in rts: continue
                        rt, dr, cr, pfx, s_id, dsc = rts[sid], 0.0, 0.0, "TX", None, b_t
                        if b_t == "Bulk Payments":
                            pfx, cr, dsc = "PAY", float(r['Amount']), f"Bank: {r['Bank Name']} | Ref: {r['Bank Ref']}"
                        elif b_t == "Bulk Scholarships":
                            pfx, s_n = "SCH", str(r['Scholarship Name']); s_id = sch_map.get(s_n); cr = (15 * rt * (float(r['Percentage'])/100)); dsc = f"Sch: {s_n}"
                        elif b_t == "Bulk Invoices (Tuition)":
                            pfx, dr, dsc = "INV", (float(r['Hours']) * rt), f"Tuition Invoice ({r['Hours']} CH)"
                        elif b_t == "Credit Hours Adjustments":
                            pfx, h = "ADJ", float(r['Hours_Delta']); v = abs(h * rt); dr, cr = (v if h > 0 else 0), (v if h < 0 else 0)
                        elif b_t == "General Adjustments":
                            pfx, dr, cr, dsc = "TXN", float(r['Debit']), float(r['Credit']), str(r['Description'])
                        
                        bulk_objs.append(Transaction(reference_no=f"{pfx}-{m_id+i+1:06d}", student_id=sid, scholarship_type_id=s_id, transaction_type=b_t, description=dsc, debit=dr, credit=cr, entry_date=pd.to_datetime(r['Date']).date(), term=str(r['Term']), academic_year=int(r['Year'])))
                    session.bulk_save_objects(bulk_objs)
                session.commit(); st.success("Bulk Success!"); st.rerun()

# --- Tab 4: Management Reports (RE-ENGINEERED) ---
with tab4:
    st.subheader("📈 Financial Management Reports")
    sel_col = st.multiselect("Filter by College", all_colleges)
    rep_v = st.radio("Format:", ["Accounting Summary", "Full Detailed Log"], horizontal=True)
    
    if st.button("📂 Generate & Download"):
        with st.spinner("Compiling Integrated Data..."):
            if rep_v == "Accounting Summary":
                sql = text("""
                    SELECT s.id AS "ID", s.name AS "Student Name", s.college AS "College", s.email AS "Email",
                           COALESCE(SUM(t.debit), 0) AS "Invoices",
                           COALESCE(SUM(CASE WHEN t.reference_no LIKE 'SCH-%' THEN t.credit ELSE 0 END), 0) AS "Discounts",
                           COALESCE(SUM(CASE WHEN t.reference_no LIKE 'PAY-%' THEN t.credit ELSE 0 END), 0) AS "Payments",
                           COALESCE(SUM(t.debit) - SUM(t.credit), 0) AS "Balance"
                    FROM students s LEFT JOIN transactions t ON s.id = t.student_id
                    WHERE (:c_cnt = 0 OR s.college IN :cls)
                    GROUP BY s.id, s.name, s.college, s.email ORDER BY s.id
                """)
                res = session.execute(sql, {"c_cnt": len(sel_col), "cls": tuple(sel_col) if sel_col else ('',)}).fetchall()
                df = pd.DataFrame(res, columns=["ID", "Student Name", "College", "Email", "Invoices", "Discounts", "Payments", "Balance"])
            else:
                sql = text("""
                    SELECT t.student_id, s.name, s.college, t.reference_no, t.entry_date, t.description, t.debit, t.credit
                    FROM transactions t JOIN students s ON t.student_id = s.id
                    WHERE (:c_cnt = 0 OR s.college IN :cls) ORDER BY t.student_id, t.entry_date DESC
                """)
                res = session.execute(sql, {"c_cnt": len(sel_col), "cls": tuple(sel_col) if sel_col else ('',)}).fetchall()
                df = pd.DataFrame(res, columns=["ID", "Name", "College", "Ref", "Date", "Description", "Debit", "Credit"])
            
            st.dataframe(df)
            buf = io.BytesIO(); df.to_excel(buf, index=False)
            st.success("Report Ready!"); st.download_button("📗 Download Excel Report", buf.getvalue(), "AR_Management_Report.xlsx")
