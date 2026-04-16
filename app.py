import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Date
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
from datetime import datetime
from fpdf import FPDF
import io

# =======================================================
# 1. Database Connection & Models
# =======================================================
DB_URL = "postgresql://postgres.njqjgvfvxtdxrabidkje:Finance01017043056@aws-0-eu-west-1.pooler.supabase.com:6543/postgres"
engine = create_engine(DB_URL)
Base = declarative_base()

class Student(Base):
    __tablename__ = 'students'
    id = Column(Integer, primary_key=True)
    college = Column(String); price_per_hr = Column(Float)

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
    debit = Column(Float, default=0); credit = Column(Float, default=0)
    entry_date = Column(Date, nullable=False)
    term = Column(String, nullable=False)
    academic_year = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

Session = sessionmaker(bind=engine)
session = Session()

# جلب البيانات المساعدة
sch_map = {sch.name: sch.id for sch in session.query(ScholarshipType).all()}
distinct_years = session.query(Transaction.academic_year).distinct().order_by(Transaction.academic_year.desc()).all()
available_years = [y[0] for y in distinct_years if y[0] is not None] or [datetime.now().year]

# =======================================================
# 2. PDF Generator (Landscape)
# =======================================================
def create_pdf(sid, df, net_balance):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("helvetica", 'B', 16)
    pdf.cell(0, 15, "Finance A/R Team Project - Official Statement of Account", ln=True, align='C')
    pdf.set_font("helvetica", '', 11)
    pdf.cell(0, 7, f"Student ID: {sid}", ln=True, align='L')
    pdf.cell(0, 7, f"Report Date: {datetime.now().strftime('%d-%b-%Y')}", ln=True, align='L')
    pdf.ln(5)

    pdf.set_fill_color(52, 73, 94); pdf.set_text_color(255, 255, 255); pdf.set_font("helvetica", 'B', 10)
    w = {'Ref': 30, 'Date': 25, 'Term': 20, 'Year': 15, 'Type': 35, 'Desc': 90, 'Debit': 30, 'Credit': 30}
    for label, width in w.items(): pdf.cell(width, 10, label, 1, 0, 'C', True)
    pdf.ln()

    pdf.set_text_color(0, 0, 0); pdf.set_font("helvetica", '', 9)
    for _, row in df.iterrows():
        pdf.cell(w['Ref'], 8, str(row['Ref No']), 1)
        pdf.cell(w['Date'], 8, str(row['Date']), 1)
        pdf.cell(w['Term'], 8, str(row['Term']), 1)
        pdf.cell(w['Year'], 8, str(row['Year']), 1)
        pdf.cell(w['Type'], 8, str(row['Type'])[:18], 1)
        pdf.cell(w['Desc'], 8, str(row['Description'])[:50], 1)
        pdf.cell(w['Debit'], 8, str(row['Debit']), 1, 0, 'R')
        pdf.cell(w['Credit'], 8, str(row['Credit']), 1, 1, 'R')

    pdf.ln(8); pdf.set_font("helvetica", 'B', 14)
    pdf.cell(0, 10, f"NET BALANCE DUE: {net_balance:,.2f} EGP", ln=True, align='R')
    return bytes(pdf.output())

# =======================================================
# 3. UI Layout
# =======================================================
st.set_page_config(page_title="Finance A/R Team Project", layout="wide", page_icon="🏦")
st.title("🏦 Finance A/R Team Project")
st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📊 Financial Operations", "📜 Statement & Audit", "📤 Bulk Operations"])

