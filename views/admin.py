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
        ["👥 Manage Users", "➕ Add New User", "🛠️ Database Fixes", "⚙️ System Settings", "📋 Audit Log"],
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
                            st.toast(f"'{u.username}' updated.", icon="✅")
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
                    st.toast(f"✅ Fixed {fixed} records.", icon="✅")
                else:
                    st.toast("✅ No issues found — database is clean.", icon="✅")

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
                st.toast(f"✅ Converted {fixed} scholarship record(s).", icon="✅")

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
                                
                                st.toast(f"✅ Successfully updated financial dimensions for {len(update_list)} students!", icon="✅")
                            else:
                                st.warning("⚠️ No valid data found in the uploaded file.")
                                
                    except Exception as e:
                        db.rollback()
                        st.error("⚠️ Execution Error: Failed to parse or sync the Excel file.")
                        st.exception(e)

        elif action == "⚙️ System Settings":
            st.markdown("### ⚙️ System Settings & Configurations")
            st.write("Dynamic system parameters (changes reflect instantly throughout the system).")
            
            from models import SystemConfig
            
            # Load current DB configurations
            keys = ["VALID_TERMS", "VALID_STATUSES", "VALID_COLLEGES", "VALID_ROLES", "DEFAULT_YEAR"]
            current_vals = {}
            for k in keys:
                row = db.query(SystemConfig).filter_by(key=k).first()
                current_vals[k] = row.value if row else ""
            
            with st.form("system_settings_form"):
                colleges_input = st.text_input("Valid Colleges (comma-separated)", value=current_vals.get("VALID_COLLEGES", ""))
                terms_input = st.text_input("Valid Terms (comma-separated)", value=current_vals.get("VALID_TERMS", ""))
                statuses_input = st.text_area("Valid Student Statuses (comma-separated)", value=current_vals.get("VALID_STATUSES", ""), height=100)
                roles_input = st.text_input("Valid Roles (comma-separated)", value=current_vals.get("VALID_ROLES", ""))
                year_input = st.number_input("Default Academic Year", value=int(current_vals.get("DEFAULT_YEAR", 2026)), step=1)
                
                if st.form_submit_button("💾 Save System Configurations", type="primary"):
                    try:
                        updates = {
                            "VALID_COLLEGES": colleges_input.strip(),
                            "VALID_TERMS": terms_input.strip(),
                            "VALID_STATUSES": statuses_input.strip(),
                            "VALID_ROLES": roles_input.strip(),
                            "DEFAULT_YEAR": str(year_input)
                        }
                        for k, v in updates.items():
                            row = db.query(SystemConfig).filter_by(key=k).first()
                            if row:
                                row.value = v
                            else:
                                db.add(SystemConfig(key=k, value=v))
                        
                        db.commit()
                        st.cache_data.clear() # Clear Streamlit cache instantly!
                        st.session_state["flash_msg"] = "System settings updated successfully!"
                        st.rerun()
                    except Exception as e:
                        db.rollback()
                        st.error("Failed to save settings. Please verify inputs.")
                        st.exception(e)

        elif action == "📋 Audit Log":
            st.markdown("### 📋 Recent System Activity & Analytics")
            logs = (
                db.query(AuditLog)
                .order_by(AuditLog.created_at.desc())
                .limit(500)
                .all()
            )
            if logs:
                import plotly.express as px
                df = pd.DataFrame([{
                    "Time":    l.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "User":    l.username,
                    "Action":  l.action,
                    "Target":  l.target,
                    "Detail":  l.detail,
                } for l in logs])
                
                # Render Visual Analytics
                st.markdown("#### 📊 Activity Analytics (Past 500 Logs)")
                an_col1, an_col2 = st.columns(2)
                
                with an_col1:
                    # Donut chart: Action types
                    action_counts = df["Action"].value_counts().reset_index()
                    action_counts.columns = ["Action Type", "Logs Count"]
                    fig_actions = px.pie(
                        action_counts,
                        names="Action Type",
                        values="Logs Count",
                        hole=0.4,
                        title="🎛️ Logs Count by Action Type",
                        color_discrete_sequence=["#0d47a1", "#00897b", "#fb8c00", "#5e35b1", "#e53935"]
                    )
                    fig_actions.update_layout(
                        margin=dict(l=20, r=20, t=40, b=20),
                        legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5)
                    )
                    st.plotly_chart(fig_actions, use_container_width=True)
                    
                with an_col2:
                    # Bar chart: User activity
                    user_counts = df["User"].value_counts().reset_index()
                    user_counts.columns = ["User", "Action Count"]
                    fig_users = px.bar(
                        user_counts,
                        x="Action Count",
                        y="User",
                        orientation="h",
                        title="👥 User Activity Volume",
                        color_discrete_sequence=["#00897b"]
                    )
                    fig_users.update_layout(margin=dict(l=20, r=20, t=40, b=20))
                    st.plotly_chart(fig_users, use_container_width=True)
                
                st.markdown("---")
                st.markdown("#### 📋 Raw Audit Logs list")
                st.dataframe(df[["Time", "User", "Action", "Target", "Detail"]], use_container_width=True, hide_index=True)
            else:
                st.info("No audit entries yet.")
