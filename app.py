import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Date
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func, text
from datetime import datetime
from fpdf import FPDF
import io

# --- Authentication Logic ---
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
# 1. Database Connection & Models
# =======================================================
DB_URL = "postgresql://postgres.njqjgvfvxtdxrabidkje:Finance01017043056@aws-0-eu-west-1.pooler.supabase.com:6543/postgres"
engine = create_engine(DB_URL)
Base = declarative_base()

class Student(Base):
    __tablename__ = 'students'
    id = Column(Integer, primary_key=True)
    college = Column(String)
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

# جلب البيانات المساعدة (تأكد من وجود بيانات في قاعدة البيانات أولاً)
try:
    sch_map = {sch.name: sch.id for sch in session.query(ScholarshipType).all()}
    all_colleges = [c[0] for c in session.query(Student.college).distinct().all() if c[0]]
    available_years = [y[0] for y in session.query(Transaction.academic_year).distinct().all() if y[0]] or [2026]
except:
    sch_map = {}
    all_colleges = []
    available_years = [2026]

# =======================================================
# 2. PDF Generator (Landscape)
# =======================================================
def create_pdf(sid, df, net_balance):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("helvetica", 'B', 16)
    pdf.cell(0, 15, "Nile University - Official Statement of Account", ln=True, align='C')
    pdf.set_font("helvetica", '', 11)
    pdf.cell(0, 7, f"Student ID: {sid}", ln=True, align='L')
    pdf.cell(0, 7, f"Report Date: {datetime.now().strftime('%d-%b-%Y')}", ln=True, align='L')
    pdf.ln(5)
    pdf.set_fill_color(52, 73, 94); pdf.set_text_color(255, 255, 255); pdf.set_font("helvetica", 'B', 10)
    h = ["Ref No", "Date", "Term", "Year", "Type", "Description", "Debit", "Credit"]
    w = [30, 25, 20, 15, 35, 90, 30, 30]
    for head, width in zip(h, w): pdf.cell(width, 10, head, 1, 0, 'C', True)
    pdf.ln(); pdf.set_text_color(0, 0, 0); pdf.set_font("helvetica", '', 9)
    for _, r in df.iterrows():
        pdf.cell(30, 8, str(r['Ref No']), 1); pdf.cell(25, 8, str(r['Date']), 1); pdf.cell(20, 8, str(r['Term']), 1)
        pdf.cell(15, 8, str(r['Year']), 1); pdf.cell(35, 8, str(r['Type'])[:18], 1); pdf.cell(90, 8, str(r['Description'])[:55], 1)
        pdf.cell(30, 8, str(r['Debit']), 1, 0, 'R'); pdf.cell(30, 8, str(r['Credit']), 1, 1, 'R')
    pdf.ln(8); pdf.set_font("helvetica", 'B', 14); pdf.cell(0, 10, f"NET BALANCE: {net_balance:,.2f} EGP", ln=True, align='R')
    return bytes(pdf.output())

# =======================================================
# 3. UI Layout
# =======================================================
st.set_page_config(page_title="Finance A/R System", layout="wide", page_icon="🏦")

# --- Authentication Check ---
if not st.session_state['authenticated']:
    login_form()
    st.stop()

# --- NEW HEADER: Title & Logout in ONE Row ---
col_title, col_logout = st.columns([0.8, 0.2], vertical_alignment="center")

with col_title:
    st.title("🏦 Nile University - Finance A/R System")

with col_logout:
    if st.button("🚪 Log out", use_container_width=True, key="main_logout"):
        st.session_state['authenticated'] = False
        st.rerun()

st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(["📊 Operations", "📜 Statement", "📤 Bulk", "📈 Management Reports"])

