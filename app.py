import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Date
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func, text
from datetime import datetime
from fpdf import FPDF
import io

# =======================================================
# 1. Authentication Logic
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
# 2. Database Models (Complete 11 Columns)
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

# Helpers
try:
    sch_map = {sch.name: sch.id for sch in session.query(ScholarshipType).all()}
    all_colleges = [c[0] for c in session.query(Student.college).distinct().all() if c[0]]
    available_years = [y[0] for y in session.query(Transaction.academic_year).distinct().all()] or [2026]
except:
    sch_map, all_colleges, available_years = {}, [], [2026]

# =======================================================
# 3. PDF Generator (Landscape)
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
        pdf.cell(30, 8, f"{float(r['Debit']):,.2f}", 1, 0, 'R')
        pdf.cell(30, 8, f"{float(r['Credit']):,.2f}", 1, 1, 'R')
    pdf.ln(8); pdf.set_font("helvetica", 'B', 14); pdf.cell(0, 10, f"NET BALANCE: {net_balance:,.2f} EGP", ln=True, align='R')
    return bytes(pdf.output())

# =======================================================
# 4. UI Layout
# =======================================================
st.set_page_config(page_title="Finance A/R System", layout="wide", page_icon="🏦")

if not st.session_state['authenticated']:
    login_form(); st.stop()

# Header row
c_title, c_logout = st.columns([0.8, 0.2])
c_title.title("🏦 Nile University - Finance A/R System")
if c_logout.button("🚪 Log out", use_container_width=True):
    st.session_state['authenticated'] = False; st.rerun()

st.markdown("---")
tab1, tab2, tab3, tab4 = st.tabs(["📊 Operations", "📜 Statement", "📤 Bulk Operations", "📈 Reports"])

# --- TAB 1: Manual Operations ---
with tab1:
    st.subheader("Post Manual Transaction")
    sid_raw = st.text_input("Student ID", key="m_sid")
    sid = int(sid_raw) if sid_raw.strip().isdigit() else 0
    a_t = st.selectbox("Action", ["Payment Receipt", "Apply Scholarship", "Credit Hours Adjustment", "Other Fees"], index=0)
    c1, c2, c3 = st.columns(3); ed = c1.date_input("Date"); et = c2.selectbox("Term", ["Fall", "Spring", "Summer"]); ey = c3.number_input("Year", 2026)
    
    dr, cr, dsc, sch_id, pfx = 0.0, 0.0, "", None, "TX"
    s_obj = session.query(Student).filter_by(id=sid).first()
    
    if a_t == "Payment Receipt":
        pfx = "PAY"; b_n = st.text_input("Bank Name"); b_r = st.text_input("Bank Ref No"); amt = st.number_input("Amount", 0.0)
        dsc, cr = f"Bank: {b_n} | Ref: {b_r}", amt
    elif a_t == "Apply Scholarship":
        pfx = "SCH"; s_n = st.selectbox("Scholarship Category", list(sch_map.keys())); sch_id = sch_map.get(s_n); pct = st.number_input("Percentage %")
        rate = s_obj.price_per_hr if s_obj else 0
        cr = (15 * rate * (pct/100)); dsc = f"Scholarship: {s_n} ({pct}%)"
    elif a_t == "Credit Hours Adjustment":
        pfx = "ADJ"; h_delta = st.number_input("Hours Delta (+/-)"); rate = s_obj.price_per_hr if s_obj else 0
        val = abs(h_delta * rate); dr, cr = (val if h_delta > 0 else 0), (val if h_delta < 0 else 0)
        dsc = f"Adj: {h_delta} CH @ {rate:,.2f}"
    elif a_t == "Other Fees":
        pfx = "INV"; amt = st.number_input("Fee Amount"); dsc = st.text_input("Description"); dr = amt

    if st.button("🚀 Process Transaction"):
        if sid > 0 and s_obj:
            m_id = session.query(func.max(Transaction.id)).scalar() or 0
            new_tx = Transaction(reference_no=f"{pfx}-{m_id+1:06d}", student_id=sid, scholarship_type_id=sch_id, transaction_type=a_t, description=dsc, debit=dr, credit=cr, entry_date=ed, term=et, academic_year=ey)
            session.add(new_tx); session.commit(); st.success("Transaction Posted Successfully!"); st.rerun()
        else: st.error("Invalid Student ID")

