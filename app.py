import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Date
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func, text
from datetime import datetime
from fpdf import FPDF
import io

# =======================================================
# 1. Database Connection & Models
# =======================================================
# ملاحظة: يفضل استخدام st.secrets["db_url"] عند الرفع على السيرفر
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

# جلب البيانات المساعدة للواجهة
sch_map = {sch.name: sch.id for sch in session.query(ScholarshipType).all()}
distinct_years = session.query(Transaction.academic_year).distinct().order_by(Transaction.academic_year.desc()).all()
available_years = [y[0] for y in distinct_years if y[0] is not None] or [2026]

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
    headers = ["Ref No", "Date", "Term", "Year", "Type", "Description", "Debit", "Credit"]
    widths = [30, 25, 20, 15, 35, 90, 30, 30]
    
    for header, width in zip(headers, widths):
        pdf.cell(width, 10, header, 1, 0, 'C', True)
    pdf.ln()

    pdf.set_text_color(0, 0, 0); pdf.set_font("helvetica", '', 9)
    for _, row in df.iterrows():
        pdf.cell(30, 8, str(row['Ref No']), 1)
        pdf.cell(25, 8, str(row['Date']), 1)
        pdf.cell(20, 8, str(row['Term']), 1)
        pdf.cell(15, 8, str(row['Year']), 1)
        pdf.cell(35, 8, str(row['Type'])[:18], 1)
        pdf.cell(90, 8, str(row['Description'])[:55], 1)
        pdf.cell(30, 8, str(row['Debit']), 1, 0, 'R')
        pdf.cell(30, 8, str(row['Credit']), 1, 1, 'R')

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
                session.add(new_tx); session.commit(); st.success("Posted Successfully!"); st.rerun()

# --- Tab 2: Statement & Audit ---
with tab2:
    st.subheader("Statement of Account Search")
    search_sid_raw = st.text_input("Search Student ID", placeholder="Search by Student ID...", key="s_search")
    search_sid = int(search_sid_raw) if search_sid_raw.strip().isdigit() else 0
    
    st.markdown("#### 🔍 Advanced Filters")
    f1, f2, f3, f4 = st.columns(4)
    with f1: dr_filter = st.date_input("Date Range", [])
    with f2: ft_filter = st.multiselect("Terms", ["Fall", "Spring", "Summer"])
    with f3: fy_filter = st.multiselect("Years", options=available_years)
    with f4: fr_filter = st.text_input("Ref No Filter")

    if search_sid > 0:
        query = session.query(Transaction).filter(Transaction.student_id == search_sid)
        if len(dr_filter) == 2: query = query.filter(Transaction.entry_date.between(dr_filter[0], dr_filter[1]))
        if ft_filter: query = query.filter(Transaction.term.in_(ft_filter))
        if fy_filter: query = query.filter(Transaction.academic_year.in_(fy_filter))
        if fr_filter: query = query.filter(Transaction.reference_no.ilike(f"%{fr_filter}%"))
        
        results = query.order_by(Transaction.entry_date.desc()).all()
        if results:
            data_list = []
            for r in results:
                data_list.append({
                    "Ref No": r.reference_no, "Date": r.entry_date, "Term": r.term, "Year": r.academic_year, 
                    "Type": r.transaction_type, "Description": r.description, 
                    "Debit": f"{float(r.debit):,.2f}", "Credit": f"{float(r.credit):,.2f}"
                })
            df = pd.DataFrame(data_list)
            
            # كشف الحركات المكررة
            duplicates = df[df.duplicated(subset=['Credit', 'Description'], keep=False) & (df['Credit'] != "0.00")]
            if not duplicates.empty:
                st.warning("⚠️ **Duplicate Payment Alert:** Potential duplicate entries found (Same Amount & Reference).")
                st.dataframe(duplicates.style.apply(lambda x: ['background-color: #ff4b4b' for i in x], axis=1))

            st.table(df)
            net_bal = sum(r.debit for r in results) - sum(r.credit for r in results)
            st.metric("Net Balance Due", f"{net_bal:,.2f} EGP")
            
            st.markdown("---")
            b1, b2 = st.columns(2)
            with b1:
                pdf_bytes = create_pdf(search_sid, df, net_bal)
                st.download_button("📄 Download PDF Statement", pdf_bytes, f"SOA_{search_sid}.pdf", "application/pdf", use_container_width=True)
            with b2:
                excel_buf = io.BytesIO()
                df.to_excel(excel_buf, index=False)
                st.download_button("📗 Download Excel Sheet", excel_buf.getvalue(), f"SOA_{search_sid}.xlsx", use_container_width=True)
        else:
            st.info("No records match the selected criteria.")

