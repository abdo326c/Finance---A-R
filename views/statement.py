# pages/statement.py
import io
import pandas as pd
import streamlit as st

from config import VALID_TERMS
from models import get_db, Transaction, Student
from pdf_utils import create_pdf


def render(engine, available_years):
    st.subheader("Transaction Search & Statement of Account")
    st.markdown("💡 Leave Student ID blank and enter a Bank Ref or System Ref to search globally.")

    if "stmt_params" not in st.session_state:
        st.session_state["stmt_params"] = None

    with st.form("stmt_search_form", clear_on_submit=False):
        c1, c2, c3 = st.columns(3)
        default_id = str(st.session_state.get("lookup_id","")) if st.session_state.get("lookup_id",0)>0 else ""
        sid_raw        = c1.text_input("Student ID", value=default_id, placeholder="e.g. 26100123")
        sys_ref        = c2.text_input("System Ref No", placeholder="e.g. INV-004751")
        bank_ref       = c3.text_input("Bank Ref / Description", placeholder="e.g. 12345 or CIB")
        f1, f2, f3     = st.columns(3)
        date_range     = f1.date_input("Date Range", [])
        sel_terms      = f2.multiselect("Terms", VALID_TERMS)
        sel_years      = f3.multiselect("Years", available_years)
        if st.form_submit_button("🔍 Search Transactions"):
            st.session_state["stmt_params"] = {
                "sid":   int(sid_raw) if sid_raw.strip().isdigit() else 0,
                "sys":   sys_ref, "bank": bank_ref,
                "dates": date_range,
                "terms": sel_terms, "years": sel_years,
            }

    p = st.session_state.get("stmt_params")
    if not p:
        return
    if not any([p["sid"]>0, p["sys"], p["bank"], len(p["dates"])==2, p["terms"], p["years"]]):
        return

    with get_db() as db:
        q = db.query(Transaction, Student).join(Student, Transaction.student_id == Student.id)
        if p["sid"]  > 0:          q = q.filter(Transaction.student_id == p["sid"])
        if p["sys"]:               q = q.filter(Transaction.reference_no.ilike(f"%{p['sys']}%"))
        if p["bank"]:              q = q.filter(Transaction.description.ilike(f"%{p['bank']}%"))
        if len(p["dates"]) == 2:   q = q.filter(Transaction.entry_date.between(*p["dates"]))
        if p["terms"]:             q = q.filter(Transaction.term.in_(p["terms"]))
        if p["years"]:             q = q.filter(Transaction.academic_year.in_(p["years"]))

        rows = q.order_by(Transaction.entry_date.desc()).limit(5000).all()

    if not rows:
        st.warning("⚠️ No transactions found matching these criteria.")
        return

    df = pd.DataFrame([{
        "Student ID": s.id, "Name": s.name, "Ref No": t.reference_no,
        "Date": t.entry_date, "Term": t.term, "Year": t.academic_year,
        "Type": t.transaction_type, "Description": t.description,
        "Debit": t.debit, "Credit": t.credit,
    } for t, s in rows])

    st.dataframe(df, use_container_width=True, column_config={
        "Debit":  st.column_config.NumberColumn(format="%,.2f"),
        "Credit": st.column_config.NumberColumn(format="%,.2f"),
    })

    if p["sid"] > 0:
        total_d = sum(t.debit  for t, _ in rows)
        total_c = sum(t.credit for t, _ in rows)
        net     = total_d - total_c
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Debit",     f"{total_d:,.2f} EGP")
        m2.metric("Total Credit",    f"{total_c:,.2f} EGP")
        m3.metric("Net Balance Due", f"{net:,.2f} EGP")

        df_pdf = pd.DataFrame([{
            "Ref No": t.reference_no, "Date": t.entry_date, "Term": t.term,
            "Year": t.academic_year, "Type": t.transaction_type,
            "Description": t.description,
            "Debit":  f"{t.debit:,.2f}", "Credit": f"{t.credit:,.2f}",
        } for t, _ in rows])

        b1, b2 = st.columns(2)
        with b1:
            pdf_bytes = create_pdf(p["sid"], rows[0][1].name, df_pdf, net, total_d, total_c)
            st.download_button("📄 Download PDF Statement", pdf_bytes,
                               file_name=f"SOA_{p['sid']}.pdf", use_container_width=True)
        with b2:
            df_xl = df.copy()
            df_xl.loc[len(df_xl)] = {
                "Student ID":"","Name":"","Ref No":"","Date":"","Term":"","Year":"",
                "Type":"","Description":"TOTALS","Debit":total_d,"Credit":total_c,
            }
            buf = io.BytesIO()
            df_xl.to_excel(buf, index=False)
            st.download_button("📗 Download Excel Sheet", buf.getvalue(),
                               file_name=f"SOA_{p['sid']}.xlsx", use_container_width=True)