# --- TAB 2: Individual Statement ---
with tab2:
    st.subheader("Student Statement of Account")
    search_r = st.text_input("Search Student ID", key="s_search")
    search_id = int(search_r) if search_r.strip().isdigit() else 0
    if search_id > 0:
        s_obj = session.query(Student).filter_by(id=search_id).first()
        if s_obj:
            st.info(f"Student: {s_obj.name} | College: {s_obj.college} | Program: {s_obj.program}")
            res = session.query(Transaction).filter(Transaction.student_id == search_id).order_by(Transaction.entry_date.desc()).all()
            if res:
                df = pd.DataFrame([{"Ref No": r.reference_no, "Date": r.entry_date, "Term": r.term, "Year": r.academic_year, "Type": r.transaction_type, "Description": r.description, "Debit": r.debit, "Credit": r.credit} for r in res])
                st.dataframe(df.style.format({"Debit": "{:,.2f}", "Credit": "{:,.2f}"}), use_container_width=True)
                net = sum(r.debit for r in res) - sum(r.credit for r in res)
                st.metric("Net Balance Due", f"{net:,.2f} EGP")
                b1, b2 = st.columns(2)
                with b1: st.download_button("📄 PDF Statement", create_pdf(search_id, s_obj.name, df, net), f"SOA_{search_id}.pdf", use_container_width=True)
                with b2:
                    excel_buf = io.BytesIO(); df.to_excel(excel_buf, index=False)
                    st.download_button("📗 Excel Export", excel_buf.getvalue(), f"SOA_{search_id}.xlsx", use_container_width=True)
        else: st.error("Student not found")

# --- TAB 3: Bulk Operations ---
with tab3:
    st.subheader("Bulk Operations Management")
    b_t = st.radio("Task:", ["Bulk Payments", "Bulk Scholarships", "Bulk Invoices (Tuition)", "Credit Hours Adjustments", "Update Student Rates", "General Adjustments"], horizontal=True)
    
    tmpls = {
        "Bulk Payments": ["ID", "Bank Name", "Bank Ref", "Amount", "Date", "Term", "Year"],
        "Bulk Scholarships": ["ID", "Scholarship Name", "Percentage", "Date", "Term", "Year"],
        "Bulk Invoices (Tuition)": ["ID", "Hours", "Date", "Term", "Year"],
        "Credit Hours Adjustments": ["ID", "Hours_Delta", "Date", "Term", "Year"],
        "Update Student Rates": ["ID", "New_Price_Per_Hr"],
        "General Adjustments": ["ID", "Debit", "Credit", "Date", "Term", "Year", "Description"]
    }
    buf_t = io.BytesIO(); pd.DataFrame(columns=tmpls[b_t]).to_excel(buf_t, index=False)
    st.download_button("📥 Download Template", buf_t.getvalue(), f"Tpl_{b_t}.xlsx")
    
    u_f = st.file_uploader("Upload Data Sheet", type=['xlsx'])
    if u_f:
        df_b = pd.read_excel(u_f)
        if st.button("🚀 Run Bulk Process"):
            with st.spinner("Processing..."):
                if b_t == "Update Student Rates":
                    for _, r in df_b.iterrows():
                        if int(r['ID']) != 0: session.query(Student).filter(Student.id == int(r['ID'])).update({"price_per_hr": float(r['New_Price_Per_Hr'])})
                else:
                    m_id = session.query(func.max(Transaction.id)).scalar() or 0
                    rts = {s.id: s.price_per_hr for s in session.query(Student).all()}
                    bulk_list = []
                    for i, r in df_b.iterrows():
                        sid = int(r['ID'])
                        if sid not in rts or sid == 0: continue
                        rt, dr, cr, pfx, s_id, dsc = rts[sid], 0.0, 0.0, "TX", None, b_t
                        if b_t == "Bulk Payments":
                            pfx, cr, dsc = "PAY", float(r['Amount']), f"Bank: {r['Bank Name']} | Ref: {r['Bank Ref']}"
                        elif b_t == "Bulk Scholarships":
                            pfx, s_id = "SCH", sch_map.get(str(r['Scholarship Name'])); cr = (15 * rt * (float(r['Percentage'])/100)); dsc = f"Sch: {r['Scholarship Name']}"
                        elif b_t == "Bulk Invoices (Tuition)":
                            pfx, dr, dsc = "INV", (float(r['Hours']) * rt), f"Tuition Invoice ({r['Hours']} CH)"
                        elif b_t == "Credit Hours Adjustments":
                            pfx, h = "ADJ", float(r['Hours_Delta']); v = abs(h * rt); dr, cr = (v if h > 0 else 0), (v if h < 0 else 0)
                        elif b_t == "General Adjustments":
                            pfx, dr, cr, dsc = "TXN", float(r['Debit']), float(r['Credit']), str(r['Description'])
                        
                        bulk_list.append(Transaction(reference_no=f"{pfx}-{m_id+i+1:06d}", student_id=sid, scholarship_type_id=s_id, transaction_type=b_t, description=dsc, debit=dr, credit=cr, entry_date=pd.to_datetime(r['Date']).date(), term=str(r['Term']), academic_year=int(r['Year'])))
                    session.bulk_save_objects(bulk_list)
                session.commit(); st.success("Bulk Success!"); st.rerun()

