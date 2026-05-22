# pages/dashboard.py
import io
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.sql import func

from config import VALID_TERMS, VALID_COLLEGES, DEFAULT_YEAR
# 🟢 التعديل هنا: استوردنا engine عشان نستخدمه مباشرة جوه دوال الكاش
from models import get_db, Transaction, Student, StudentStatus, highlight_negatives, engine


# تفعيل الكاش لمدة 10 دقائق عشان نخفف الحمل عن Supabase
@st.cache_data(ttl=600)
def fetch_dashboard_metrics(term_f, year_f, college_f):
    with get_db() as db:
        # استبعاد طلاب الـ Test من الحسابات
        exclude_test_sql = text("COALESCE((SELECT status FROM student_statuses WHERE student_id=students.id ORDER BY id DESC LIMIT 1),'Not Set') != 'Test'")
        
        base_q    = db.query(Transaction).join(Student, Transaction.student_id == Student.id).filter(exclude_test_sql)
        status_q  = db.query(StudentStatus).filter(StudentStatus.status == "Active")
        student_q = db.query(Student).filter(exclude_test_sql)

        if term_f != "All Terms":
            base_q   = base_q.filter(Transaction.term == term_f)
            status_q = status_q.filter(StudentStatus.term == term_f)
        if year_f != "All Years":
            yr = int(year_f)
            base_q   = base_q.filter(Transaction.academic_year == yr)
            status_q = status_q.filter(StudentStatus.academic_year == yr)
        if college_f != "All Colleges":
            base_q    = base_q.filter(Student.college == college_f)
            student_q = student_q.filter(Student.college == college_f)
            status_q  = status_q.join(Student, StudentStatus.student_id == Student.id)\
                                 .filter(Student.college == college_f)

        def agg(types, col="debit"):
            return base_q.filter(Transaction.transaction_type.in_(types))\
                         .with_entities(func.sum(getattr(Transaction, col))).scalar() or 0.0

        # حساب المقاييس
        gross_billed    = agg(["Invoice","Bulk Invoices (Tuition)","Other Fees","Bulk Other Fees"])
        total_discounts = (agg(["Discount","Bulk Scholarships"],"credit")
                         - agg(["Discount","Bulk Scholarships"],"debit"))
        total_payments  = (agg(["Payment Receipt","Bulk Payments"],"credit")
                         - agg(["Payment Receipt","Bulk Payments"],"debit"))
                         
        total_debit     = base_q.with_entities(func.sum(Transaction.debit)).scalar() or 0.0
        total_credit    = base_q.with_entities(func.sum(Transaction.credit)).scalar() or 0.0
        net_balance     = total_debit - total_credit
        net_adjustments = net_balance - (gross_billed - total_discounts - total_payments)
        
        total_students  = student_q.count()
        active_count    = status_q.distinct(StudentStatus.student_id).count()
        
        return {
            "gross_billed": gross_billed,
            "total_discounts": total_discounts,
            "total_payments": total_payments,
            "net_balance": net_balance,
            "net_adjustments": net_adjustments,
            "total_students": total_students,
            "active_count": active_count
        }

# 🟢 التعديل الأهم: الدالة بتاخد الفلاتر بس، وبتفتح اتصال رسمي من engine المعتمد
@st.cache_data(ttl=600)
def fetch_college_breakdown(term_f, year_f, college_f):
    with engine.connect() as conn:
        df = pd.read_sql(
            text("""
                SELECT s.college AS "College", COUNT(DISTINCT s.id) AS "Students",
                    COALESCE(SUM(CASE WHEN t.transaction_type IN ('Invoice','Bulk Invoices (Tuition)') THEN t.debit ELSE 0 END),0) AS "Tuition Billed (EGP)",
                    COALESCE(SUM(CASE WHEN t.transaction_type IN ('Discount','Bulk Scholarships') THEN t.credit-t.debit ELSE 0 END),0) AS "Discounts (EGP)",
                    COALESCE(SUM(CASE WHEN t.transaction_type IN ('Payment Receipt','Bulk Payments') THEN t.credit ELSE 0 END),0) AS "Payments (EGP)",
                    COALESCE(SUM(t.debit)-SUM(t.credit),0) AS "Net Balance (EGP)"
                FROM students s LEFT JOIN transactions t ON s.id=t.student_id
                    AND (:tf='All Terms' OR t.term=:tf)
                    AND (:yf='All Years' OR t.academic_year=:yv)
                WHERE (:cf='All Colleges' OR s.college=:cf)
                    AND COALESCE((SELECT status FROM student_statuses WHERE student_id=s.id ORDER BY id DESC LIMIT 1),'Not Set') != 'Test'
                GROUP BY s.college ORDER BY s.college
            """),
            con=conn, # بنستخدم الـ connection الآمن هنا
            params={"tf": term_f, "yf": year_f,
                    "yv": int(year_f) if year_f != "All Years" else 0,
                    "cf": college_f},
        )
    return df


