# pages/lookup.py
import io
import streamlit as st
import pandas as pd

from config import VALID_TERMS, VALID_STATUSES, VALID_COLLEGES, DEFAULT_YEAR
from auth import require_role
from models import get_db, Student, StudentStatus, StudentScholarship, ScholarshipType, write_audit

STATUS_COLORS = {
    "Active":           "background:#d4edda;color:#155724;font-weight:bold;border-radius:5px;",
    "Semester Withdraw":"background:#fff3cd;color:#856404;font-weight:bold;border-radius:5px;",
    "Inactive":         "background:#f8d7da;color:#721c24;font-weight:bold;border-radius:5px;",
    "Graduated":        "background:#d1ecf1;color:#0c5460;font-weight:bold;border-radius:5px;",
    "Program Withdraw": "background:#e2e3e5;color:#383d41;font-weight:bold;border-radius:5px;",
}

# 🟢 دالة سريعة مكيشة لتوليد شيت إكسيل لكل الطلاب
@st.cache_data(ttl=300)
def get_all_students_excel():
    with get_db() as db:
        all_students = db.query(Student).all()
        if not all_students:
            return None
        df_all = pd.DataFrame([{
            "Student ID": s.id, "Name": s.name, "College": s.college, "Program": s.program,
            "Email": s.email, "Mobile": s.mobile, "National ID": s.national_id,
            "Nationality": s.nationality, "Admit Year": s.admit_year,
            "Price / Hr (EGP)": s.price_per_hr, "Is Sponsored": s.is_sponsored,
            "Sponsor Name": s.sponsor_name, "Sibling ID": s.sibling_id,
            "General Notes": s.general_notes
        } for s in all_students])
        buf = io.BytesIO()
        df_all.to_excel(buf, index=False)
        return buf.getvalue()