# --- TAB 4: Reports (The Integrated View) ---
with tab4:
    st.subheader("📈 Integrated Management Reports")
    sel_col = st.multiselect("Filter by College", all_colleges)
    r_type = st.radio("Report Type:", ["Accounting Summary", "Full Detailed Log"], horizontal=True)
    
    if st.button("📊 Generate Report"):
        with st.spinner("Calculating..."):
            if r_type == "Accounting Summary":
                sql = text("""
                    SELECT s.id, s.name, s.college, s.email, 
                           COALESCE(SUM(t.debit), 0) as "Invoices",
                           COALESCE(SUM(CASE WHEN t.reference_no LIKE 'SCH-%' THEN t.credit ELSE 0 END), 0) as "Scholarships",
                           COALESCE(SUM(CASE WHEN t.reference_no LIKE 'PAY-%' THEN t.credit ELSE 0 END), 0) as "Payments",
                           COALESCE(SUM(t.debit) - SUM(t.credit), 0) as "Balance"
                    FROM students s LEFT JOIN transactions t ON s.id = t.student_id
                    WHERE (:c_cnt = 0 OR s.college IN :cls)
                    GROUP BY s.id, s.name, s.college, s.email ORDER BY s.id
                """)
                res = session.execute(sql, {"c_cnt": len(sel_col), "cls": tuple(sel_col) if sel_col else ('',)}).fetchall()
                df = pd.DataFrame(res, columns=["ID", "Name", "College", "Email", "Invoices", "Scholarships", "Payments", "Balance"])
            else:
                sql = text("""
                    SELECT t.student_id, s.name, s.college, t.reference_no, t.entry_date, t.description, t.debit, t.credit
                    FROM transactions t JOIN students s ON t.student_id = s.id
                    WHERE (:c_cnt = 0 OR s.college IN :cls) ORDER BY t.entry_date DESC
                """)
                res = session.execute(sql, {"c_cnt": len(sel_col), "cls": tuple(sel_col) if sel_col else ('',)}).fetchall()
                df = pd.DataFrame(res, columns=["ID", "Name", "College", "Ref", "Date", "Description", "Debit", "Credit"])
            
            st.dataframe(df.style.format({"Invoices": "{:,.2f}", "Scholarships": "{:,.2f}", "Payments": "{:,.2f}", "Balance": "{:,.2f}", "Debit": "{:,.2f}", "Credit": "{:,.2f}"}), use_container_width=True)
            buf = io.BytesIO(); df.to_excel(buf, index=False)
            st.download_button("📗 Download Excel Report", buf.getvalue(), "Financial_Report.xlsx", use_container_width=True)
