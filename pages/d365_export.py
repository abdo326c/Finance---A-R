import io
import datetime
import pandas as pd
import streamlit as st
from sqlalchemy.sql import text
from models import get_db, Transaction, Student
from config import VALID_TERMS, DEFAULT_YEAR

def render(engine, available_years):
    st.subheader("🔄 Dynamics 365 Integration - FTI Export")
    st.markdown("Extract financial transactions (Invoices/Discounts) in a format ready for direct upload as a Free Text Invoice.")

    with st.form("d365_export_form"):
        col1, col2, col3 = st.columns(3)
        export_term = col1.selectbox("Term:", VALID_TERMS)
        export_year = col2.selectbox("Year:", available_years)
        
        tx_type_filter = col3.selectbox("Transaction Type:", [
            "All Transactions",
            "Invoices Only (Tuition & Fees)", 
            "Discounts Only (Scholarships)"
        ])

        st.markdown("---")
        st.markdown("### ⚙️ Accounting Routing Settings")
        
        col_rev, col_disc = st.columns(2)
        revenue_account = col_rev.text_input("Revenue Ledger Account (For Invoices/Fees) *", value="4101028")
        discount_account = col_disc.text_input("Discount Ledger Account (For Scholarships) *", value="4104001")
        
        col_prof, col_curr = st.columns(2)
        posting_profile = col_prof.text_input("Posting Profile", value="STD")
        currency_code = col_curr.text_input("Currency", value="EGP")
        
        st.markdown("#### 📅 Invoice & Due Dates")
        col_inv_date, col_due_date = st.columns(2)
        # التاريخ هيطلع بصيغة YYYY-MM-DD
        invoice_date = col_inv_date.date_input("Invoice Date", datetime.date.today())
        due_date = col_due_date.date_input("Due Date", datetime.date.today())

        st.markdown("#### 🔢 Invoice Numbering & References")
        col_fti, col_ref = st.columns(2)
        # التعديل الرابع: إدخال آخر رقم فاتورة
        last_fti = col_fti.text_input("Last D365 FTI Number (e.g., FTI-0012133) *", value="FTI-0012133")
        # التعديل الخامس: حقل مرجع العميل
        customer_ref = col_ref.text_input("Customer Reference (Optional)", value="")

        submitted = st.form_submit_button("🚀 Generate D365 Template", type="primary")

    if submitted:
        if not revenue_account or not discount_account:
            st.error("⚠️ Please enter both Revenue and Discount Ledger Account Numbers.")
            return
            
        if not last_fti or '-' not in last_fti:
            st.error("⚠️ Please enter a valid Last FTI Number containing a hyphen (e.g., FTI-0012133).")
            return

        # تحليل رقم الفاتورة لفصله عن الحروف وتجهيزه للزيادة التلقائية
        try:
            prefix, num_str = last_fti.rsplit('-', 1)
            fti_counter = int(num_str)
            num_length = len(num_str) # عشان نحافظ على الأصفار اللي على الشمال (e.g., 0012133)
        except ValueError:
            st.error("⚠️ The part after the hyphen must be a number.")
            return

        with st.spinner("Preparing D365 Export File..."):
            with get_db() as db:
                query = db.query(Transaction, Student).join(Student, Transaction.student_id == Student.id)
                query = query.filter(Transaction.term == export_term, Transaction.academic_year == export_year)

                if tx_type_filter == "Invoices Only (Tuition & Fees)":
                    query = query.filter(Transaction.transaction_type.in_(['Invoice', 'Bulk Invoices (Tuition)', 'Other Fees', 'Bulk Other Fees']))
                elif tx_type_filter == "Discounts Only (Scholarships)":
                    query = query.filter(Transaction.transaction_type.in_(['Discount', 'Bulk Scholarships']))

                results = query.order_by(Transaction.id).all()

                if not results:
                    st.warning("⚠️ No matching transactions found for this Term/Year.")
                    return

                d365_data = []
                for idx, (tx, student) in enumerate(results, start=1):
                    is_discount = tx.transaction_type in ['Discount', 'Bulk Scholarships']
                    amount = tx.credit if is_discount else tx.debit
                    if amount <= 0: continue 

                    # 1. زيادة رقم الفاتورة (Auto Increment FTI)
                    fti_counter += 1
                    current_fti = f"{prefix}-{str(fti_counter).zfill(num_length)}"

                    # 2. إجبار رقم الطالب ليكون 9 أرقام نصية (Zero-Padded String)
                    student_id_str = str(student.id).zfill(9)

                    target_ledger = discount_account if is_discount else revenue_account
                    
                    # 3. استخدام الـ Dimension المسجل للطالب (أو بناء واحد احتياطي لو الطالب ملوش)
                    dim_val = getattr(student, 'financial_dimension', None)
                    if not dim_val:
                        dim_val = f"Academic||||||||{student.college}|{student.program if student.program else ''}|{student_id_str}|{tx.term}|"

                    d365_row = {
                        "FREETEXTNUMBER": current_fti,
                        "LINENUMBER": 1, 
                        "AMOUNTCUR": amount,
                        "CURRENCYCODE": currency_code,
                        "CUSTOMERACCOUNT": student_id_str, # رقم بـ 9 خانات
                        "CUSTOMERREFERENCE": customer_ref, # مرجع اختياري
                        "DEFAULTDIMENSIONDISPLAYVALUE": dim_val, # من الداتا بيز
                        "DESCRIPTION": tx.description,
                        "DOCUMENTDATE": invoice_date.strftime("%Y-%m-%d"), # فورمات التاريخ 2026-05-21
                        "DUEDATE": due_date.strftime("%Y-%m-%d"),
                        "HEADERDEFAULTDIMENSIONDISPLAYVALUE": dim_val,
                        "INVOICEACCOUNT": student_id_str,
                        "INVOICEDATE": invoice_date.strftime("%Y-%m-%d"),
                        "LEDGERDIMENSIONDISPLAYVALUE": target_ledger, 
                        "POSTINGPROFILE": posting_profile,
                        "QUANTITY": 1,
                        "UNITPRICE": amount
                    }
                    d365_data.append(d365_row)

                if d365_data:
                    df_d365 = pd.DataFrame(d365_data)
                    
                    st.success(f"✅ Successfully prepared {len(df_d365)} rows for upload!")
                    st.dataframe(df_d365.head(10), use_container_width=True) 

                    csv_buf = df_d365.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download D365 CSV File",
                        data=csv_buf,
                        # التعديل الثاني: اسم الملف المطلوب بالضبط
                        file_name="Customer_free_text_invoice.csv", 
                        mime="text/csv",
                        type="primary",
                        use_container_width=True
                    )
