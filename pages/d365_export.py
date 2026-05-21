import io
import pandas as pd
import streamlit as st
from sqlalchemy.sql import text
from models import get_db, Transaction, Student
from config import VALID_TERMS, DEFAULT_YEAR

def render(engine, available_years):
    st.subheader("🔄 Dynamics 365 Integration - FTI Export")
    st.markdown("استخراج الحركات المالية (فواتير/خصومات) بصيغة جاهزة للرفع المباشر كـ Free Text Invoice.")

    with st.form("d365_export_form"):
        col1, col2, col3 = st.columns(3)
        export_term = col1.selectbox("التيرم (Term):", VALID_TERMS)
        export_year = col2.selectbox("السنة (Year):", available_years)
        
        # اختيار نوع الحركات اللي عايز تخرجها
        tx_type_filter = col3.selectbox("نوع الحركات (Transaction Type):", [
            "Invoices Only (Tuition & Fees)", 
            "Discounts Only (Scholarships)", 
            "All Transactions"
        ])

        st.markdown("---")
        st.markdown("### ⚙️ إعدادات التوجيه المحاسبي (Ledger & Dimensions)")
        col4, col5, col6 = st.columns(3)
        
        # أرقام الحسابات للربط مع شجرة الحسابات في D365
        ledger_account = col4.text_input("رقم حساب الأستاذ العام (Ledger Account) *", value="4101028")
        posting_profile = col5.text_input("Posting Profile", value="STD")
        currency_code = col6.text_input("العملة (Currency)", value="EGP")

        submitted = st.form_submit_button("🚀 Generate D365 Template", type="primary")

    if submitted:
        if not ledger_account:
            st.error("⚠️ برجاء إدخال رقم حساب الأستاذ العام.")
            return

        with st.spinner("Preparing D365 Export File..."):
            with get_db() as db:
                # 1. فلترة البيانات بناءً على اختياراتك
                query = db.query(Transaction, Student).join(Student, Transaction.student_id == Student.id)
                query = query.filter(Transaction.term == export_term, Transaction.academic_year == export_year)

                if tx_type_filter == "Invoices Only (Tuition & Fees)":
                    query = query.filter(Transaction.transaction_type.in_(['Invoice', 'Bulk Invoices (Tuition)', 'Other Fees', 'Bulk Other Fees']))
                elif tx_type_filter == "Discounts Only (Scholarships)":
                    query = query.filter(Transaction.transaction_type.in_(['Discount', 'Bulk Scholarships']))

                results = query.order_by(Transaction.id).all()

                if not results:
                    st.warning("⚠️ لا توجد حركات مطابقة للبحث في هذا التيرم/السنة.")
                    return

                # 2. تجهيز الداتا بالشكل المطابق تماماً لملف D365
                d365_data = []
                for idx, (tx, student) in enumerate(results, start=1):
                    
                    # تحديد المبلغ (إذا كانت فاتورة نأخذ المدين، وإذا خصم نأخذ الدائن)
                    amount = tx.debit if tx.debit > 0 else tx.credit
                    if amount <= 0: continue # تخطي الحركات الصفرية

                    # بناء الأبعاد المالية (Financial Dimensions) بناءً على الفورمات في ملفك
                    # Format: Department||||||||CostCenter|Program|StudentID|Term|
                    # يمكنك تعديل هذا السطر ليتطابق مع ترتيب الـ Account Structures في جامعتكم
                    dimension_string = f"Academic||||||||{student.college}|{student.program if student.program else ''}|{student.id}|{tx.term}|"

                    d365_row = {
                        "FREETEXTNUMBER": tx.reference_no,
                        "LINENUMBER": 1, # سطر واحد لكل حركة
                        "AMOUNTCUR": amount,
                        "CURRENCYCODE": currency_code,
                        "CUSTOMERACCOUNT": student.id,
                        "CUSTOMERREFERENCE": "Sys_Export",
                        "DEFAULTDIMENSIONDISPLAYVALUE": dimension_string,
                        "DESCRIPTION": tx.description,
                        "DOCUMENTDATE": tx.entry_date.strftime("%Y-%m-%d"),
                        "DUEDATE": tx.entry_date.strftime("%Y-%m-%d"),
                        "HEADERDEFAULTDIMENSIONDISPLAYVALUE": dimension_string,
                        "INVOICEACCOUNT": student.id,
                        "INVOICEDATE": tx.entry_date.strftime("%Y-%m-%d"),
                        "LEDGERDIMENSIONDISPLAYVALUE": ledger_account, # حساب الإيراد أو الخصم اللي دخلته
                        "POSTINGPROFILE": posting_profile,
                        "QUANTITY": 1,
                        "UNITPRICE": amount
                    }
                    d365_data.append(d365_row)

                if d365_data:
                    df_d365 = pd.DataFrame(d365_data)
                    
                    st.success(f"✅ تم تجهيز {len(df_d365)} سطر للرفع بنجاح!")
                    st.dataframe(df_d365.head(10), use_container_width=True) # عرض أول 10 سطور للمراجعة

                    # 3. إخراج الملف كـ CSV أو Excel
                    csv_buf = df_d365.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download D365 CSV File",
                        data=csv_buf,
                        file_name=f"FTI_Export_{export_term}_{export_year}.csv",
                        mime="text/csv",
                        type="primary",
                        use_container_width=True
                    )