# --- Tab 1: Manual Operations ---
with tab1:
    st.subheader("Post Manual Transaction")
    sid_raw = st.text_input("Student ID", placeholder="Enter ID (e.g., 18100523)...", key="manual_id")
    sid = int(sid_raw) if sid_raw.strip().isdigit() else 0
    a_t = st.selectbox("Action", ["Payment Receipt", "Apply Scholarship", "Credit Hours Adjustment", "Other Fees"], index=1)
    c1, c2, c3 = st.columns(3); ed = c1.date_input("Date"); et = c2.selectbox("Term", ["Fall", "Spring", "Summer"]); ey = c3.number_input("Year", value=ed.year)
    
    dr, cr, dsc, sch_id, pfx = 0.0, 0.0, "", None, "TX"
    if a_t == "Payment Receipt":
        pfx = "PAY"; b_n = st.text_input("Bank Name"); b_r = st.text_input("Ref No"); amt = st.number_input("Amount Paid", min_value=0.0)
        dsc, cr = f"Bank: {b_n} | Ref: {b_r}", amt
    elif a_t == "Apply Scholarship":
        pfx = "SCH"; s_n = st.selectbox("Scholarship Category", list(sch_map.keys())); sch_id = sch_map.get(s_n); pct = st.number_input("Percentage %")
        s_d = session.query(Student).filter_by(id=sid).first(); rate = s_d.price_per_hr if s_d else 0
        cr = (15 * rate * (pct/100)); dsc = f"Scholarship: {s_n} ({pct}%)"
    elif a_t == "Credit Hours Adjustment":
        pfx = "ADJ"; h = st.number_input("Hours Delta (+/-)"); s_d = session.query(Student).filter_by(id=sid).first(); rate = s_d.price_per_hr if s_d else 0
        val = abs(h * rate); dr = val if h > 0 else 0; cr = val if h < 0 else 0; dsc = f"Adj: {h} CH @ {rate:,.2f}"
    elif a_t == "Other Fees":
        pfx = "INV"; amt = st.number_input("Fee Amount"); dsc = st.text_input("Description"); dr = amt

    if st.button("🚀 Process Transaction"):
        if sid == 0: st.error("Please enter a valid Student ID.")
        else:
            s_d = session.query(Student).filter_by(id=sid).first()
            if not s_d: st.error("Student ID not found!"); st.stop()
            m_id = session.query(func.max(Transaction.id)).scalar() or 0
            new_tx = Transaction(reference_no=f"{pfx}-{m_id+1:06d}", student_id=sid, scholarship_type_id=sch_id, transaction_type=a_t, description=dsc, debit=dr, credit=cr, entry_date=ed, term=et, academic_year=ey)
            session.add(new_tx); session.commit(); st.success("Successfully Posted!"); st.rerun()

# --- Tab 2: Individual Statement ---
with tab2:
    st.subheader("Student Statement of Account")
    search_r = st.text_input("Search Student ID", placeholder="Search ID...", key="s_search")
    search_id = int(search_r) if search_r.strip().isdigit() else 0
    f1, f2, f3, f4 = st.columns(4); df_r = f1.date_input("Date Range", []); s_t = f2.multiselect("Terms", ["Fall", "Spring", "Summer"]); s_y = f3.multiselect("Years", available_years); s_ref = f4.text_input("Ref No Filter")
    if search_id > 0:
        q = session.query(Transaction).filter(Transaction.student_id == search_id)
        if len(df_r) == 2: q = q.filter(Transaction.entry_date.between(df_r[0], df_r[1]))
        if s_t: q = q.filter(Transaction.term.in_(s_t))
        if s_y: q = q.filter(Transaction.academic_year.in_(s_y))
        if s_ref: q = q.filter(Transaction.reference_no.ilike(f"%{s_ref}%"))
        res = q.order_by(Transaction.entry_date.desc()).all()
        if res:
            df = pd.DataFrame([{"Ref No": r.reference_no, "Date": r.entry_date, "Term": r.term, "Year": r.academic_year, "Type": r.transaction_type, "Description": r.description, "Debit": f"{r.debit:,.2f}", "Credit": f"{r.credit:,.2f}"} for r in res])
            dupes = df[df.duplicated(subset=['Credit', 'Description'], keep=False) & (df['Credit'] != "0.00")]
            if not dupes.empty: st.warning("⚠️ Duplicate Payment Alert"); st.dataframe(dupes.style.apply(lambda x: ['background-color: #ff4b4b' for i in x], axis=1))
            st.table(df); net = sum(r.debit for r in res) - sum(r.credit for r in res); st.metric("Net Balance Due", f"{net:,.2f} EGP")
            # --- إضافة زرار الإكسيل والـ PDF في سطر واحد ---
            b1, b2 = st.columns(2)
            with b1:
                st.download_button("📄 Download PDF Statement", create_pdf(search_id, df, net), f"SOA_{search_id}.pdf", use_container_width=True)
            with b2:
                excel_buf = io.BytesIO()
                df.to_excel(excel_buf, index=False)
                st.download_button("📗 Download Excel Sheet", excel_buf.getvalue(), f"SOA_{search_id}.xlsx", use_container_width=True)

