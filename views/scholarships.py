# pages/scholarships.py
import io
from datetime import datetime
import pandas as pd
import streamlit as st
from sqlalchemy import text

from config import VALID_TERMS, DEFAULT_YEAR
from auth import require_role
from models import (
    get_db, Student, StudentScholarship, ScholarshipType,
    next_ref_block, write_audit,
)
from helpers import (
    get_student_scholarships, get_retroactive_scholarship_tx,
    enforce_scholarship_cap, _pct,
)


def render(engine):
    st.subheader("🎓 Student Scholarships Management")
    require_role("Admin", "Editor")

    sch_map = st.session_state.get("_sch_map", {})

    action = st.radio(
        "Action:",
        ["View / Edit", "Add Scholarship", "Bulk Upload Scholarships",
         "🔄 Sync & Recalculate", "📊 Scholarships Report"],
        horizontal=True,
    )

    # ── VIEW / EDIT ──
    if action == "View / Edit":
        with st.form("sch_lookup_form", clear_on_submit=False):
            raw = st.text_input("Student ID:", placeholder="e.g. 26100123")
            c1, c2 = st.columns(2)
            s_term = c1.selectbox("Term:", VALID_TERMS)
            s_year = c2.number_input("Year:", value=DEFAULT_YEAR, step=1)
            if st.form_submit_button("🔍 Load"):
                st.session_state["sch_params"] = {
                    "sid": int(raw) if raw.strip().isdigit() else 0,
                    "term": s_term, "year": int(s_year),
                }

        p = st.session_state.get("sch_params")
        if not p or p["sid"] <= 0:
            return

        with get_db() as db:
            student = db.get(Student, p["sid"])
            if not student:
                st.warning("Student not found.")
                return
            st.info(f"**{student.name}** — {p['term']} {p['year']}")

            rows = (
                db.query(StudentScholarship, ScholarshipType)
                .join(ScholarshipType)
                .filter(StudentScholarship.student_id    == p["sid"],
                        StudentScholarship.term          == p["term"],
                        StudentScholarship.academic_year == p["year"])
                .all()
            )
            if not rows:
                st.info("No scholarships for this term.")
                return

            for ss, st_type in rows:
                pct_disp = _pct(ss.percentage)
                c1, c2, c3 = st.columns([4, 2, 2])
                c1.write(f"**{st_type.name}**")
                c2.write(f"{pct_disp:.1f}%")
                c3.write("✅ Active" if ss.is_active else "🔴 Inactive")

                with st.expander(f"⚙️ Manage '{st_type.name}'"):
                    if ss.is_active:
                        if st.button("Stop (future only)", key=f"stop_{ss.id}"):
                            ss.is_active = False
                            db.commit()
                            st.rerun()
                        if st.session_state.get("user_role") == "Admin":
                            if st.checkbox(f"Confirm reverse {st_type.name}", key=f"chk_{ss.id}"):
                                if st.button("Stop & Reverse Past Discounts", key=f"rev_{ss.id}"):
                                    ss.is_active = False
                                    db.commit()
                                    seq = next_ref_block(db, 1)
                                    r_tx = get_retroactive_scholarship_tx(
                                        db, p["sid"], p["term"], p["year"],
                                        ss.scholarship_type_id, st_type.name, 0.0, seq,
                                    )
                                    if r_tx:
                                        db.add(r_tx)
                                        db.commit()
                                    st.rerun()
                    else:
                        if st.button("Activate", key=f"act_{ss.id}"):
                            ss.is_active = True
                            db.commit()
                            enforce_scholarship_cap(db, p["sid"], p["term"], p["year"])
                            db.commit()
                            still_active = db.query(StudentScholarship.is_active).filter_by(id=ss.id).scalar()
                            if still_active:
                                seq  = next_ref_block(db, 1)
                                r_tx = get_retroactive_scholarship_tx(
                                    db, p["sid"], p["term"], p["year"],
                                    ss.scholarship_type_id, st_type.name, _pct(ss.percentage), seq,
                                )
                                if r_tx:
                                    db.add(r_tx)
                                    db.commit()
                            st.rerun()

    # ── ADD SINGLE ──
    elif action == "Add Scholarship":
        # 🟢 شلنا الـ st.form من هنا عشان القائمة تسمع وتظهر الخانة في نفس اللحظة
        st.markdown("#### Assign New Scholarship")
        
        c1, c2, c3 = st.columns(3)
        add_sid  = c1.number_input("Student ID:",placeholder="e.g 251000120", step=1)
        add_term = c2.selectbox("Term:", VALID_TERMS)
        add_year = c3.number_input("Year:", value=DEFAULT_YEAR, step=1)
        add_type = st.selectbox("Scholarship Type:", list(sch_map.keys()) or ["—"])
        add_pct  = st.number_input("Percentage (0–100):", min_value=0.0, max_value=100.0, step=5.0)
        
        # 🟢 حقل مخفي لمعالجة شرط الأخوات (هيشتغل لايف دلوقتي)
        sibling_id_input = ""
        if add_type == "SCH: Sibiling %":
            sibling_id_input = st.text_input("⚠️ Enter Sibling ID (Required)", placeholder="e.g. 25100999")
            
        if st.button("➕ Add Scholarship", type="primary"):
            with get_db() as db:
                student = db.get(Student, int(add_sid))
                if not student:
                    st.error("Student not found.")
                elif add_type not in sch_map:
                    st.error("Invalid scholarship type.")
                # التحقق من خصم الأخوات
                elif add_type == "SCH: Sibiling %" and not sibling_id_input.strip().isdigit():
                    st.error("🛑 Sibling ID is REQUIRED when applying 'SCH: Sibiling %'.")
                else:
                    # تحديث بيانات الطالب إذا تم إدخال رقم الأخ
                    if add_type == "SCH: Sibiling %" and not student.sibling_id:
                        student.sibling_id = int(sibling_id_input.strip())
                        
                    s_type_id = sch_map[add_type]
                    existing  = db.query(StudentScholarship).filter_by(
                        student_id=int(add_sid), scholarship_type_id=s_type_id,
                        term=add_term, academic_year=int(add_year)).first()
                    if existing:
                        existing.percentage, existing.is_active = add_pct, True
                    else:
                        db.add(StudentScholarship(
                            student_id=int(add_sid), scholarship_type_id=s_type_id,
                            percentage=add_pct, term=add_term,
                            academic_year=int(add_year), is_active=True,
                        ))
                    enforce_scholarship_cap(db, int(add_sid), add_term, int(add_year))
                    db.commit()
                    still_active = db.query(StudentScholarship.is_active).filter_by(
                        student_id=int(add_sid), scholarship_type_id=s_type_id,
                        term=add_term, academic_year=int(add_year)).scalar()
                    if still_active:
                        seq  = next_ref_block(db, 1)
                        r_tx = get_retroactive_scholarship_tx(
                            db, int(add_sid), add_term, int(add_year),
                            s_type_id, add_type, add_pct, seq,
                        )
                        if r_tx:
                            db.add(r_tx)
                    write_audit(db, st.session_state["logged_in_user"],
                                "ADD_SCHOLARSHIP", f"student_id={add_sid}",
                                f"{add_type} {add_pct}% {add_term} {int(add_year)}")
                    db.commit()
                    st.session_state["flash_msg"] = "Scholarship added/updated!"
                    st.rerun()

    # ── BULK UPLOAD ──
    elif action == "Bulk Upload Scholarships":
        st.info("💡 Scholarship Name must exactly match the type name in the system.")
        tpl = {"Student ID":26100123,"Scholarship Name":list(sch_map.keys())[0] if sch_map else "SCH","Percentage":60.0,"Term":"Spring","Academic Year":DEFAULT_YEAR}
        buf = io.BytesIO()
        pd.DataFrame([tpl]).to_excel(buf, index=False)
        st.download_button("📥 Download Template", buf.getvalue(), file_name="Template_Scholarships.xlsx")

        upl = st.file_uploader("Upload Scholarships Excel", type=["xlsx"])
        if upl and st.button("🚀 Upload"):
            df_sch = pd.read_excel(upl)
            df_sch.columns = [str(c).strip() for c in df_sch.columns]
            with get_db() as db:
                valid_ids = {s[0] for s in db.query(StudentScholarship.student_id.distinct()).all()} \
                          | {s[0] for s in db.query(Student.id).all()}
                uploaded_data, failed, combos = [], [], set()
                for _, row in df_sch.iterrows():
                    sid      = int(row.get("Student ID",0)) if pd.notnull(row.get("Student ID")) else 0
                    s_name   = str(row.get("Scholarship Name","")).strip()
                    pct      = float(row.get("Percentage",0))
                    trm      = str(row.get("Term", VALID_TERMS[1])).strip()
                    yr       = int(row.get("Academic Year", DEFAULT_YEAR))
                    s_type_id= sch_map.get(s_name)
                    
                    if sid <= 0 or sid not in valid_ids or not s_type_id or pct <= 0:
                        failed.append(row.to_dict())
                        continue
                        
                    ex = db.query(StudentScholarship).filter_by(
                        student_id=sid, scholarship_type_id=s_type_id, term=trm, academic_year=yr).first()
                    if ex:
                        ex.percentage, ex.is_active = pct, True
                    else:
                        db.add(StudentScholarship(student_id=sid, scholarship_type_id=s_type_id,
                                                  percentage=pct, term=trm, academic_year=yr, is_active=True))
                    uploaded_data.append((sid, s_type_id, s_name, pct, trm, yr))
                    combos.add((sid, trm, yr))

                db.commit()
                for sid_, trm_, yr_ in combos:
                    enforce_scholarship_cap(db, sid_, trm_, yr_)
                db.commit()

                batch_id = f"BCH-SCH-{datetime.now().strftime('%y%m%d-%H%M%S')}"
                retro, curr = [], next_ref_block(db, len(uploaded_data)+1)
                for sid_, s_type_id_, s_name_, pct_, trm_, yr_ in uploaded_data:
                    still = db.query(StudentScholarship.is_active).filter_by(
                        student_id=sid_, scholarship_type_id=s_type_id_, term=trm_, academic_year=yr_).scalar()
                    if still:
                        r_tx = get_retroactive_scholarship_tx(
                            db, sid_, trm_, yr_, s_type_id_, s_name_, pct_, curr, batch_id)
                        if r_tx:
                            retro.append(r_tx)
                            curr += 1
                if retro:
                    db.bulk_save_objects(retro)
                db.commit()
                st.success(f"✅ Done! Added/updated {len(uploaded_data)} | Retroactive: {len(retro)}")
                if failed:
                    st.error(f"⚠️ {len(failed)} failed.")
                    st.dataframe(pd.DataFrame(failed))

    # ── SYNC ──
    elif action == "🔄 Sync & Recalculate":
        st.info("Scan a term and apply any missing retroactive discounts.")
        with st.form("sync_form"):
            sc1, sc2 = st.columns(2)
            r_term = sc1.selectbox("Term:", VALID_TERMS)
            r_year = sc2.number_input("Year:", value=DEFAULT_YEAR, step=1)
            if st.form_submit_button("🚀 Run Sync"):
                with get_db() as db:
                    active_schs = (
                        db.query(StudentScholarship, ScholarshipType)
                        .join(ScholarshipType)
                        .filter(StudentScholarship.term          == r_term,
                                StudentScholarship.academic_year == int(r_year),
                                StudentScholarship.is_active     == True)
                        .all()
                    )
                    if not active_schs:
                        st.warning("No active scholarships found for this term.")
                    else:
                        batch_id = f"BCH-SYNC-{datetime.now().strftime('%y%m%d-%H%M%S')}"
                        curr     = next_ref_block(db, len(active_schs)+1)
                        retro    = []
                        for ss, st_type in active_schs:
                            r_tx = get_retroactive_scholarship_tx(
                                db, ss.student_id, r_term, int(r_year),
                                ss.scholarship_type_id, st_type.name,
                                _pct(ss.percentage), curr, batch_id,
                            )
                            if r_tx:
                                retro.append(r_tx)
                                curr += 1
                        if retro:
                            db.bulk_save_objects(retro)
                            db.commit()
                            st.success(f"✅ Applied {len(retro)} missing discount(s).")
                        else:
                            st.success("✅ All discounts are already aligned.")

    # ── REPORT ──
    elif action == "📊 Scholarships Report":
        if st.button("📂 Generate Report"):
            sql = text("""
                SELECT s.id AS "Student ID", s.name AS "Student Name", s.college AS "College",
                    ss.term AS "Term", ss.academic_year AS "Year", st.name AS "Scholarship Name",
                    ss.percentage AS "Configured %",
                    CASE WHEN ss.is_active THEN 'Active' ELSE 'Inactive' END AS "Status",
                    COALESCE((SELECT SUM(t.debit-t.credit) FROM transactions t
                              WHERE t.student_id=s.id AND t.term=ss.term AND t.academic_year=ss.academic_year
                              AND t.transaction_type IN ('Invoice','Bulk Invoices (Tuition)','Credit Hours Adjustment','Credit Hours Adjustments')),0) AS "Tuition Billed (EGP)",
                    COALESCE((SELECT SUM(t.credit-t.debit) FROM transactions t
                              WHERE t.student_id=s.id AND t.term=ss.term AND t.academic_year=ss.academic_year
                              AND t.reference_no LIKE 'SCH-%' AND t.scholarship_type_id=ss.scholarship_type_id),0) AS "Actual Discount (EGP)"
                FROM student_scholarships ss
                JOIN students s  ON ss.student_id=s.id
                JOIN scholarship_types st ON ss.scholarship_type_id=st.id
                ORDER BY ss.academic_year DESC, ss.term, s.id
            """)
            with get_db() as db:
                df = pd.read_sql(sql, con=engine)
            if df.empty:
                st.info("No scholarships configured yet.")
            else:
                st.dataframe(df.style.format({"Configured %":"{:.1f}","Tuition Billed (EGP)":"{:,.2f}","Actual Discount (EGP)":"{:,.2f}"}), use_container_width=True)
                buf = io.BytesIO()
                df.to_excel(buf, index=False)
                st.download_button("📗 Download Excel", buf.getvalue(), file_name="Scholarships_Report.xlsx")
