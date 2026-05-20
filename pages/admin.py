# pages/admin.py
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
