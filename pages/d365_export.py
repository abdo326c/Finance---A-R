import io
import datetime
import pandas as pd
import streamlit as st
from sqlalchemy.sql import text
from models import get_db, Transaction, Student
from config import VALID_TERMS, DEFAULT_YEAR

def render(engine, available_years):
    st.subheader("🔄 Dynamics 365 Integration - FTI Export")
    st.markdown("Extract financial transactions (Invoices/Discounts/Fees) in a format ready for direct upload as a Free Text Invoice.")

    # تم نقل هذه الاختيارات خارج الـ Form لكي يتم تحديث الشاشة ديناميكياً
    col1, col2, col3 = st.columns(3)
    export_term = col1.selectbox("Term:", VALID_TERMS)
    export_year = col2.selectbox("Year:", available_years)
    
    tx_type_filter = col3.selectbox("Transaction Type:", [
        "All (Tuition Invoices & Discounts)",
        "Tuition Invoices Only", 
        "Discounts Only (Scholarships)",
        "Other Fees Only"
    ])

    with st.form("d365_export_form"):
        st.markdown("### ⚙️ Accounting Routing Settings")
        
        revenue_account = None
        discount_account = None
        
        # إظهار الخانات بناءً على الاختيار
        if tx_type_filter == "All (Tuition Invoices & Discounts)":
            c1, c2 = st.columns(2)
            revenue_account = c1.text_input("Tuition Revenue Ledger Account *", value="4101028")
            discount_account = c2.text_input("Discount Ledger Account *", value="4104001")
            
        elif tx_type_filter == "Tuition Invoices Only":
            revenue_account = st.text_input("Tuition Revenue Ledger Account *", value="4101028")
            
        elif tx_type_filter == "Discounts Only (Scholarships)":
            discount_account = st.text_input("Discount Ledger Account *", value="4104001")
            
        elif tx_type_filter == "Other Fees Only":
            st.info("💡 **ملاحظة هامة:** رسوم الـ Other Fees متعددة الأنواع (تأخير، كارنيه، أنشطة) ولها حسابات مختلفة. سيتم ترك عمود حساب الأستاذ العام (Ledger Account) فارغاً في الملف لتتمكن من تعبئته يدوياً بناءً على حقل الوصف (Description) لكل حركة.")
        
        col_prof, col_curr = st.columns(2)
        posting_profile = col_prof.text_input("Posting Profile", value="STD")
        currency_code = col_curr.text_input("Currency", value="EGP")
        
        st.markdown("#### 📅 Invoice & Due Dates")
        col_inv_date, col_due_date = st.columns(2)
        invoice_date = col_inv_date.date_input("Invoice Date", datetime.date.today())
        due_date = col_due_date.date_input("Due Date", datetime.date.today())

        st.markdown("#### 🔢 Invoice Numbering & References")
        col_fti, col_ref = st.columns(2)
        last_fti = col_fti.text_input("Last D365 FTI Number (e.g., FTI-0012133) *", value="FTI-0012133")
        customer_ref = col_ref.text_input("Customer Reference (Optional)", value="")

        submitted = st.form_submit_button("🚀 Generate D365 Template", type="primary")

    if submitted:
        # التحقق من إدخال الحسابات المطلوبة
        if tx_type_filter in ["All (Tuition Invoices & Discounts)", "Tuition Invoices Only"] and not revenue_account:
            st.error("⚠️ Please enter the Revenue Ledger Account.")
            return
        if tx_type_filter in ["All (Tuition Invoices & Discounts)", "Discounts Only (Scholarships)"] and not discount_account:
            st.error("⚠️ Please enter the Discount Ledger Account.")
            return
            
        if not last_fti or '-' not in last_fti:
            st.error("⚠️ Please enter a valid Last FTI Number containing a hyphen (e.g., FTI-0012133).")
            return

        try:
            prefix, num_str = last_fti.rsplit('-', 1)
            fti_counter = int(num_str)
            num_length = len(num_str)
        except ValueError:
            st.error("⚠️ The part after the hyphen must be a number.")
            return

        with st.spinner("Preparing D365 Export File..."):
            with get_db() as db:
                query = db.query(Transaction, Student).join(Student, Transaction.student_id == Student.id)
                query = query.filter(Transaction.term == export_term, Transaction.academic_year == export_year)

                # فلترة الحركات بناءً على الاختيار
                if tx_type_filter == "Tuition Invoices Only":
                    query = query.filter(Transaction.transaction_type.in_(['Invoice', 'Bulk Invoices (Tuition)']))
                elif tx_type_filter == "Discounts Only (Scholarships)":
                    query = query.filter(Transaction.transaction_type.in_(['Discount', 'Bulk Scholarships']))
                elif tx_type_filter == "Other Fees Only":
                    query = query.filter(Transaction.transaction_type.in_(['Other Fees', 'Bulk Other Fees']))
                else: 
                    # All (Tuition + Scholarships) - Excluding Other Fees
                    query = query.filter(Transaction.transaction_type.in_(['Invoice', 'Bulk Invoices (Tuition)', 'Discount', 'Bulk Scholarships']))

                results = query.order_by(Transaction.id).all()

                if not results:
                    st.warning("⚠️ No matching transactions found for this Term/Year.")
                    return

                d365_data = []
                for idx, (tx, student) in enumerate(results, start=1):
                    is_discount = tx.transaction_type in ['Discount', 'Bulk Scholarships']
                    is_other_fee = tx.transaction_type in ['Other Fees', 'Bulk Other Fees']
                    
                    amount = tx.credit if is_discount else tx.debit
                    if amount <= 0: continue 

                    fti_counter += 1
                    current_fti = f"{prefix}-{str(fti_counter).zfill(num_length)}"
                    student_id_str = str(student.id).zfill(9)

                    # تحديد حساب الأستاذ العام المناسب
                    if is_other_fee:
                        target_ledger = ""
                    elif is_discount:
                        target_ledger = discount_account
                    else:
                        target_ledger = revenue_account
                    
                    dim_val = getattr(student, 'financial_dimension', None)
                    if not dim_val or str(dim_val).lower() == 'nan':
                        dim_val = f"Academic||||||||{student.college}|{student.program if student.program else ''}|{student_id_str}|{tx.term}|"

                    d365_row = {
                        "FREETEXTNUMBER": current_fti,
                        "LINENUMBER": 1, 
                        "AMOUNTCUR": amount,
                        "CURRENCYCODE": currency_code,
                        "CUSTOMERACCOUNT": student_id_str,
                        "CUSTOMERREFERENCE": customer_ref,
                        "DEFAULTDIMENSIONDISPLAYVALUE": dim_val,
                        "DESCRIPTION": tx.description,
                        "DOCUMENTDATE": invoice_date.strftime("%Y-%m-%d"),
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
                        file_name="Customer_free_text_invoice.csv", 
                        mime="text/csv",
                        type="primary",
                        use_container_width=True
                    )