# --- Tab 1: Manual Entry ---
with tab1:
    col_in, col_pre = st.columns([1, 1])
    with col_in:
        st.subheader("Post Transaction")
        stu_id_raw = st.text_input("Student ID", placeholder="Enter ID (e.g., 18100523)...", key="manual_id")
        stu_id = int(stu_id_raw) if stu_id_raw.strip().isdigit() else 0
        
        # Default: Apply Scholarship (Index 1)
        a_type = st.selectbox("Action", ["Payment Receipt", "Apply Scholarship", "Credit Hours Adjustment", "Other Fees"], index=1)
        
        c1, c2, c3 = st.columns(3)
        with c1: ed = st.date_input("Entry Date", value=datetime.now().date())
        with c2: et = st.selectbox("Term", ["Fall", "Spring", "Summer"])
        with c3: ey = st.number_input("Academic Year", value=ed.year)
        
        f_dr, f_cr, f_dsc, f_sch_id, pfx = 0.0, 0.0, "", None, "TX"
        
        if a_type == "Payment Receipt":
            pfx = "PAY"; b_name = st.text_input("Bank Name (Mandatory)")
            b_ref = st.text_input("Transaction Reference (Mandatory)")
            amt = st.number_input("Amount Paid", min_value=0.0)
            f_dsc = f"Bank: {b_name} | Ref: {b_ref}"; f_cr = amt
        elif a_type == "Apply Scholarship":
            pfx = "SCH"; s_name = st.selectbox("Scholarship Category", options=list(sch_map.keys()))
            f_sch_id = sch_map[s_name]; pct = st.number_input("Percentage %", min_value=0.0)
            s_data = session.query(Student).filter_by(id=stu_id).first()
            f_cr = (15 * s_data.price_per_hr * (pct/100)) if s_data else 0
            f_dsc = f"Scholarship: {s_name} ({pct}%)"
        elif a_type == "Credit Hours Adjustment":
            pfx = "ADJ"; hrs = st.number_input("Hours Delta (+/-)", value=0)
            s_data = session.query(Student).filter_by(id=stu_id).first()
            rate = s_data.price_per_hr if s_data else 0
            val = abs(hrs * rate); f_dsc = f"Credit Hours Adj: {hrs} CH @ {rate:,.2f}"
            f_dr = val if hrs > 0 else 0; f_cr = val if hrs < 0 else 0
        elif a_type == "Other Fees":
            pfx = "INV"; amt = st.number_input("Fee Amount", min_value=0.0); f_dsc = st.text_input("Description"); f_dr = amt

        if st.button("🚀 Process Transaction"):
            if stu_id == 0: st.error("Please enter a valid Student ID.")
            elif a_type == "Payment Receipt" and (not b_name or not b_ref): st.error("Bank details are mandatory!")
            else:
                max_id = session.query(func.max(Transaction.id)).scalar() or 0
                new_tx = Transaction(reference_no=f"{pfx}-{max_id+1:06d}", student_id=stu_id, scholarship_type_id=f_sch_id, transaction_type=a_type, description=f_dsc, debit=f_dr, credit=f_cr, entry_date=ed, term=et, academic_year=ey)
                session.add(new_tx); session.commit(); st.success("Posted!"); st.rerun()

# --- Tab 2: Statement & Full Filters ---
with tab2:
    st.subheader("Statement of Account Search")
    search_sid_raw = st.text_input("Search Student ID", placeholder="Search by Student ID...", key="s_search")
    search_sid = int(search_sid_raw) if search_sid_raw.strip().isdigit() else 0
    
    st.markdown("#### 🔍 Advanced Filters")
    f1, f2, f3, f4 = st.columns(4)
    with f1: dr = st.date_input("Date Range", [])
    with f2: ft = st.multiselect("Terms", ["Fall", "Spring", "Summer"])
    with f3: fy = st.multiselect("Years", options=available_years)
    with f4: fr = st.text_input("Ref No Filter")

    if search_sid > 0:
        q = session.query(Transaction).filter(Transaction.student_id == search_sid)
        if len(dr) == 2: q = q.filter(Transaction.entry_date.between(dr[0], dr[1]))
        if ft: q = q.filter(Transaction.term.in_(ft))
        if fy: q = q.filter(Transaction.academic_year.in_(fy))
        if fr: q = q.filter(Transaction.reference_no.ilike(f"%{fr}%"))
        
        res = q.order_by(Transaction.entry_date.desc()).all()
        if res:
            df = pd.DataFrame([{
                "Ref No": r.reference_no, "Date": r.entry_date, "Term": r.term, "Year": r.academic_year, 
                "Type": r.transaction_type, "Description": r.description, 
                "Debit": f"{float(r.debit):,.2f}", "Credit": f"{float(r.credit):,.2f}"
            } for r in res])
            
            duplicates = df[df.duplicated(subset=['Credit', 'Description'], keep=False) & (df['Credit'] != "0.00")]
            if not duplicates.empty:
                st.warning("⚠️ **Duplicate Payment Alert:** Potential duplicate entries found.")
                st.dataframe(duplicates.style.apply(lambda x: ['background-color: #ff4b4b' for i in x], axis=1))

            st.table(df)
            net = sum(r.debit for r in res) - sum(r.credit for r in res)
            st.metric("Net Balance Due", f"{net:,.2f} EGP")
            
            st.markdown("---")
            b1, b2 = st.columns(2)
            with b1:
                pdf_b = create_pdf(search_sid, df, net)
                st.download_button("📄 Download PDF Statement", pdf_b, f"Statement_{search_sid}.pdf", "application/pdf", use_container_width=True)
            with b2:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='openpyxl') as wr: df.to_excel(wr, index=False)
                st.download_button("📗 Download Excel Sheet", buf.getvalue(), f"Statement_{search_sid}.xlsx", use_container_width=True)

