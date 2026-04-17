import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Date
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func, text
from datetime import datetime
from fpdf import FPDF
import io

# =======================================================
# 1. Authentication & Security
# =======================================================
USERS = {"abdo_finance": "Finance2026", "fin_admin": "NU_2026"}

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
                st.rerun()
            else:
                st.error("Invalid Username or Password")

# =======================================================
# 2. Database Engine & Models (The 11 Columns Structure)
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

# Dynamic Data Loading
try:
    sch_map = {sch.name: sch.id for sch in session.query(ScholarshipType).all()}
    all_colleges = [c[0] for c in session.query(Student.college).distinct().all() if c[0]]
    available_years = [y[0] for y in session.query(Transaction.academic_year).distinct().all()] or [2026]
except:
    sch_map, all_colleges, available_years = {}, [], [2026]

# =======================================================
# 3. PDF Reporting Engine (Landscape)
# =======================================================
def create_pdf(sid, student_name, df, net_balance):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("helvetica", 'B', 16)
    pdf.cell(0, 15, "Nile University - Official Statement of Account", ln=True, align='C')
    pdf.set_font("helvetica", '', 11)
    pdf.cell(0, 7, f"Student: {student_name} ({sid}) | Generated: {datetime.now().strftime('%d-%b-%Y')}", ln=True, align='L')
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
        pdf.cell(30, 8, f"{float(str(r['Debit']).replace(',','')):,.2f}", 1, 0, 'R')
        pdf.cell(30, 8, f"{float(str(r['Credit']).replace(',','')):,.2f}", 1, 1, 'R')
    pdf.ln(8); pdf.set_font("helvetica", 'B', 14); pdf.cell(0, 10, f"NET BALANCE: {net_balance:,.2f} EGP", ln=True, align='R')
    return bytes(pdf.output())

# =======================================================
# 4. Main Application Interface
# =======================================================
st.set_page_config(page_title="NU Finance ERP", layout="wide", page_icon="🏦")

if not st.session_state['authenticated']:
    login_form(); st.stop()

# Dashboard Header
c_title, c_logout = st.columns([0.8, 0.2])
with c_title: st.title("🏦 Nile University - Finance A/R System")
with c_logout:
    if st.button("🚪 Log out", use_container_width=True):
        st.session_state['authenticated'] = False; st.rerun()

st.markdown("---")
tab1, tab2, tab3, tab4 = st.tabs(["📊 Operations", "📜 Statement", "📤 Bulk Operations", "📈 Reports"])

# --- TAB 1: Manual Entry ---
with tab1:
    st.subheader("Manual Transaction Posting")
    sid_raw = st.text_input("Student ID", key="man_id")
    sid = int(sid_raw) if sid_raw.strip().isdigit() else 0
    a_t = st.selectbox("Transaction Type", ["Payment Receipt", "Apply Scholarship", "Credit Hours Adjustment", "Other Fees"])
    c1, c2, c3 = st.columns(3); ed = c1.date_input("Entry Date"); et = c2.selectbox("Term", ["Fall", "Spring", "Summer"]); ey = c3.number_input("Academic Year", 2026)
    
    dr, cr, dsc, sch_id, pfx = 0.0, 0.0, "", None, "TX"
    student_obj = session.query(Student).filter_by(id=sid).first()
    
    if a_t == "Payment Receipt":
        pfx = "PAY"; b_name = st.text_input("Bank"); b_ref = st.text_input("Bank Reference"); amt = st.number_input("Amount Paid", 0.0)
        dsc, cr = f"Bank: {b_name} | Ref: {b_ref}", amt
    elif a_t == "Apply Scholarship":
        pfx = "SCH"; s_cat = st.selectbox("Scholarship Category", list(sch_map.keys())); sch_id = sch_map.get(s_cat); pct = st.number_input("Percentage %")
        hr_rate = student_obj.price_per_hr if student_obj else 0
        cr = (15 * hr_rate * (pct/100)); dsc = f"Scholarship: {s_cat} ({pct}%)"
    elif a_t == "Credit Hours Adjustment":
        pfx = "ADJ"; hours = st.number_input("Hours (+/-)"); hr_rate = student_obj.price_per_hr if student_obj else 0
        val = abs(hours * hr_rate); dr, cr = (val if hours > 0 else 0), (val if hours < 0 else 0)
        dsc = f"Adjustment: {hours} CH @ {hr_rate:,.2f}"
    elif a_t == "Other Fees":
        pfx = "INV"; amt = st.number_input("Fee Amount"); dr, dsc = amt, st.text_input("Description")

    if st.button("🚀 Commit to Ledger"):
        if sid > 0 and student_obj:
            max_id = session.query(func.max(Transaction.id)).scalar() or 0
            new_tx = Transaction(reference_no=f"{pfx}-{max_id+1:06d}", student_id=sid, scholarship_type_id=sch_id, transaction_type=a_t, description=dsc, debit=dr, credit=cr, entry_date=ed, term=et, academic_year=ey)
            session.add(new_tx); session.commit(); st.success("Transaction Successfully Posted!"); st.rerun()
        else: st.error("Student ID not found in Master Data.")