# --- Tab 3: Bulk Operations ---
with tab3:
    st.subheader("Bulk Operations Management")
    b_t = st.radio("Type:", ["Bulk Payments", "Bulk Scholarships", "Bulk Invoices (Tuition)", "Credit Hours Adjustments", "Update Student Rates", "General Adjustments"], horizontal=True)
    st.warning("⚠️ **IMPORTANT:** DELETE the Example Row (ID: 0) before uploading.")
    if b_t == "Update Student Rates": st.info("ℹ️ Note: Use this for updating the Price/Hour every new academic year only.")
    ex = {
        "Bulk Payments": {"ID": 0, "Bank Name": "Bank", "Bank Ref": "REF123", "Amount": 0.0, "Date": "2026-04-17", "Term": "Spring", "Year": 2026},
        "Bulk Scholarships": {"ID": 0, "Scholarship Name": "Name", "Percentage": 0.0, "Date": "2026-04-17", "Term": "Spring", "Year": 2026},
        "Bulk Invoices (Tuition)": {"ID": 0, "Hours": 15.0, "Date": "2026-04-17", "Term": "Spring", "Year": 2026},
        "Credit Hours Adjustments": {"ID": 0, "Hours_Delta": 3.0, "Date": "2026-04-17", "Term": "Spring", "Year": 2026},
        "Update Student Rates": {"ID": 0, "New_Price_Per_Hr": 5500.0},
        "General Adjustments": {"ID": 0, "Debit": 0.0, "Credit": 0.0, "Date": "2026-04-17", "Term": "Spring", "Year": 2026, "Description": "DELETE"}
    }
    buf_t = io.BytesIO(); pd.DataFrame([ex[b_t]]).to_excel(buf_t, index=False); st.download_button("📥 Download Template", buf_t.getvalue(), f"Tpl_{b_t}.xlsx")
    u_f = st.file_uploader("Upload Excel File", type=['xlsx'])
    if u_f:
        df_b = pd.read_excel(u_f)
        if st.button("🚀 Run Bulk Process"):
            with st.spinner("Processing..."):
                if b_t == "Update Student Rates":
                    for _, r in df_b.iterrows():
                        if int(r['ID']) != 0: session.query(Student).filter(Student.id == int(r['ID'])).update({"price_per_hr": float(r['New_Price_Per_Hr'])})
                    session.commit(); st.success("Student Rates Updated!"); st.rerun()
                else:
                    m_id = session.query(func.max(Transaction.id)).scalar() or 0; rts = {s.id: s.price_per_hr for s in session.query(Student).all()}; bulk_l = []
                    for i, r in df_b.iterrows():
                        sid = int(r['ID']) if pd.notnull(r.get('ID')) else 0
                        if sid == 0 or sid not in rts: continue
                        rt, dr, cr, pfx, s_id = rts[sid], 0.0, 0.0, "TX", None
                        raw = str(r.get('Description', '')).strip(); dsc = b_t if not raw or raw in ['0', '0.0', 'nan'] else raw
                        if b_t == "Bulk Payments":
                            pfx, cr, dsc = "PAY", float(r.get('Amount', 0)), f"Bank: {r.get('Bank Name')} | Ref: {r.get('Bank Ref')}"
                        elif b_t == "Bulk Scholarships":
                            pfx, s_n = "SCH", str(r.get('Scholarship Name', '')); s_id = sch_map.get(s_n); cr = (15 * rt * (float(r.get('Percentage', 0))/100)); dsc = f"Sch: {s_n}"
                        elif b_t == "Bulk Invoices (Tuition)":
                            pfx, dr, dsc = "INV", (float(r.get('Hours', 15)) * rt), f"Tuition Invoice ({r.get('Hours')} CH)"
                        elif b_t == "Credit Hours Adjustments":
                            pfx, h = "ADJ", float(r.get('Hours_Delta', 0)); v = abs(h * rt); dr, cr = (v if h > 0 else 0), (v if h < 0 else 0); dsc = f"Adj {h} CH"
                        elif b_t == "General Adjustments":
                            pfx, dr, cr = "TXN", float(r.get('Debit', 0)), float(r.get('Credit', 0))
                        bulk_l.append(Transaction(reference_no=f"{pfx}-{m_id+i+1:06d}", student_id=sid, scholarship_type_id=s_id, transaction_type=b_t, description=dsc, debit=dr, credit=cr, entry_date=pd.to_datetime(r.get('Date')).date(), term=str(r.get('Term')), academic_year=int(r.get('Year'))))
                    session.bulk_save_objects(bulk_l); session.commit(); st.success("Bulk Success!"); st.rerun()

