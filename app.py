import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Date
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func, text
from datetime import datetime
from fpdf import FPDF
import io

# =======================================================
# الإعدادات — مأخوذة من ملف .env
# =======================================================
load_dotenv()

DB_URL = "postgresql://postgres.njqjgvfvxtdxrabidkje:Finance01017043056@aws-0-eu-west-1.pooler.supabase.com:6543/postgres"
DEFAULT_YEAR = 2026

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
    hours_change = Column(Float, default=0.0) 
    debit = Column(Float, default=0)
    credit = Column(Float, default=0)
    entry_date = Column(Date, nullable=False)
    term = Column(String, nullable=False)
    academic_year = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

Session = sessionmaker(bind=engine)
session = Session()

# جلب البيانات المساعدة 
try:
    sch_map = {sch.name: sch.id for sch in session.query(ScholarshipType).all()}
    all_colleges = [c[0] for c in session.query(Student.college).distinct().all() if c[0]]
    available_years = [y[0] for y in session.query(Transaction.academic_year).distinct().all() if y[0]] or [DEFAULT_YEAR]
except:
    sch_map = {}
    all_colleges = []
    available_years = [DEFAULT_YEAR]

# =======================================================
# 2. PDF Generator (Landscape)
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
        pdf.cell(30, 8, str(r['Ref No']), 1); pdf.cell(25, 8, str(r['Date']), 1); pdf.cell(20, 8, str(r['Term']), 1)
        pdf.cell(15, 8, str(r['Year']), 1); pdf.cell(35, 8, str(r['Type'])[:18], 1); pdf.cell(90, 8, str(r['Description'])[:55], 1)
        pdf.cell(30, 8, str(r['Debit']), 1, 0, 'R'); pdf.cell(30, 8, str(r['Credit']), 1, 1, 'R')
    pdf.ln(8); pdf.set_font("helvetica", 'B', 14); pdf.cell(0, 10, f"NET BALANCE: {net_balance:,.2f} EGP", ln=True, align='R')
    return bytes(pdf.output())

# =======================================================
# 3. UI Layout
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
        st.rerun()

st.markdown("---")

tab_std, tab1, tab2, tab3, tab4 = st.tabs(["👤 Students", "📊 Operations", "📜 Statement", "📤 Bulk Financials", "📈 Management Reports"])

