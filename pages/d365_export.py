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
        
        # Select transaction type to export
        tx_type_filter = col3.selectbox("Transaction Type:", [
            "All Transactions",
            "Invoices Only (Tuition & Fees)", 
            "Discounts Only (Scholarships)"
        ])

        st.markdown("---")
        st.markdown("### ⚙️ Accounting Routing Settings (Ledgers & Dimensions)")
        
        col_rev, col_disc = st.columns(2)
        revenue_account = col_rev.text_input("Revenue Ledger Account (For Invoices/Fees) *", value="4101028")
        discount_account = col_disc.text_input("Discount Ledger Account (For Scholarships) *", value="4104001")
        
        col_prof, col_curr = st.columns(2)
        posting_profile = col_prof.text_input("Posting Profile", value="STD")
        currency_code = col_curr.text_input("Currency", value="EGP")
        
        # التعديل هنا: إضافة حقول اختيار التواريخ
        st.markdown("#### 📅 Invoice & Due Dates")
        col_inv_date, col_due_date = st.columns(2)
        invoice_date = col_inv_date.date_input("Invoice Date (DOCUMENTDATE & INVOICEDATE)", datetime.date.today())
        due_date = col_due_date.date_input("Due Date (DUEDATE)", datetime.date.today())

        submitted = st.form_submit_button("🚀 Generate D365 Template", type="primary")

    if submitted:
        if not revenue_account or not discount_account:
            st.error("⚠️ Please enter both Revenue and Discount Ledger Account Numbers.")
            return

        with st.spinner("Preparing D365 Export File..."):
            with get_db() as db:
                # 1. Filter data based on selections
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

                # 2. Prepare data to exactly match D365 format
                d365_data = []
                for idx, (tx, student) in enumerate(results, start=1):
                    
                    is_discount = tx.transaction_type in ['Discount', 'Bulk Scholarships']
                    amount = tx.credit if is_discount else tx.debit
                    if amount <= 0: continue 

                    target_ledger = discount_account if is_discount else revenue_account
                    dimension_string = f"Academic||||||||{student.college}|{student.program if student.program else ''}|{student.id}|{tx.term}|"

                    d365_row = {
                        "FREETEXTNUMBER": tx.reference_no,
                        "LINENUMBER": 1, 
                        "AMOUNTCUR": amount,
                        "CURRENCYCODE": currency_code,
                        "CUSTOMERACCOUNT": student.id,
                        "CUSTOMERREFERENCE": "Sys_Export",
                        "DEFAULTDIMENSIONDISPLAYVALUE": dimension_string,
                        "DESCRIPTION": tx.description,
                        # التعديل هنا: تمرير التواريخ المختارة من الواجهة وتنسيقها
                        "DOCUMENTDATE": invoice_date.strftime("%Y-%m-%d"),
                        "DUEDATE": due_date.strftime("%Y-%m-%d"),
                        "HEADERDEFAULTDIMENSIONDISPLAYVALUE": dimension_string,
                        "INVOICEACCOUNT": student.id,
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

                    # 3. Export the file as CSV
                    csv_buf = df_d365.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download D365 CSV File",
                        data=csv_buf,
                        file_name=f"FTI_Export_{export_term}_{export_year}.csv",
                        mime="text/csv",
                        type="primary",
                        use_container_width=True
                    )