# --- Tab 3: Bulk Operations ---
with tab3:
    st.subheader("Bulk Operations Management")
    with st.expander("📖 Scholarship Names Reference"):
        for name in sch_map.keys(): st.code(name)

    b_type = st.radio("Bulk Type:", ["Bulk Payments", "Bulk Scholarships", "Bulk Invoices (Tuition)", "Credit Hours Adjustments", "Update Student Rates", "General Adjustments"], horizontal=True)
    
    # ملحوظة واضحة في البرنامج
    st.warning("⚠️ **IMPORTANT:** Please **DELETE** the first row (Example Row) from the template before uploading your final file.")
    if b_type == "Update Student Rates":
        st.info("ℹ️ **Note:** Use this for updating the Price/Hour every new academic year only.")

    # نماذج البيانات (Example Data)
    example_data = {
        "Bulk Payments": {"ID": 00000000, "Bank Name": "Example Bank", "Bank Ref": "EXAMPLE_REF", "Amount": 0.0, "Date": "2026-04-17", "Term": "Spring", "Year": 2026},
        "Bulk Scholarships": {"ID": 00000000, "Scholarship Name": "Choose from list above", "Percentage": 0.0, "Date": "2026-04-17", "Term": "Spring", "Year": 2026},
        "Bulk Invoices (Tuition)": {"ID": 00000000, "Hours": 15.0, "Date": "2026-04-17", "Term": "Spring", "Year": 2026},
        "Credit Hours Adjustments": {"ID": 00000000, "Hours_Delta": 0.0, "Date": "2026-04-17", "Term": "Spring", "Year": 2026},
        "Update Student Rates": {"ID": 00000000, "New_Price_Per_Hr": 5000.0},
        "General Adjustments": {"ID": 00000000, "Debit": 0.0, "Credit": 0.0, "Date": "2026-04-17", "Term": "Spring", "Year": 2026, "Description": "DELETE THIS EXAMPLE ROW"}
    }
    
    template_buf = io.BytesIO()
    pd.DataFrame([example_data[b_type]]).to_excel(template_buf, index=False)
    st.download_button(f"📥 Download Template", template_buf.getvalue(), f"Template_{b_type.replace(' ','_')}.xlsx")
    
    u_file = st.file_uploader("Upload Sheet", type=['xlsx'])
    if u_file:
        df_bulk = pd.read_excel(u_file)
        st.dataframe(df_bulk.head())
        
        if st.button("🚀 Execute Bulk Process"):
            with st.spinner("Processing..."):
                if b_type == "Update Student Rates":
                    count = 0
                    for _, row in df_bulk.iterrows():
                        if int(row['ID']) != 0:
                            session.query(Student).filter(Student.id == int(row['ID'])).update({"price_per_hr": float(row['New_Price_Per_Hr'])})
                            count += 1
                    session.commit(); st.success(f"✅ Successfully updated rates for {count} students!"); st.rerun()
                else:
                    max_tx_id = session.query(func.max(Transaction.id)).scalar() or 0
                    student_rates = {s.id: s.price_per_hr for s in session.query(Student).all()}
                    bulk_list = []; errors_list = []
                    
                    for i, row in df_bulk.iterrows():
                        target_sid = int(row['ID']) if pd.notnull(row.get('ID')) else 0
                        # تجاهل سطر المثال أو الطلاب غير الموجودين
                        if target_sid == 0 or target_sid not in student_rates:
                            if target_sid != 0: errors_list.append(f"Row {i+2}: ID {target_sid} not found.")
                            continue
                        
                        s_rate, dr, cr, s_type_id, p_fix = student_rates[target_sid], 0.0, 0.0, None, "TX"
                        r_dsc = str(row.get('Description', '')).strip()
                        f_dsc = b_type if not r_dsc or r_dsc in ['0', '0.0', 'nan', 'NaN'] else r_dsc

                        if b_type == "Bulk Payments":
                            p_fix, cr = "PAY", float(row.get('Amount', 0))
                            f_dsc = f"Bank: {row.get('Bank Name', 'N/A')} | Ref: {row.get('Bank Ref', 'N/A')}"
                        elif b_type == "Bulk Scholarships":
                            p_fix, s_name = "SCH", str(row.get('Scholarship Name', ''))
                            s_type_id = sch_map.get(s_name)
                            s_pct = float(row.get('Percentage', 0))
                            cr = (15 * s_rate) * (s_pct / 100)
                            f_dsc = f"Scholarship: {s_name} ({s_pct}%)"
                        elif b_type == "Bulk Invoices (Tuition)":
                            p_fix, h_val = "INV", float(row.get('Hours', 15))
                            dr = h_val * s_rate
                            f_dsc = f"Tuition Invoice ({h_val} CH @ {s_rate:,.2f} EGP/Hr)"
                        elif b_type == "Credit Hours Adjustments":
                            p_fix, h_delta = "ADJ", float(row.get('Hours_Delta', 0))
                            val = abs(h_delta * s_rate)
                            dr = val if h_delta > 0 else 0
                            cr = val if h_delta < 0 else 0
                            f_dsc = f"Credit Hours Adj: {h_delta} CH @ {s_rate:,.2f}"
                        elif b_type == "General Adjustments":
                            p_fix, dr, cr = "TXN", float(row.get('Debit', 0)), float(row.get('Credit', 0))
                            if dr > 0 and cr > 0:
                                errors_list.append(f"Row {i+2}: Debit and Credit in one row skipped."); continue

                        bulk_list.append(Transaction(
                            reference_no=f"{p_fix}-{max_tx_id+i+1:06d}", 
                            student_id=target_sid, 
                            scholarship_type_id=s_type_id, 
                            transaction_type=b_type, 
                            description=f_dsc, 
                            debit=dr, credit=cr, 
                            entry_date=pd.to_datetime(row.get('Date', datetime.now())).date(), 
                            term=str(row.get('Term', 'Spring')), 
                            academic_year=int(row.get('Year', 2026))
                        ))
                    
                    if bulk_list:
                        session.bulk_save_objects(bulk_list); session.commit()
                        st.success(f"✅ Successfully posted {len(bulk_list)} entries."); st.rerun()
                    if errors_list:
                        for e in errors_list: st.error(e)
