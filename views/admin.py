# views/admin.py
import io
import streamlit as st

from config import VALID_ROLES
from auth import require_role, hash_pw
from models import get_db, SystemUser, Student, AuditLog
from sqlalchemy.sql import func
import pandas as pd
from datetime import datetime


def render():
    st.subheader("⚙️ System Administration")
    require_role("Admin")

    action = st.radio(
        "Action:",
        ["👥 Manage Users", "➕ Add New User", "🛠️ Database Fixes", "📋 Audit Log"],
        horizontal=True,
    )

    with get_db() as db:

        if action == "👥 Manage Users":
            users = db.query(SystemUser).order_by(SystemUser.id).all()
            for u in users:
                label = f"👤 {u.username} — {u.role} — {'🟢 Active' if u.is_active else '🔴 Disabled'}"
                with st.expander(label):
                    with st.form(f"edit_user_{u.id}"):
                        c1, c2, c3 = st.columns(3)
                        new_role   = c1.selectbox("Role",   VALID_ROLES,
                                                  index=VALID_ROLES.index(u.role) if u.role in VALID_ROLES else 1,
                                                  key=f"role_{u.id}")
                        new_active = c2.checkbox("Active", value=u.is_active, key=f"act_{u.id}")
                        new_pwd    = c3.text_input("New Password (blank = no change)",
                                                   type="password", key=f"pwd_{u.id}")
                        if st.form_submit_button("💾 Save"):
                            if new_pwd:
                                u.password_hash = hash_pw(new_pwd)
                            u.role, u.is_active = new_role, new_active
                            db.commit()
                            st.success(f"'{u.username}' updated.")
                            st.rerun()

        elif action == "➕ Add New User":
            with st.form("add_user_form"):
                c1, c2 = st.columns(2)
                n_user = c1.text_input("Username *")
                n_pwd  = c2.text_input("Password *", type="password")
                n_role = st.selectbox("Role *", VALID_ROLES, index=1)
                if st.form_submit_button("🚀 Create User"):
                    if not n_user or not n_pwd:
                        st.error("Username and password are required.")
                    elif db.query(SystemUser).filter(
                        func.lower(SystemUser.username) == n_user.lower().strip()
                    ).first():
                        st.error("Username already exists (case-insensitive).")
                    else:
                        db.add(SystemUser(
                            username      = n_user.strip(),
                            password_hash = hash_pw(n_pwd),
                            role          = n_role,
                            is_active     = True,
                        ))
                        db.commit()
                        st.session_state["flash_msg"] = f"User '{n_user}' created."
                        st.rerun()

        elif action == "🛠️ Database Fixes":
            st.markdown("### 🧹 College Name Normalisation")
            st.write("Strips whitespace and uppercases all college codes in the students table.")
            if st.button("🚀 Run Fix", type="primary"):
                fixed = 0
                for s in db.query(Student).all():
                    clean = s.college.strip().upper() if s.college else s.college
                    if clean != s.college:
                        s.college = clean
                        fixed += 1
                db.commit()
                if fixed:
                    st.success(f"✅ Fixed {fixed} records.")
                else:
                    st.success("✅ No issues found — database is clean.")

            st.markdown("---\n### 🔢 Scholarship Percentage Normalisation")
            st.write("Converts any percentage stored as a decimal (0.60 → 60.0) to 0–100 format.")
            if st.button("🔄 Normalise Percentages"):
                fixed = 0
                from models import StudentScholarship
                for ss in db.query(StudentScholarship).all():
                    if ss.percentage <= 1.0:
                        ss.percentage = round(ss.percentage * 100.0, 4)
                        fixed += 1
                db.commit()
                st.success(f"✅ Converted {fixed} scholarship record(s).")

            # ---------------------------------------------------------
            # الأداة المُحسنة: الدفعات السريعة (Bulk Update in Chunks)
            # ---------------------------------------------------------
            st.markdown("---\n### 🛠️ Bulk Update: Financial Dimensions (D365)")
            st.write("Download the verified Excel template, fill your data, and upload it back to sync with Supabase.")
            
            sample_data = {
                "ID": [211000224, 211001595],
                "Dimension": [
                    "Academic||||||||EAS (AC02)|Civil and Infrastructure|211000224|Spring|",
                    "Academic||||||||BA (AC02)|General Business|211001595|Fall|"
                ]
            }
            df_sample = pd.DataFrame(sample_data)
            
            template_buffer = io.BytesIO()
            with pd.ExcelWriter(template_buffer, engine='openpyxl') as writer:
                df_sample.to_excel(writer, index=False, sheet_name='D365_Template')
            
            st.download_button(
                label="📥 Download Verified Excel Template",
                data=template_buffer.getvalue(),
                file_name="D365_Students_Dimensions_Template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            st.markdown("<br>", unsafe_allow_html=True)
            dim_file = st.file_uploader("Upload Completed Dimensions Excel", type=['xlsx'], key="dim_uploader")
            
            if dim_file and st.button("🚀 Update Students Dimensions", type="primary"):
                with st.spinner("Processing template and syncing with Supabase in chunks..."):
                    try:
                        df_dims = pd.read_excel(dim_file, engine='openpyxl')
                        
                        if 'ID' not in df_dims.columns or 'Dimension' not in df_dims.columns:
                            st.error("⚠️ Validation Error: The uploaded file must contain exactly two columns named 'ID' and 'Dimension'.")
                        else:
                            update_list = []
                            for index, row in df_dims.iterrows():
                                if pd.isna(row['ID']) or pd.isna(row['Dimension']):
                                    continue
                                    
                                student_id = int(row['ID'])
                                dimension_val = str(row['Dimension']).strip()
                                
                                if student_id > 0 and dimension_val and dimension_val.lower() != 'nan':
                                    # نجمع الداتا المطلوبة في قائمة بدل التحديث الفردي
                                    update_list.append({
                                        "id": student_id,
                                        "financial_dimension": dimension_val
                                    })
                            
                            if update_list:
                                # تقسيم التحديثات لـ Chunks (كل 500 طالب في خبطة واحدة)
                                chunk_size = 500
                                for i in range(0, len(update_list), chunk_size):
                                    chunk = update_list[i:i+chunk_size]
                                    db.bulk_update_mappings(Student, chunk)
                                    db.commit() # نأكد الحفظ لكل 500 لتجنب الـ Timeout
                                
                                st.success(f"✅ Successfully updated financial dimensions for {len(update_list)} students!")
                            else:
                                st.warning("⚠️ No valid data found in the uploaded file.")
                                
                    except Exception as e:
                        db.rollback()
                        st.error("⚠️ Execution Error: Failed to parse or sync the Excel file.")
                        st.exception(e)

        elif action == "📋 Audit Log":
            st.markdown("### 📋 Recent System Activity (last 500 entries)")
            logs = (
                db.query(AuditLog)
                .order_by(AuditLog.created_at.desc())
                .limit(500)
                .all()
            )
            if logs:
                df = pd.DataFrame([{
                    "Time":    l.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "User":    l.username,
                    "Action":  l.action,
                    "Target":  l.target,
                    "Detail":  l.detail,
                } for l in logs])
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No audit entries yet.")