# --- TAB 2: Statement of Account ---
with tab2:
    st.subheader("Student Statement Search")
    search_raw = st.text_input("Enter Student ID", key="search_box")
    search_id = int(search_raw) if search_raw.strip().isdigit() else 0
    if search_id > 0:
        s_data = session.query(Student).filter_by(id=search_id).first()
        if s_data:
            st.info(f"Student: **{s_data.name}** | College: {s_data.college} | Program: {s_data.program}")
            res = session.query(Transaction).filter(Transaction.student_id == search_id).order_by(Transaction.entry_date.desc()).all()
            if res:
                df_soa = pd.DataFrame([{"Ref No": r.reference_no, "Date": r.entry_date, "Term": r.term, "Year": r.academic_year, "Type": r.transaction_type, "Description": r.description, "Debit": r.debit, "Credit": r.credit} for r in res])
                st.dataframe(df_soa.style.format({"Debit": "{:,.2f}", "Credit": "{:,.2f}"}), use_container_width=True)
                balance = sum(r.debit for r in res) - sum(r.credit for r in res)
                st.metric("Net Balance", f"{balance:,.2f} EGP")
                c_pdf, c_xls = st.columns(2)
                c_pdf.download_button("📄 PDF Statement", create_pdf(search_id, s_data.name, df_soa, balance), f"SOA_{search_id}.pdf", use_container_width=True)
                buf_xls = io.BytesIO(); df_soa.to_excel(buf_xls, index=False)
                c_xls.download_button("📗 Excel Export", buf_xls.getvalue(), f"SOA_{search_id}.xlsx", use_container_width=True)
        else: st.error("ID not found.")

# --- TAB 3: Bulk Processing (The Full Logic) ---
with tab3:
    st.subheader("Bulk Operations & Data Upload")
    b_mode = st.radio("Select Operation:", ["Bulk Payments", "Bulk Scholarships", "Bulk Invoices (Tuition)", "Credit Hours Adjustments", "Update Student Rates", "General Adjustments"], horizontal=True)
    
    # Template Matrix
    templates = {
        "Bulk Payments": ["ID", "Bank Name", "Bank Ref", "Amount", "Date", "Term", "Year"],
        "Bulk Scholarships": ["ID", "Scholarship Name", "Percentage", "Date", "Term", "Year"],
        "Bulk Invoices (Tuition)": ["ID", "Hours", "Date", "Term", "Year"],
        "Credit Hours Adjustments": ["ID", "Hours_Delta", "Date", "Term", "Year"],
        "Update Student Rates": ["ID", "New_Price_Per_Hr"],
        "General Adjustments": ["ID", "Debit", "Credit", "Date", "Term", "Year", "Description"]
    }
    buf_tpl = io.BytesIO(); pd.DataFrame(columns=templates[b_mode]).to_excel(buf_tpl, index=False)
    st.download_button("📥 Download Excel Template", buf_tpl.getvalue(), f"NU_Template_{b_mode.replace(' ','_')}.xlsx")
    
    uploaded_file = st.file_uploader("Upload Completed Sheet", type=['xlsx'])
    if uploaded_file:
        df_upload = pd.read_excel(uploaded_file)
        if st.button("🚀 Execute Bulk Transaction"):
            with st.spinner("Processing Bulk Data..."):
                if b_mode == "Update Student Rates":
                    for _, row in df_upload.iterrows():
                        if int(row['ID']) != 0: session.query(Student).filter(Student.id == int(row['ID'])).update({"price_per_hr": float(row['New_Price_Per_Hr'])})
                else:
                    current_max = session.query(func.max(Transaction.id)).scalar() or 0
                    price_map = {s.id: s.price_per_hr for s in session.query(Student).all()}
                    bulk_objects = []
                    for i, r in df_upload.iterrows():
                        sid = int(r['ID'])
                        if sid == 0 or sid not in price_map: continue
                        rate, dr, cr, pfx, s_type_id, dsc = price_map[sid], 0.0, 0.0, "TX", None, b_mode
                        
                        if b_mode == "Bulk Payments":
                            pfx, cr, dsc = "PAY", float(r['Amount']), f"Bank: {r['Bank Name']} | Ref: {r['Bank Ref']}"
                        elif b_mode == "Bulk Scholarships":
                            pfx, s_name = "SCH", str(r['Scholarship Name']); s_type_id = sch_map.get(s_name)
                            cr = (15 * rate * (float(r['Percentage'])/100)); dsc = f"Scholarship: {s_name}"
                        elif b_mode == "Bulk Invoices (Tuition)":
                            pfx, dr, dsc = "INV", (float(r['Hours']) * rate), f"Tuition Invoice ({r['Hours']} CH)"
                        elif b_mode == "Credit Hours Adjustments":
                            pfx, h_val = "ADJ", float(r['Hours_Delta']); total = abs(h_val * rate)
                            dr, cr, dsc = (total if h_val > 0 else 0), (total if h_val < 0 else 0), f"Adj: {h_val} CH"
                        elif b_mode == "General Adjustments":
                            pfx, dr, cr, dsc = "ADJ", float(r['Debit']), float(r['Credit']), str(r['Description'])
                        
                        bulk_objects.append(Transaction(reference_no=f"{pfx}-{current_max+i+1:06d}", student_id=sid, scholarship_type_id=s_type_id, transaction_type=b_mode, description=dsc, debit=dr, credit=cr, entry_date=pd.to_datetime(r['Date']).date(), term=str(r['Term']), academic_year=int(r['Year'])))
                    session.bulk_save_objects(bulk_objects)
                session.commit(); st.success("Bulk Posting Complete!"); st.rerun()