# --- Tab 0: Student Management ---
with tab_std:
    st.subheader("🎓 Student Management")
    std_mode = st.radio("Select Registration Mode:", ["Single Student Entry", "Bulk Upload Students"], horizontal=True)
    
    if std_mode == "Single Student Entry":
        st.info("Use this form to manually add a single new student. (Note: The #Price/Hr is needed here and can be changed later every Academic Year).")
        with st.form("new_student_form", clear_on_submit=True):
            col_s1, col_s2, col_s3 = st.columns(3)
            n_id = col_s1.number_input("Student ID", value=None, placeholder="(e.g., 26100123)", step=1, format="%d")
            n_name = col_s2.text_input("Full Name *")
            n_email = col_s3.text_input("University Email")

            # رسالة واضحة بأسماء الكليات
            st.markdown("💡 **Valid College Codes:** `ENG` (Engineering), `BBA` (Business), `IT_CS` (Computer Science), `Bio_Tech` (Biotechnology)")
            col_s4, col_s5, col_s6 = st.columns(3)
            n_college = col_s4.text_input("College Code *")
            n_program = col_s5.text_input("Program")
            n_price = col_s6.number_input("Fixed Price Per Credit Hour (EGP) *", min_value=0.0, step=100.0, format="%.2f")

            col_s7, col_s8, col_s9 = st.columns(3)
            n_mobile = col_s7.text_input("Mobile Number")
            n_nat_id = col_s8.text_input("National ID")
            n_nationality = col_s9.text_input("Nationality", value="Egyptian")

            col_s10, col_s11 = st.columns(2)
            n_dob = col_s10.date_input("Birth Date", min_value=datetime(1990, 1, 1), value=datetime(2005, 1, 1))
            n_admit = col_s11.number_input("Admit Year", value=DEFAULT_YEAR, step=1)

            submitted = st.form_submit_button("💾 Save Student Record")
            if submitted:
                if n_id is None or not n_name or not n_college:
                    st.error("⚠️ Student ID, Name, and College are required fields!")
                else:
                    exists = session.query(Student).filter_by(id=n_id).first()
                    if exists:
                        st.error(f"⚠️ Student ID {n_id} already exists ({exists.name})!")
                    else:
                        try:
                            # تمت إزالة college_short تماماً من قاعدة البيانات
                            new_student = Student(id=n_id, name=n_name, college=n_college.upper(), program=n_program, birth_date=n_dob, email=n_email, mobile=n_mobile, national_id=n_nat_id, nationality=n_nationality, admit_year=n_admit, price_per_hr=n_price)
                            session.add(new_student); session.commit()
                            st.success(f"✅ Student '{n_name}' has been registered!")
                        except Exception as e:
                            session.rollback(); st.error(f"❌ Error: {e}")

    else:
        st.info("Upload an Excel file to register multiple students at once. Existing IDs will be ignored.")
        std_ex = {
            "ID": 26100123, "Name": "Ahmed Ali", "College": "ENG", "Program": "Computer Eng", 
            "Price Per Hr": 4600.0, "Email": "ahmed@nu.edu.eg", "Mobile": "01000000000", 
            "National ID": "29901010000000", "Nationality": "Egyptian", 
            "Admit Year": DEFAULT_YEAR, "Birth Date": "2005-01-01"
        }
        buf_std = io.BytesIO(); pd.DataFrame([std_ex]).to_excel(buf_std, index=False)
        st.download_button("📥 Download Students Template", buf_std.getvalue(), "Template_Bulk_Students.xlsx")
        
        u_std = st.file_uploader("Upload Students Excel", type=['xlsx'])
        if u_std:
            df_std = pd.read_excel(u_std)
            if st.button("🚀 Process Bulk Registration"):
                with st.spinner("Registering students..."):
                    existing_ids = {s[0] for s in session.query(Student.id).all()}
                    new_students = []
                    for _, r in df_std.iterrows():
                        sid = int(r.get('ID', 0)) if pd.notnull(r.get('ID')) else 0
                        if sid > 0 and sid not in existing_ids:
                            bd_raw = r.get('Birth Date')
                            bd_clean = pd.to_datetime(bd_raw, errors='coerce').date() if pd.notnull(bd_raw) else None
                            new_students.append(Student(
                                id=sid, name=str(r.get('Name', 'Unknown')), college=str(r.get('College', 'N/A')).upper(), 
                                program=str(r.get('Program', '')), price_per_hr=float(r.get('Price Per Hr', 0.0)), 
                                email=str(r.get('Email', '')), mobile=str(r.get('Mobile', '')), 
                                national_id=str(r.get('National ID', '')), nationality=str(r.get('Nationality', 'Egyptian')), 
                                admit_year=int(r.get('Admit Year', DEFAULT_YEAR)), 
                                birth_date=bd_clean
                            ))
                    if new_students:
                        try:
                            session.add_all(new_students)
                            session.commit()
                            st.success(f"✅ Successfully registered {len(new_students)} new students!")
                            st.rerun()
                        except Exception as e:
                            session.rollback(); st.error(f"❌ Upload failed: {e}")
                    else:
                        st.warning("⚠️ No new students added. Ensure the IDs are correct and not already registered.")

# --- Tab 1: Manual Operations ---
with tab1:
    st.subheader("Post Manual Transaction")
    sid_raw = st.text_input("Student ID", placeholder="Enter ID (e.g., 18100523)...", key="manual_id")
    sid = int(sid_raw) if sid_raw.strip().isdigit() else 0
    a_t = st.selectbox("Action", ["Payment Receipt", "Apply Scholarship", "Credit Hours Adjustment", "Other Fees"], index=1)
    c1, c2, c3 = st.columns(3); ed = c1.date_input("Date"); et = c2.selectbox("Term", ["Fall", "Spring", "Summer"]); ey = c3.number_input("Year", value=DEFAULT_YEAR)
    
    dr, cr, dsc, sch_id, pfx, h_change = 0.0, 0.0, "", None, "TX", 0.0 
    
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
        h_change = h 
    elif a_t == "Other Fees":
        pfx = "INV"; amt = st.number_input("Fee Amount"); dsc = st.text_input("Description"); dr = amt

    if st.button("🚀 Process Transaction"):
        if sid == 0: st.error("Please enter a valid Student ID.")
        else:
            s_d = session.query(Student).filter_by(id=sid).first()
            if not s_d: st.error("Student ID not found! Please register the student first in the 'Students' tab."); st.stop()
            m_id = session.query(func.max(Transaction.id)).scalar() or 0
            new_tx = Transaction(reference_no=f"{pfx}-{m_id+1:06d}", student_id=sid, scholarship_type_id=sch_id, transaction_type=a_t, description=dsc, debit=dr, credit=cr, hours_change=h_change, entry_date=ed, term=et, academic_year=ey)
            session.add(new_tx); session.commit(); st.success("Successfully Posted!"); st.rerun()