def render():
    c_head, c_btn = st.columns([3, 1])
    c_head.subheader("🔍 Student Data Explorer")
    
    # 🟢 زرار تنزيل بيانات كل الطلاب
    all_excel_data = get_all_students_excel()
    if all_excel_data:
        c_btn.download_button("📥 Download All Students", all_excel_data, file_name="All_Students_Master_Data.xlsx", type="primary", use_container_width=True)

    with st.form("lookup_form", clear_on_submit=False):
        default = str(st.session_state.get("lookup_id","")) if st.session_state.get("lookup_id",0)>0 else ""
        sid_raw   = st.text_input("Student ID:", value=default, placeholder="e.g. 26100123")
        submitted = st.form_submit_button("🔍 Lookup Profile")
        
    if submitted:
        st.session_state["lookup_id"] = int(sid_raw) if sid_raw.strip().isdigit() else 0

    sid = st.session_state.get("lookup_id", 0)
    if sid <= 0:
        return

    with get_db() as db:
        student = db.get(Student, sid)
        if not student:
            st.warning("⚠️ No student found with this ID.")
            return

        # 🟢 تجهيز شيت إكسيل مخصص للطالب الحالي فقط
        df_single = pd.DataFrame([{
            "Student ID": student.id, "Name": student.name, "College": student.college, "Program": student.program,
            "Email": student.email, "Mobile": student.mobile, "National ID": student.national_id,
            "Nationality": student.nationality, "Admit Year": student.admit_year,
            "Price / Hr (EGP)": student.price_per_hr, "Is Sponsored": student.is_sponsored,
            "Sponsor Name": student.sponsor_name, "Sibling ID": student.sibling_id,
            "General Notes": student.general_notes
        }])
        buf_single = io.BytesIO()
        df_single.to_excel(buf_single, index=False)

        # عرض الترويسة وزرار تنزيل بروفايل الطالب
        c_prof1, c_prof2 = st.columns([3, 1])
        c_prof1.info(f"✅ Profile: **{student.name}**")
        c_prof2.download_button("📥 Export Profile", buf_single.getvalue(), file_name=f"Student_{student.id}_Profile.xlsx", type="primary" ,use_container_width=True)

        c1, c2, c3 = st.columns(3)
        c1.metric("College",        student.college or "—")
        c2.metric("Program",        student.program or "—")
        c3.metric("Price / Credit Hour", f"{student.price_per_hr:,.2f} EGP" if student.price_per_hr else "—")

        with st.expander("📝 Full Personal Details", expanded=True):
            l, r = st.columns(2)
            l.write(f"**Email:** {student.email}")
            l.write(f"**Mobile:** {student.mobile}")
            l.write(f"**Admit Year:** {student.admit_year}")
            r.write(f"**National ID:** {student.national_id}")
            r.write(f"**Nationality:** {student.nationality}")
            r.write(f"**Birth Date:** {student.birth_date}")
            
            st.markdown("---")
            sl, sr = st.columns(2)
            if student.is_sponsored:
                sl.success(f"🤝 **Sponsored Student** (By: {student.sponsor_name})")
            else:
                sl.write("**Sponsorship:** None")
                
            if student.sibling_id:
                sr.info(f"👨‍👩‍👧 **Sibling ID:** {student.sibling_id}")
            else:
                sr.write("**Sibling ID:** None")
                
            if student.general_notes:
                st.warning(f"📌 **General Notes:** {student.general_notes}")

        # ── Academic status ──
        st.markdown("---\n### 📌 Academic Status")
        statuses = (
            db.query(StudentStatus)
            .filter_by(student_id=sid)
            .order_by(StudentStatus.academic_year.desc())
            .all()
        )
        if statuses:
            df_s = pd.DataFrame([{"Term": s.term, "Year": s.academic_year, "Status": s.status} for s in statuses])
            st.dataframe(
                df_s.style.map(lambda v: STATUS_COLORS.get(v,""), subset=["Status"]),
                use_container_width=True, hide_index=True,
            )
        else:
            st.info("No status history yet.")

        with st.expander("⚙️ Update / Add Status"):
            with st.form("status_form"):
                sc1, sc2, sc3 = st.columns(3)
                s_term  = sc1.selectbox("Term:",  VALID_TERMS)
                s_year  = sc2.number_input("Year:", value=DEFAULT_YEAR, step=1)
                s_value = sc3.selectbox("Status:", VALID_STATUSES)
                if st.form_submit_button("💾 Save Status"):
                    existing = db.query(StudentStatus).filter_by(
                        student_id=sid, term=s_term, academic_year=s_year).first()
                    if existing:
                        existing.status = s_value
                    else:
                        db.add(StudentStatus(student_id=sid, term=s_term,
                                             academic_year=int(s_year), status=s_value))
                    write_audit(db, st.session_state["logged_in_user"],
                                "UPDATE_STATUS", f"student_id={sid}",
                                f"{s_term} {s_year} → {s_value}")
                    db.commit()
                    st.session_state["flash_msg"] = f"Status set to {s_value} for {s_term} {int(s_year)}."
                    st.rerun()

        # ── Scholarships overview ──
        with st.expander("🎓 Scholarships (All Terms)"):
            all_schs = (
                db.query(StudentScholarship, ScholarshipType)
                .join(ScholarshipType)
                .filter(StudentScholarship.student_id == sid)
                .order_by(StudentScholarship.academic_year.desc())
                .all()
            )
            if all_schs:
                df_sch = pd.DataFrame([{
                    "Term": ss.term, "Year": ss.academic_year,
                    "Scholarship": st_type.name,
                    "Percentage": f"{ss.percentage:.1f}%",
                    "Status": "✅ Active" if ss.is_active else "❌ Inactive",
                } for ss, st_type in all_schs])
                st.dataframe(df_sch, use_container_width=True, hide_index=True)
            else:
                st.info("No scholarships found.")

        # ── Edit master data ──
        if st.session_state.get("user_role") in ["Admin", "Editor"]:
            st.markdown("---")
            if st.toggle("🔓 Unlock Edit Mode"):
                st.warning("⚠️ You are modifying master student data.")
                
                with st.form("edit_master_data_form"):
                    e1, e2, e3 = st.columns(3)
                    e_name    = e1.text_input("Full Name",  value=student.name or "")
                    try:    col_idx = VALID_COLLEGES.index(str(student.college).strip().upper())
                    except: col_idx = 0
                    e_college = e2.selectbox("College", VALID_COLLEGES, index=col_idx)
                    e_price   = e3.number_input("Price/Hr (EGP)", value=float(student.price_per_hr or 0), step=100.0)
                    
                    e4, e5, e6 = st.columns(3)
                    e_email   = e4.text_input("Email",   value=student.email   or "")
                    e_mobile  = e5.text_input("Mobile",  value=student.mobile  or "")
                    e_program = e6.text_input("Program", value=student.program or "")
                    
                    st.markdown("#### 💼 Additional Data (Sponsorship & Notes)")
                    c_s1, c_s2, c_s3 = st.columns([1, 2, 1])
                    e_is_sponsored = c_s1.checkbox("Is Sponsored?", value=student.is_sponsored)
                    e_sponsor_name = c_s2.text_input("Sponsor Name", value=student.sponsor_name or "", placeholder="e.g. MISR El Kheir")
                    e_sibling_id_raw = c_s3.text_input("Sibling ID (Optional)", value=str(student.sibling_id) if student.sibling_id else "")
                    
                    e_notes = st.text_area("General Notes (Internal use)", value=student.general_notes or "", placeholder="Add any specific conditions, notes or instructions regarding this student...")

                    if st.form_submit_button("💾 Save Changes", type="primary"):
                        try:
                            sib_id = None
                            if e_sibling_id_raw and e_sibling_id_raw.strip().isdigit():
                                sib_id = int(e_sibling_id_raw.strip())
                                
                            student.name, student.college, student.price_per_hr = e_name, e_college, e_price
                            student.email, student.mobile, student.program       = e_email, e_mobile, e_program
                            
                            student.is_sponsored = e_is_sponsored
                            student.sponsor_name = e_sponsor_name if e_is_sponsored else None
                            student.general_notes = e_notes
                            student.sibling_id = sib_id
                            
                            write_audit(db, st.session_state["logged_in_user"],
                                        "EDIT_STUDENT", f"student_id={sid}", "Master data & Notes updated")
                            db.commit()
                            
                            # مسح الكاش عشان الداتا الجديدة تظهر لو اليوزر نزل شيت الماستر تاني
                            st.cache_data.clear() 
                            st.session_state["flash_msg"] = "Student data updated successfully!"
                            st.rerun()
                        except Exception as e:
                            db.rollback()
                            st.error(f"Save failed. Error: {str(e)}")