# --- TAB 4: Reports (Integrated Names & Financials) ---
with tab4:
    st.subheader("📈 Professional Financial Reporting")
    filter_col = st.multiselect("Filter by College", all_colleges)
    report_type = st.radio("Choose Report Format:", ["Accounting Summary (Names & Balances)", "Detailed Transaction Log"], horizontal=True)
    
    if st.button("📊 Generate Live Report"):
        with st.spinner("Compiling Ledger Data..."):
            if report_type == "Accounting Summary (Names & Balances)":
                sql = text("""
                    SELECT s.id AS "ID", s.name AS "Name", s.college AS "College", s.email AS "Email", 
                           COALESCE(SUM(t.debit), 0) AS "Invoices",
                           COALESCE(SUM(CASE WHEN t.reference_no LIKE 'SCH-%' THEN t.credit ELSE 0 END), 0) AS "Scholarships",
                           COALESCE(SUM(CASE WHEN t.reference_no LIKE 'PAY-%' THEN t.credit ELSE 0 END), 0) AS "Payments",
                           COALESCE(SUM(t.debit) - SUM(t.credit), 0) AS "Balance"
                    FROM students s LEFT JOIN transactions t ON s.id = t.student_id
                    WHERE (:c_cnt = 0 OR s.college IN :cls)
                    GROUP BY s.id, s.name, s.college, s.email ORDER BY s.id
                """)
                rows = session.execute(sql, {"c_cnt": len(filter_col), "cls": tuple(filter_col) if filter_col else ('',)}).fetchall()
                df_final = pd.DataFrame(rows, columns=["ID", "Name", "College", "Email", "Invoices", "Scholarships", "Payments", "Balance"])
            else:
                sql = text("""
                    SELECT t.student_id, s.name, s.college, t.reference_no, t.entry_date, t.description, t.debit, t.credit
                    FROM transactions t JOIN students s ON t.student_id = s.id
                    WHERE (:c_cnt = 0 OR s.college IN :cls) ORDER BY t.student_id, t.entry_date DESC
                """)
                rows = session.execute(sql, {"c_cnt": len(filter_col), "cls": tuple(filter_col) if filter_col else ('',)}).fetchall()
                df_final = pd.DataFrame(rows, columns=["ID", "Name", "College", "Ref No", "Date", "Description", "Debit", "Credit"])
            
            st.dataframe(df_final.style.format({col: "{:,.2f}" for col in df_final.columns if any(x in col for x in ["Invoices", "Scholarships", "Payments", "Balance", "Debit", "Credit"])}), use_container_width=True)
            buf_rep = io.BytesIO(); df_final.to_excel(buf_rep, index=False)
            st.download_button("📗 Download Management Report", buf_rep.getvalue(), "NU_Finance_Management_Report.xlsx", use_container_width=True)