# --- Tab 2: Individual Statement ---
with tab2:
    st.subheader("Student Statement of Account")
    search_r = st.text_input("Search Student ID", placeholder="Search ID...", key="s_search")
    search_id = int(search_r) if search_r.strip().isdigit() else 0
    
    f1, f2, f3, f4 = st.columns(4); df_r = f1.date_input("Date Range", []); s_t = f2.multiselect("Terms", ["Fall", "Spring", "Summer"]); s_y = f3.multiselect("Years", available_years); s_ref = f4.text_input("Ref No Filter")
    
    if search_id > 0:
        s_obj = session.query(Student).filter_by(id=search_id).first()
        student_name = s_obj.name if s_obj else "Unknown"
        
        q = session.query(Transaction).filter(Transaction.student_id == search_id)
        if len(df_r) == 2: q = q.filter(Transaction.entry_date.between(df_r[0], df_r[1]))
        if s_t: q = q.filter(Transaction.term.in_(s_t))
        if s_y: q = q.filter(Transaction.academic_year.in_(s_y))
        if s_ref: q = q.filter(Transaction.reference_no.ilike(f"%{s_ref}%"))
        res = q.order_by(Transaction.entry_date.desc()).all()
        
        if res:
            df = pd.DataFrame([{"Ref No": r.reference_no, "Date": r.entry_date, "Term": r.term, "Year": r.academic_year, "Type": r.transaction_type, "Description": r.description, "Hours": r.hours_change, "Debit": f"{r.debit:,.2f}", "Credit": f"{r.credit:,.2f}"} for r in res])
            
            dupes = df[df.duplicated(subset=['Credit', 'Description'], keep=False) & (df['Credit'] != "0.00")]
            if not dupes.empty: st.warning("⚠️ Duplicate Payment Alert"); st.dataframe(dupes.style.apply(lambda x: ['background-color: #ff4b4b' for i in x], axis=1))
            
            st.table(df); net = sum(r.debit for r in res) - sum(r.credit for r in res); st.metric("Net Balance Due", f"{net:,.2f} EGP")
            
            b1, b2 = st.columns(2)
            with b1:
                st.download_button("📄 Download PDF Statement", create_pdf(search_id, student_name, df, net), f"SOA_{search_id}.pdf", use_container_width=True)
            with b2:
                excel_buf = io.BytesIO()
                df.to_excel(excel_buf, index=False)
                st.download_button("📗 Download Excel Sheet", excel_buf.getvalue(), f"SOA_{search_id}.xlsx", use_container_width=True)