# --- Tab 3: Bulk Operations (No nan, No double-entry) ---
with tab3:
    st.subheader("Bulk Operations Management")
    with st.expander("📖 Scholarship Names Reference"):
        for name in sch_map.keys(): st.code(name)

    b_type = st.radio("Bulk Type:", ["Bulk Payments", "Bulk Scholarships", "Credit Hours Adjustments", "General Adjustments"], horizontal=True)
    
    tmpls = {
        "Bulk Payments": ["ID", "Bank Name", "Bank Ref", "Amount", "Date", "Term", "Year"],
        "Bulk Scholarships": ["ID", "Scholarship Name", "Percentage", "Date", "Term", "Year"],
        "Credit Hours Adjustments": ["ID", "Hours_Delta", "Date", "Term", "Year"],
        "General Adjustments": ["ID", "Debit", "Credit", "Date", "Term", "Year", "Description"]
    }
    
    buf_t = io.BytesIO()
    pd.DataFrame(columns=tmpls[b_type]).to_excel(buf_t, index=False)
    st.download_button(f"📥 Download Template", buf_t.getvalue(), f"Template_{b_type.replace(' ','_')}.xlsx")
    
    u_file = st.file_uploader("Upload Sheet", type=['xlsx'])
    if u_file:
        df_b = pd.read_excel(u_file)
        st.dataframe(df_b.head())
        
        if st.button("🚀 Execute Bulk Post"):
            with st.spinner("Processing..."):
                m_id = session.query(func.max(Transaction.id)).scalar() or 0
                rates = {s.id: s.price_per_hr for s in session.query(Student).all()}
                bulk_tx = []; errors = []
                
                for i, row in df_b.iterrows():
                    sid = int(row['ID']) if pd.notnull(row.get('ID')) else 0
                    if sid not in rates:
                        errors.append(f"Row {i+2}: ID {sid} not found."); continue
                    
                    rate, dr, cr, s_id, pfx = rates[sid], 0.0, 0.0, None, "TX"
                    raw_dsc = str(row.get('Description', '')).strip()
                    # Smart Description: Fallback to Op Type if empty
                    if not raw_dsc or raw_dsc in ['0', '0.0', 'nan', 'NaN']:
                        final_dsc = b_type
                    else:
                        final_dsc = raw_dsc

                    if b_type == "Bulk Payments":
                        pfx = "PAY"; cr = float(row.get('Amount', 0))
                        final_dsc = f"Bank: {row.get('Bank Name', 'N/A')} | Ref: {row.get('Bank Ref', 'N/A')}"
                    elif b_type == "Bulk Scholarships":
                        pfx = "SCH"; s_n = str(row.get('Scholarship Name', '')); s_id = sch_map.get(s_n)
                        pct = float(row.get('Percentage', 0)); cr = (15 * rate) * (pct/100)
                        final_dsc = f"Scholarship: {s_n} ({pct}%)"
                    elif b_type == "Credit Hours Adjustments":
                        pfx = "ADJ"; h = float(row.get('Hours_Delta', 0)); v = abs(h * rate)
                        dr = v if h > 0 else 0; cr = v if h < 0 else 0
                        final_dsc = f"Credit Hours Adj: {h} CH @ {rate:,.2f}"
                    elif b_type == "General Adjustments":
                        pfx = "TXN"
                        dr = float(row.get('Debit', 0)) if pd.notnull(row.get('Debit')) else 0.0
                        cr = float(row.get('Credit', 0)) if pd.notnull(row.get('Credit')) else 0.0
                        # Prevent double-entry in one row
                        if dr > 0 and cr > 0:
                            errors.append(f"Row {i+2}: Debit and Credit in one row skipped."); continue

                    bulk_tx.append(Transaction(reference_no=f"{pfx}-{m_id+i+1:06d}", student_id=sid, scholarship_type_id=s_id, transaction_type=b_type, description=final_dsc, debit=dr, credit=cr, entry_date=pd.to_datetime(row.get('Date', datetime.now())).date(), term=str(row.get('Term', 'Spring')), academic_year=int(row.get('Year', 2026))))
                
                if bulk_tx:
                    session.bulk_save_objects(bulk_tx); session.commit()
                    st.success(f"✅ Posted {len(bulk_tx)} entries."); st.rerun()
                if errors:
                    for e in errors: st.error(e)