# --- Tab 4: Management Reports ---
with tab4:
    st.subheader("📈 Financial Management Reports")
    sel_col = st.multiselect("Filter by College", all_colleges)
    rep_v = st.radio("Format:", ["Accounting Summary", "Full Detailed Log"], horizontal=True)
    if st.button("📂 Generate & Download"):
        with st.spinner("Processing SQL..."):
            with st.spinner("Calculating Financial Summary..."):
            if rep_v == "Accounting Summary":
                # SQL Query المحدثة لربط بيانات الطالب بالمعاملات المالية
                sql = text("""
                    SELECT 
                        s.id AS "ID", 
                        s.name AS "Student Name",
                        s.college AS "College",
                        s.email AS "Email",
                        COALESCE(SUM(t.debit), 0) AS "Invoices",
                        COALESCE(SUM(CASE WHEN t.reference_no LIKE 'SCH-%' THEN t.credit ELSE 0 END), 0) AS "Discounts",
                        COALESCE(SUM(CASE WHEN t.reference_no LIKE 'PAY-%' THEN t.credit ELSE 0 END), 0) AS "Payments",
                        COALESCE(SUM(t.debit) - SUM(t.credit), 0) AS "Balance"
                    FROM students s 
                    LEFT JOIN transactions t ON s.id = t.student_id
                    WHERE (:c_cnt = 0 OR s.college IN :cls) 
                    GROUP BY s.id, s.name, s.college, s.email
                    ORDER BY s.id
                """)
                
                res = session.execute(sql, {"c_cnt": len(sel_col), "cls": tuple(sel_col) if sel_col else ('',)}).fetchall()
                
                # تحديث أسماء الأعمدة في الـ DataFrame لتطابق الـ SQL
                df = pd.DataFrame(res, columns=["ID", "Student Name", "College", "Email", "Invoices", "Discounts", "Payments", "Balance"])
            else:
                sql = text("""
                    SELECT t.student_id, s.college, t.reference_no, t.entry_date, t.description, t.debit, t.credit
                    FROM transactions t JOIN students s ON t.student_id = s.id
                    WHERE (:c_cnt = 0 OR s.college IN :cls) ORDER BY t.student_id, t.entry_date DESC
                """)
                res = session.execute(sql, {"c_cnt": len(sel_col), "cls": tuple(sel_col) if sel_col else ('',)}).fetchall()
                df = pd.DataFrame(res, columns=["ID", "College", "Ref", "Date", "Description", "Debit", "Credit"])
            buf = io.BytesIO(); df.to_excel(buf, index=False)
            st.success("Report Ready!"); st.download_button("📗 Download Excel Report", buf.getvalue(), "AR_Management_Report.xlsx")