# --- Tab 3: Bulk Operations ---
with tab3:
    st.subheader("Bulk Financial Operations")
    b_t = st.radio("Type:", ["Bulk Payments", "Bulk Scholarships", "Bulk Invoices (Tuition)", "Credit Hours Adjustments", "Update Student Rates", "General Adjustments"], horizontal=True)
    st.warning("⚠️ **IMPORTANT:** DELETE the Example Row (ID: 0) before uploading.")
    
    ex = {
        "Bulk Payments": {"ID": 0, "Bank Name": "Bank", "Bank Ref": "REF123", "Amount": 0.0, "Date": "2026-04-17", "Term": "Spring", "Year": DEFAULT_YEAR},
        "Bulk Scholarships": {"ID": 0, "Scholarship Name": "Name", "Percentage": 0.0, "Date": "2026-04-17", "Term": "Spring", "Year": DEFAULT_YEAR},
        "Bulk Invoices (Tuition)": {"ID": 0, "Hours": 15.0, "Date": "2026-04-17", "Term": "Spring", "Year": DEFAULT_YEAR},
        "Credit Hours Adjustments": {"ID": 0, "Hours_Delta": 3.0, "Date": "2026-04-17", "Term": "Spring", "Year": DEFAULT_YEAR},
        "Update Student Rates": {"ID": 0, "New_Price_Per_Hr": 5500.0},
        "General Adjustments": {"ID": 0, "Debit": 0.0, "Credit": 0.0, "Date": "2026-04-17", "Term": "Spring", "Year": DEFAULT_YEAR, "Description": "DELETE"}
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
                        rt, dr, cr, pfx, s_id, h_change = rts[sid], 0.0, 0.0, "TX", None, 0.0 
                        raw = str(r.get('Description', '')).strip(); dsc = b_t if not raw or raw in ['0', '0.0', 'nan'] else raw
                        
                        if b_t == "Bulk Payments":
                            pfx, cr, dsc = "PAY", float(r.get('Amount', 0)), f"Bank: {r.get('Bank Name')} | Ref: {r.get('Bank Ref')}"
                        elif b_t == "Bulk Scholarships":
                            pfx, s_n = "SCH", str(r.get('Scholarship Name', '')); s_id = sch_map.get(s_n); cr = (15 * rt * (float(r.get('Percentage', 0))/100)); dsc = f"Sch: {s_n}"
                        elif b_t == "Bulk Invoices (Tuition)":
                            h = float(r.get('Hours', 15))
                            pfx, dr, dsc, h_change = "INV", (h * rt), f"Tuition Invoice ({h} CH)", h 
                        elif b_t == "Credit Hours Adjustments":
                            h = float(r.get('Hours_Delta', 0)); v = abs(h * rt); dr, cr = (v if h > 0 else 0), (v if h < 0 else 0); dsc = f"Adj {h} CH"
                            h_change = h 
                        elif b_t == "General Adjustments":
                            pfx, dr, cr = "TXN", float(r.get('Debit', 0)), float(r.get('Credit', 0))
                        
                        bulk_l.append(Transaction(reference_no=f"{pfx}-{m_id+i+1:06d}", student_id=sid, scholarship_type_id=s_id, transaction_type=b_t, description=dsc, debit=dr, credit=cr, hours_change=h_change, entry_date=pd.to_datetime(r.get('Date')).date(), term=str(r.get('Term')), academic_year=int(r.get('Year'))))
                    session.bulk_save_objects(bulk_l); session.commit(); st.success("Bulk Success!"); st.rerun()

# --- Tab 4: Management Reports ---
with tab4:
    st.subheader("📈 Financial Management Reports")
    
    col_f1, col_f2, col_f3 = st.columns(3)
    sel_col = col_f1.multiselect("Filter by College", all_colleges)
    sel_term = col_f2.multiselect("Filter by Term", ["Fall", "Spring", "Summer"])
    sel_year = col_f3.multiselect("Filter by Year", available_years)

    rep_v = st.radio("Format:", ["Accounting Summary", "Full Detailed Log"], horizontal=True)
    
    if st.button("📂 Generate & Download"):
        with st.spinner("Processing Data..."):
            if rep_v == "Accounting Summary":
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
                    "c_cnt": len(sel_col), "cls": tuple(sel_col) if sel_col else ('',),
                    "t_cnt": len(sel_term), "trms": tuple(sel_term) if sel_term else ('',),
                    "y_cnt": len(sel_year), "yrs": tuple(sel_year) if sel_year else (-1,)
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
                    SELECT t.student_id, s.name, s.college, t.reference_no, t.entry_date, t.term, t.academic_year, t.description, t.hours_change AS "Hours", t.debit, t.credit
                    FROM transactions t JOIN students s ON t.student_id = s.id
                    WHERE (:c_cnt = 0 OR s.college IN :cls) 
                      AND (:t_cnt = 0 OR t.term IN :trms)
                      AND (:y_cnt = 0 OR t.academic_year IN :yrs)
                    ORDER BY t.student_id, t.entry_date DESC
                """)
                params = {
                    "c_cnt": len(sel_col), "cls": tuple(sel_col) if sel_col else ('',),
                    "t_cnt": len(sel_term), "trms": tuple(sel_term) if sel_term else ('',),
                    "y_cnt": len(sel_year), "yrs": tuple(sel_year) if sel_year else (-1,)
                }
                res = session.execute(sql, params).fetchall()
                df = pd.DataFrame(res, columns=["ID", "Student Name", "College", "Ref No", "Date", "Term", "Year", "Description", "Hours", "Debit", "Credit"])
                st.dataframe(df.style.format({"Hours": "{:,.1f}", "Debit": "{:,.2f}", "Credit": "{:,.2f}"}), use_container_width=True)
            
            buf = io.BytesIO(); df.to_excel(buf, index=False)
            st.success("Report Ready!")
            st.download_button("📗 Download Excel Report", buf.getvalue(), "AR_Management_Report.xlsx", use_container_width=True)
