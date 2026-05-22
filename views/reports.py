# pages/reports.py
import io
import pandas as pd
import streamlit as st
from sqlalchemy import text

from config import VALID_TERMS, VALID_STATUSES, VALID_COLLEGES
from models import highlight_negatives


FORMATS = [
    "Accounting Summary",
    "Full Detailed Log",
    "Period Closing (Activity Summary)",
    "Student Academic Status Report",
]


def render(engine, available_years):
    st.subheader("📈 Financial Management Reports")

    if "report_params" not in st.session_state:
        st.session_state["report_params"] = None

    with st.form("reports_filter_form", clear_on_submit=False):
        c1, c2, c3, c4 = st.columns(4)
        sel_col    = c1.multiselect("College",  VALID_COLLEGES)
        sel_term   = c2.multiselect("Term",     VALID_TERMS)
        sel_year   = c3.multiselect("Year",     available_years)
        sel_status = c4.multiselect("Status",   VALID_STATUSES)
        c5, c6     = st.columns([1, 2])
        sel_dates  = c5.date_input("Date Range", [])
        rep_fmt    = c6.radio("Format:", FORMATS, horizontal=True)
        if st.form_submit_button("📂 Generate Report"):
            st.session_state["report_params"] = {
                "col":    sel_col,  "term":   sel_term,
                "year":   sel_year, "status": sel_status,
                "dates":  sel_dates,"format": rep_fmt,
            }

    p = st.session_state.get("report_params")
    if not p:
        return

    common = {
        "c_cnt": len(p["col"]),   "cls":  tuple(p["col"])    or ("",),
        "t_cnt": len(p["term"]),  "trms": tuple(p["term"])   or ("",),
        "y_cnt": len(p["year"]),  "yrs":  tuple(p["year"])   or (-1,),
        "s_cnt": len(p["status"]),"stats":tuple(p["status"]) or ("",),
    }

    df = pd.DataFrame()   # defined in every branch; avoids scope leak

    with st.spinner("Generating report…"):

        if p["format"] == "Student Academic Status Report":
            sql = text("""
                SELECT s.id AS "Student ID", s.name AS "Student Name",
                    s.college AS "College", s.program AS "Program",
                    ss.term AS "Term", ss.academic_year AS "Year", ss.status AS "Academic Status"
                FROM student_statuses ss JOIN students s ON ss.student_id=s.id
                WHERE (:c_cnt=0 OR s.college IN :cls)
                    AND (:t_cnt=0 OR ss.term IN :trms)
                    AND (:y_cnt=0 OR ss.academic_year IN :yrs)
                    /* 🟢 التعديل: استبعاد طلاب التيست افتراضياً، وإظهارهم فقط لو تم اختيارهم بالفلتر */
                    AND (
                        (:s_cnt=0 AND COALESCE((SELECT status FROM student_statuses WHERE student_id=s.id ORDER BY id DESC LIMIT 1),'Not Set') != 'Test')
                        OR (:s_cnt>0 AND ss.status IN :stats)
                    )
                ORDER BY ss.academic_year DESC, ss.term, s.college, s.id
            """)
            df = pd.read_sql(sql, con=engine, params=common)
            if df.empty:
                st.warning("No status history found.")
            else:
                st.dataframe(df, use_container_width=True)

        elif p["format"] == "Accounting Summary":
            sql = text("""
                SELECT s.id AS "ID", s.name AS "Student Name", s.college AS "College",
                    s.email AS "Email",
                    COALESCE((SELECT status FROM student_statuses WHERE student_id=s.id ORDER BY id DESC LIMIT 1),'Not Set') AS "Current Status",
                    s.price_per_hr AS "Price/Hr",
                    COALESCE(SUM(t.hours_change),0) AS "Reg. Hours",
                    COALESCE(SUM(CASE WHEN t.transaction_type IN ('Invoice','Bulk Invoices (Tuition)') THEN t.debit ELSE 0 END),0) AS "Tuition Billed",
                    COALESCE(SUM(CASE WHEN t.transaction_type IN ('Other Fees','Bulk Other Fees') THEN t.debit ELSE 0 END),0) AS "Other Fees",
                    COALESCE(SUM(CASE WHEN t.transaction_type IN ('Discount','Bulk Scholarships') THEN t.credit-t.debit ELSE 0 END),0) AS "Discounts",
                    COALESCE(SUM(CASE WHEN t.transaction_type IN ('Payment Receipt','Bulk Payments') THEN t.credit-t.debit ELSE 0 END),0) AS "Payments",
                    COALESCE(SUM(CASE WHEN t.transaction_type IN ('Credit Hours Adjustment','Credit Hours Adjustments','General Adjustment','General Adjustments') THEN t.debit-t.credit ELSE 0 END),0) AS "Adjustments",
                    COALESCE(SUM(t.debit)-SUM(t.credit),0) AS "Balance"
                FROM students s LEFT JOIN transactions t ON s.id=t.student_id
                    AND (:t_cnt=0 OR t.term IN :trms)
                    AND (:y_cnt=0 OR t.academic_year IN :yrs)
                WHERE (:c_cnt=0 OR s.college IN :cls)
                    /* 🟢 التعديل: استبعاد طلاب التيست من ملخص الإيرادات */
                    AND (
                        (:s_cnt=0 AND COALESCE((SELECT status FROM student_statuses WHERE student_id=s.id ORDER BY id DESC LIMIT 1),'Not Set') != 'Test')
                        OR (:s_cnt>0 AND COALESCE((SELECT status FROM student_statuses WHERE student_id=s.id ORDER BY id DESC LIMIT 1),'Not Set') IN :stats)
                    )
                GROUP BY s.id,s.name,s.college,s.email,s.price_per_hr ORDER BY s.id
            """)
            df = pd.read_sql(sql, con=engine, params=common)
            if df.empty:
                st.warning("No data found.")
            else:
                num_cols = ["Reg. Hours","Tuition Billed","Other Fees","Discounts","Payments","Adjustments","Balance"]
                totals   = {c: df[c].sum() if c in num_cols else ("🔢 TOTAL" if c=="Student Name" else "") for c in df.columns}
                totals["Student Name"] = "🔢 TOTAL"
                df_show  = pd.concat([df, pd.DataFrame([totals])], ignore_index=True)
                fmt = {"Price/Hr":"{:,.2f}","Reg. Hours":"{:,.1f}","Tuition Billed":"{:,.2f}",
                       "Other Fees":"{:,.2f}","Discounts":"{:,.2f}","Payments":"{:,.2f}",
                       "Adjustments":"{:,.2f}","Balance":"{:,.2f}"}
                st.dataframe(
                    df_show.style.format(fmt)
                        .map(highlight_negatives, subset=["Balance"])
                        .apply(lambda x: ["background:#f0f4ff;font-weight:bold" if x.name==len(df_show)-1 else "" for _ in x], axis=1),
                    use_container_width=True,
                )

        elif p["format"] == "Period Closing (Activity Summary)":
            if len(p["dates"]) != 2:
                st.warning("⚠️ Please select a Date Range for Period Closing.")
                return
            params = {**common, "s_date": p["dates"][0], "e_date": p["dates"][1]}
            sql = text("""
                SELECT s.id AS "ID", s.name AS "Student Name", s.college AS "College",
                    COALESCE((SELECT status FROM student_statuses WHERE student_id=s.id ORDER BY id DESC LIMIT 1),'Not Set') AS "Current Status",
                    COALESCE(SUM(t.hours_change),0) AS "CH Changed",
                    COALESCE(SUM(CASE WHEN t.transaction_type IN ('Invoice','Bulk Invoices (Tuition)') THEN t.debit ELSE 0 END),0) AS "Tuition Billed",
                    COALESCE(SUM(CASE WHEN t.transaction_type IN ('Other Fees','Bulk Other Fees') THEN t.debit ELSE 0 END),0) AS "Other Fees",
                    COALESCE(SUM(CASE WHEN t.transaction_type IN ('Discount','Bulk Scholarships') THEN t.credit-t.debit ELSE 0 END),0) AS "New Discounts",
                    COALESCE(SUM(CASE WHEN t.transaction_type IN ('Payment Receipt','Bulk Payments') THEN t.credit-t.debit ELSE 0 END),0) AS "Payments Received",
                    COALESCE(SUM(CASE WHEN t.transaction_type IN ('Credit Hours Adjustment','Credit Hours Adjustments','General Adjustment','General Adjustments') THEN t.debit-t.credit ELSE 0 END),0) AS "Adjustments",
                    COALESCE(SUM(t.debit)-SUM(t.credit),0) AS "Net Period Change"
                FROM transactions t JOIN students s ON t.student_id=s.id
                WHERE (:c_cnt=0 OR s.college IN :cls)
                    AND (:t_cnt=0 OR t.term IN :trms)
                    AND (:y_cnt=0 OR t.academic_year IN :yrs)
                    /* 🟢 التعديل: استبعاد طلاب التيست من تقفيل الفترات المالية */
                    AND (
                        (:s_cnt=0 AND COALESCE((SELECT status FROM student_statuses WHERE student_id=s.id ORDER BY id DESC LIMIT 1),'Not Set') != 'Test')
                        OR (:s_cnt>0 AND COALESCE((SELECT status FROM student_statuses WHERE student_id=s.id ORDER BY id DESC LIMIT 1),'Not Set') IN :stats)
                    )
                    AND t.entry_date BETWEEN :s_date AND :e_date
                GROUP BY s.id,s.name,s.college
                HAVING COALESCE(SUM(t.debit),0)>0 OR COALESCE(SUM(t.credit),0)>0
                ORDER BY s.id
            """)
            df = pd.read_sql(sql, con=engine, params=params)
            if df.empty:
                st.warning("No financial activity in the selected date range.")
            else:
                num_cols = ["CH Changed","Tuition Billed","Other Fees","New Discounts","Payments Received","Adjustments","Net Period Change"]
                totals = {c: df[c].sum() if c in num_cols else ("🔢 TOTAL" if c=="Student Name" else "") for c in df.columns}
                totals["Student Name"] = "🔢 TOTAL"
                df_show = pd.concat([df, pd.DataFrame([totals])], ignore_index=True)
                fmt = {c:"{:,.2f}" for c in num_cols}; fmt["CH Changed"] = "{:,.1f}"
                st.dataframe(
                    df_show.style.format(fmt)
                        .map(highlight_negatives, subset=["Net Period Change"])
                        .apply(lambda x: ["background:#f0f4ff;font-weight:bold" if x.name==len(df_show)-1 else "" for _ in x], axis=1),
                    use_container_width=True,
                )

        else:  # Full Detailed Log
            params = {**common,
                      "has_dates": 1 if len(p["dates"])==2 else 0,
                      "s_date": p["dates"][0] if len(p["dates"])==2 else None,
                      "e_date": p["dates"][1] if len(p["dates"])==2 else None}
            sql = text("""
                SELECT t.student_id, s.name, s.college,
                    COALESCE((SELECT status FROM student_statuses WHERE student_id=s.id ORDER BY id DESC LIMIT 1),'Not Set') AS "Current Status",
                    t.reference_no, t.entry_date, t.term, t.academic_year,
                    t.description, t.hours_change AS "Hours", t.debit, t.credit
                FROM transactions t JOIN students s ON t.student_id=s.id
                WHERE (:c_cnt=0 OR s.college IN :cls)
                    AND (:t_cnt=0 OR t.term IN :trms)
                    AND (:y_cnt=0 OR t.academic_year IN :yrs)
                    /* 🟢 التعديل: استبعاد طلاب التيست من سجل الحركات التفصيلي */
                    AND (
                        (:s_cnt=0 AND COALESCE((SELECT status FROM student_statuses WHERE student_id=s.id ORDER BY id DESC LIMIT 1),'Not Set') != 'Test')
                        OR (:s_cnt>0 AND COALESCE((SELECT status FROM student_statuses WHERE student_id=s.id ORDER BY id DESC LIMIT 1),'Not Set') IN :stats)
                    )
                    AND (:has_dates=0 OR (t.entry_date BETWEEN :s_date AND :e_date))
                ORDER BY t.student_id, t.entry_date DESC
            """)
            df = pd.read_sql(sql, con=engine, params=params)
            if df.empty:
                st.warning("No activity found.")
            else:
                st.dataframe(df, use_container_width=True, column_config={
                    "Hours": st.column_config.NumberColumn(format="%,.1f"),
                    "debit": st.column_config.NumberColumn(format="%,.2f"),
                    "credit":st.column_config.NumberColumn(format="%,.2f"),
                })

    if not df.empty:
        buf = io.BytesIO()
        df.to_excel(buf, index=False)
        st.download_button("📗 Download Excel Report", buf.getvalue(),
                           file_name=f"Report_{p['format'].replace(' ','_')}.xlsx",
                           use_container_width=True)