def render(engine_param, available_years):
    # إضافة زر لتحديث البيانات (مسح الكاش)
    c_head, c_btn = st.columns([4, 1])
    c_head.subheader("📊 Financial Dashboard")
    if c_btn.button("🔄 Refresh Data", help="Fetch the latest live data from the database"):
        st.cache_data.clear()
        st.rerun()
        
    f1, f2, f3 = st.columns(3)
    term_f    = f1.selectbox("Filter by Term:",    ["All Terms"]    + VALID_TERMS,    key="dash_term")
    year_f    = f2.selectbox("Filter by Year:",    ["All Years"]    + [str(y) for y in available_years], key="dash_year")
    college_f = f3.selectbox("Filter by College:", ["All Colleges"] + VALID_COLLEGES, key="dash_college")
    st.markdown("<br>", unsafe_allow_html=True)

    # جلب البيانات من الدالة المخبأة (سريعة جداً)
    metrics = fetch_dashboard_metrics(term_f, year_f, college_f)

    # ── KPI row 1 ──
    st.markdown("### 💰 Financial Summary")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    cards = [
        (kpi1, "#1a73e8", "#0d47a1", "📈 Gross Billed",        metrics["gross_billed"]),
        (kpi2, "#e53935", "#b71c1c", "🎓 Total Scholarships",  metrics["total_discounts"]),
        (kpi3, "#00897b", "#004d40", "💳 Total Payments",        metrics["total_payments"]),
        (kpi4, "#fb8c00" if metrics["net_adjustments"] >= 0 else "#757575",
               "#e65100" if metrics["net_adjustments"] >= 0 else "#424242",
               "⚙️ Net Adjustments", metrics["net_adjustments"]),
    ]
    for col, c1, c2, label, val in cards:
        with col:
            st.markdown(
                f'<div style="background:linear-gradient(135deg,{c1},{c2});padding:15px;'
                f'border-radius:12px;color:white;height:110px;">'
                f'<p style="margin:0;font-size:14px;opacity:.85;">{label}</p>'
                f'<h3 style="margin:5px 0 0;font-size:22px;">{val:,.0f}</h3></div>',
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── KPI row 2 ──
    kpi5, kpi6, kpi7 = st.columns(3)
    bal_c  = ("#2e7d32","#1b5e20") if metrics["net_balance"] >= 0 else ("#b71c1c","#7f0000")
    cards2 = [
        (kpi5, bal_c[0], bal_c[1], "⚖️ Net Balance Due",  f"{metrics['net_balance']:,.0f} EGP"),
        (kpi6, "#5e35b1", "#311b92", "👥 Total Students",  f"{metrics['total_students']:,}"),
        (kpi7, "#f57c00", "#e65100", "✅ Active Students", f"{metrics['active_count']:,}"),
    ]
    for col, c1, c2, label, val in cards2:
        with col:
            st.markdown(
                f'<div style="background:linear-gradient(135deg,{c1},{c2});padding:20px;'
                f'border-radius:12px;color:white;height:120px;">'
                f'<p style="margin:0;font-size:16px;opacity:.85;">{label}</p>'
                f'<h2 style="margin:8px 0 0;font-size:28px;">{val}</h2></div>',
                unsafe_allow_html=True,
            )
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 📋 Revenue Breakdown by College")

    # 🟢 التعديل: استدعاء الدالة بدون ما نبعتلها الـ engine_str
    df = fetch_college_breakdown(term_f, year_f, college_f)

    if not df.empty:
        totals = {c: df[c].sum() if df[c].dtype != object else ("🔢 TOTAL" if c=="College" else "") for c in df.columns}
        totals["College"] = "🔢 TOTAL"
        df_show = pd.concat([df, pd.DataFrame([totals])], ignore_index=True)
        fmt = {c: "{:,.2f}" for c in ["Tuition Billed (EGP)","Discounts (EGP)","Payments (EGP)","Net Balance (EGP)"]}
        st.dataframe(
            df_show.style.format(fmt)
                .map(highlight_negatives, subset=["Net Balance (EGP)"])
                .apply(lambda x: ["font-weight:bold;background:#f0f4ff" if x.name==len(df_show)-1 else "" for _ in x], axis=1),
            use_container_width=True, hide_index=True,
        )
        buf = io.BytesIO()
        df.to_excel(buf, index=False)
        st.download_button("📗 Download College Report (Excel)", buf.getvalue(),
                           file_name=f"Dashboard_Report.xlsx")
    else:
        st.info("⚠️ No financial data found for the selected filters.")

    if metrics["gross_billed"] > 0:
        st.markdown("---\n### 📐 Key Ratios")
        r1, r2 = st.columns(2)
        r1.metric("🎓 Discount Rate",    f"{metrics['total_discounts']/metrics['gross_billed']*100:.1f}%", f"{metrics['total_discounts']:,.0f} EGP")
        r2.metric("💳 Collection Rate",  f"{metrics['total_payments']/metrics['gross_billed']*100:.1f}%",  f"{metrics['total_payments']:,.0f} EGP")
