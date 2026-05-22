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


def render_info_card(label: str, value: str, icon: str = ""):
    """كارد صغير أنيق بدل st.metric الكبيرة"""
    st.markdown(f"""
    <div style="
        background: #f8f9fc;
        border: 1px solid #e3e6ef;
        border-radius: 10px;
        padding: 12px 16px;
        display: flex;
        flex-direction: column;
        gap: 4px;
    ">
        <span style="font-size:11px; color:#6c757d; text-transform:uppercase; letter-spacing:0.6px; font-weight:600;">
            {icon} {label}
        </span>
        <span style="font-size:17px; color:#1a3a5c; font-weight:700; line-height:1.3;">
            {value}
        </span>
    </div>
    """, unsafe_allow_html=True)


def render():
    c_head, c_btn = st.columns([3, 1])
    c_head.subheader("🔍 Student Data Explorer")

    all_excel_data = get_all_students_excel()
    if all_excel_data:
        c_btn.download_button(
            "📥 Download All Students", all_excel_data,
            file_name="All_Students_Master_Data.xlsx",
            type="primary", use_container_width=True
        )

    with st.form("lookup_form", clear_on_submit=False):
        default = str(st.session_state.get("lookup_id", "")) if st.session_state.get("lookup_id", 0) > 0 else ""
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

        df_single = pd.DataFrame([{
            "Student ID": student.id, "Name": student.name, "College": student.college,
            "Program": student.program, "Email": student.email, "Mobile": student.mobile,
            "National ID": student.national_id, "Nationality": student.nationality,
            "Admit Year": student.admit_year, "Price / Hr (EGP)": student.price_per_hr,
            "Is Sponsored": student.is_sponsored, "Sponsor Name": student.sponsor_name,
            "Sibling ID": student.sibling_id, "General Notes": student.general_notes
        }])
        buf_single = io.BytesIO()
        df_single.to_excel(buf_single, index=False)

        # ── 1. Fetch Current Status & Total Debit/Credit ──
        latest_status = db.query(StudentStatus).filter_by(student_id=student.id).order_by(StudentStatus.academic_year.desc(), StudentStatus.id.desc()).first()
        status_val = latest_status.status if latest_status else "Active"
        
        # Color coding for status
        status_styles = {
            "Active": "background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb;",
            "Semester Withdraw": "background-color: #fff3cd; color: #856404; border: 1px solid #ffeeba;",
            "Inactive": "background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb;",
            "Graduated": "background-color: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb;",
            "Program Withdraw": "background-color: #e2e3e5; color: #383d41; border: 1px solid #d6d8db;"
        }
        status_style = status_styles.get(status_val, "background-color: #e2e3e5; color: #383d41;")

        # Fetch financial calculations for dynamic stamp/quick buttons
        rows = db.query(Transaction, Student).join(Student, Transaction.student_id == Student.id).filter(Transaction.student_id == student.id).order_by(Transaction.entry_date.asc()).all()
        total_d = sum(t.debit for t, _ in rows)
        total_c = sum(t.credit for t, _ in rows)
        net_bal = total_d - total_c

        # ── 2. Premium Avatar Header Card ──
        initials = "".join([part[0] for part in student.name.split()[:2]]).upper() if student.name else "NU"
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #0d47a1, #1a237e);
            padding: 24px;
            border-radius: 16px;
            color: white;
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 20px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        ">
            <div style="display: flex; align-items: center; gap: 20px;">
                <div style="
                    width: 64px;
                    height: 64px;
                    background-color: rgba(255, 255, 255, 0.2);
                    border: 2px solid rgba(255, 255, 255, 0.4);
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 22px;
                    font-weight: 700;
                    letter-spacing: 1px;
                ">
                    {initials}
                </div>
                <div>
                    <h2 style="margin: 0; font-size: 24px; font-weight: 700; color: white;">{student.name}</h2>
                    <p style="margin: 4px 0 0; opacity: 0.85; font-size: 14px;">
                        🆔 Student ID: <b>{student.id}</b> &nbsp;|&nbsp; admit: {student.admit_year}
                    </p>
                </div>
            </div>
            <div style="
                padding: 8px 16px;
                border-radius: 30px;
                font-weight: 700;
                font-size: 13px;
                text-transform: uppercase;
                letter-spacing: 0.8px;
                {status_style}
            ">
                ● {status_val}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── 3. Quick Actions row ──
        act_col1, act_col2, act_col3 = st.columns([1.5, 1.5, 1])
        
        with act_col1:
            from views.statement import create_landscape_pdf
            pdf_bytes = create_landscape_pdf(student.id, student.name, student.college, rows, net_bal, total_d, total_c)
            st.download_button(
                "📄 Download Statement PDF", pdf_bytes,
                file_name=f"SOA_{student.id}.pdf",
                type="primary", use_container_width=True,
                key=f"quick_pdf_dl_{student.id}_{net_bal}"
            )
            
        with act_col2:
            if st.button("📩 Email Statement", type="secondary", use_container_width=True, key=f"quick_email_btn_{student.id}"):
                with st.spinner("Preparing and sending email..."):
                    # Quick email helper
                    def send_quick_statement(std, txs, bal):
                        import smtplib
                        from email.mime.multipart import MIMEMultipart
                        from email.mime.text import MIMEText
                        from email.mime.base import MIMEBase
                        from email import encoders
                        from views.email_followup import generate_statement_pdf
                        
                        sender_email = st.secrets.get("SMTP_USER", "abdo.325c@gmail.com")
                        sender_password = st.secrets.get("SMTP_PASS", "ivpxvvnyyamgqavg")
                        
                        if not std.email:
                            return False, "Student does not have an email address registered."
                            
                        try:
                            server = smtplib.SMTP("smtp.gmail.com", 587)
                            server.starttls()
                            server.login(sender_email.strip(), sender_password.replace(" ", ""))
                            
                            tx_list = [t for t, _ in txs]
                            pdf_attachment = generate_statement_pdf(std, tx_list, bal, "All Terms")
                            
                            msg = MIMEMultipart("mixed")
                            msg["Subject"] = "Nile University - Student Statement of Account"
                            msg["From"] = f"Finance Department <{sender_email.strip()}>"
                            msg["To"] = std.email
                            
                            body = f"""Dear {std.name},

Please find attached your updated Statement of Account as of today.

Outstanding Balance: {bal:,.2f} EGP.

Best Regards,
Finance Department
Nile University"""

                            msg.attach(MIMEText(body, "plain"))
                            
                            part = MIMEBase('application', "octet-stream")
                            part.set_payload(pdf_attachment)
                            encoders.encode_base64(part)
                            part.add_header('Content-Disposition', f'attachment; filename="Statement_{std.id}.pdf"')
                            msg.attach(part)
                            
                            server.sendmail(sender_email.strip(), std.email, msg.as_string())
                            server.quit()
                            return True, "Email sent successfully!"
                        except Exception as ex:
                            return False, str(ex)

                    success, msg = send_quick_statement(student, rows, net_bal)
                    if success:
                        st.success("✅ Email statement sent successfully to registered address!")
                    else:
                        st.error(f"❌ Failed to send email: {msg}")
                        
        with act_col3:
            st.download_button(
                "📥 Export Profile Excel", buf_single.getvalue(),
                file_name=f"Student_{student.id}_Profile.xlsx",
                type="secondary", use_container_width=True,
                key=f"quick_xl_dl_{student.id}"
            )
            
        st.markdown("<br>", unsafe_allow_html=True)

        # ── 4. CRM Tabbed Structure ──
        tab1, tab2, tab3 = st.tabs(["📝 Profile Details", "🎓 Scholarships", "💳 Financial Ledger Timeline"])

        with tab1:
            # ── 3 core metrics ──
            mc1, mc2, mc3 = st.columns(3)
            with mc1:
                render_info_card("College", student.college or "—", "🎓")
            with mc2:
                render_info_card("Program", student.program or "—", "📚")
            with mc3:
                price_val = f"{student.price_per_hr:,.0f} EGP / hr" if student.price_per_hr else "—"
                render_info_card("Price / Credit Hour", price_val, "💰")
                
            st.markdown("<br>", unsafe_allow_html=True)

            l, r = st.columns(2)
            l.markdown(f"""
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 12px; border: 1px solid #e9ecef; height: 100%;">
                <h4 style="margin-top: 0; color: #0d47a1;">✉️ Contact Details</h4>
                <p style="margin: 8px 0;"><b>Email:</b> {student.email or "—"}</p>
                <p style="margin: 8px 0;"><b>Mobile:</b> {student.mobile or "—"}</p>
                <p style="margin: 8px 0;"><b>Admit Year:</b> {student.admit_year or "—"}</p>
            </div>
            """, unsafe_allow_html=True)
            
            r.markdown(f"""
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 12px; border: 1px solid #e9ecef; height: 100%;">
                <h4 style="margin-top: 0; color: #0d47a1;">📋 Identification & Background</h4>
                <p style="margin: 8px 0;"><b>National ID:</b> {student.national_id or "—"}</p>
                <p style="margin: 8px 0;"><b>Nationality:</b> {student.nationality or "—"}</p>
                <p style="margin: 8px 0;"><b>Birth Date:</b> {student.birth_date or "—"}</p>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            sl, sr = st.columns(2)
            with sl:
                if student.is_sponsored:
                    st.success(f"🤝 **Sponsored Student** (By: {student.sponsor_name})")
                else:
                    st.write("💼 **Sponsorship:** None")
            with sr:
                if student.sibling_id:
                    st.info(f"👨‍👩‍👧 **Sibling ID:** {student.sibling_id}")
                else:
                    st.write("👨‍👩‍👧 **Sibling ID:** None")

            if student.general_notes:
                st.warning(f"📌 **General Notes:** {student.general_notes}")
                
            # Academic Status Form inside Tab 1
            st.markdown("<br>---", unsafe_allow_html=True)
            st.markdown("### 📌 Academic Status History")
            statuses = db.query(StudentStatus).filter_by(student_id=sid).order_by(StudentStatus.academic_year.desc(), StudentStatus.id.desc()).all()
            if statuses:
                df_s = pd.DataFrame([{"Term": s.term, "Year": s.academic_year, "Status": s.status} for s in statuses])
                st.dataframe(
                    df_s.style.map(lambda v: STATUS_COLORS.get(v, ""), subset=["Status"]),
                    use_container_width=True, hide_index=True,
                )
            else:
                st.info("No status history yet.")

            with st.expander("⚙️ Update / Add Status"):
                with st.form("status_form"):
                    sc1, sc2, sc3 = st.columns(3)
                    s_term  = sc1.selectbox("Term:",   VALID_TERMS)
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

        with tab2:
            st.markdown("### 🎓 Scholarships (All Terms)")
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

        with tab3:
            st.markdown("### 💳 Visual Financial Ledger Timeline")
            st.write("Chronological transaction timeline showing the visual lifecycle of debits, credits, and running balance.")
            
            # Construct interactive visual timeline
            if not rows:
                st.info("⚠️ No financial transactions posted yet for this student.")
            else:
                running_balance = 0.0
                
                # Render Net Balance Due at the top of the timeline
                bal_card_style = "background-color: #d4edda; color: #155724; border: 1.5px solid #28a745;" if net_bal <= 0 else "background-color: #f8d7da; color: #721c24; border: 1.5px solid #dc3545;"
                bal_card_text = f"Balanced / In Credit: {abs(net_bal):,.2f} EGP" if net_bal <= 0 else f"Outstanding Balance Due: {net_bal:,.2f} EGP"
                
                st.markdown(f"""
                <div style="padding: 16px; border-radius: 12px; font-weight: 700; text-align: center; font-size: 16px; margin-bottom: 24px; {bal_card_style}">
                    ⚖️ Current {bal_card_text}
                </div>
                """, unsafe_allow_html=True)
                
                for t, _ in rows:
                    running_balance += (t.debit - t.credit)
                    is_debit = t.debit > 0
                    
                    # Colors and icons based on transaction type
                    if is_debit:
                        bg_color = "#fff5f5"
                        border_color = "#feb2b2"
                        text_color = "#9b2c2c"
                        badge_bg = "#fed7d7"
                        badge_text = "DEBIT / CHARGE"
                        amt_sign = "+"
                        amt_val = t.debit
                        icon = "📄"
                    else:
                        bg_color = "#f0fff4"
                        border_color = "#9ae6b4"
                        text_color = "#22543d"
                        badge_bg = "#c6f6d5"
                        badge_text = "CREDIT / PAYMENT"
                        amt_sign = "-"
                        amt_val = t.credit
                        icon = "💰"
                        
                    if "Adjustment" in t.transaction_type or "ADJ" in t.reference_no:
                        icon = "⚙️"
                    elif "Discount" in t.transaction_type or "SCH" in t.reference_no:
                        icon = "🎓"

                    tx_date = t.entry_date.strftime("%Y-%m-%d") if hasattr(t.entry_date, 'strftime') else str(t.entry_date)

                    st.markdown(f"""
                    <div style="
                        background-color: {bg_color};
                        border: 1px solid {border_color};
                        padding: 16px;
                        border-radius: 10px;
                        margin-bottom: 12px;
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.01);
                    ">
                        <div style="display: flex; align-items: center; gap: 15px;">
                            <div style="font-size: 24px;">{icon}</div>
                            <div>
                                <span style="
                                    font-size: 10px;
                                    font-weight: 700;
                                    padding: 3px 8px;
                                    border-radius: 4px;
                                    background-color: {badge_bg};
                                    color: {text_color};
                                    text-transform: uppercase;
                                    letter-spacing: 0.5px;
                                ">
                                    {badge_text}
                                </span>
                                <h4 style="margin: 8px 0 4px; color: #1a202c; font-size: 15px;">{t.description or t.transaction_type}</h4>
                                <span style="font-size: 12px; color: #718096;">
                                    Ref: <b>{t.reference_no}</b> &nbsp;|&nbsp; Date: {tx_date} &nbsp;|&nbsp; Term: {t.term} {t.academic_year}
                                </span>
                            </div>
                        </div>
                        <div style="text-align: right;">
                            <h3 style="margin: 0; color: {text_color}; font-size: 18px; font-weight: 700;">
                                {amt_sign}{amt_val:,.2f} EGP
                            </h3>
                            <span style="font-size: 11px; color: #718096; font-style: italic;">
                                Running Bal: {running_balance:,.2f} EGP
                            </span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        # ── Edit Master Data ──
        if st.session_state.get("user_role") in ["Admin", "Editor"]:
            st.markdown("---")
            if st.toggle("🔓 Unlock Edit Mode"):
                st.warning("⚠️ You are modifying master student data.")

                with st.form("edit_master_data_form"):
                    e1, e2, e3 = st.columns(3)
                    e_name    = e1.text_input("Full Name",      value=student.name or "")
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
                    e_is_sponsored   = c_s1.checkbox("Is Sponsored?", value=student.is_sponsored)
                    e_sponsor_name   = c_s2.text_input("Sponsor Name", value=student.sponsor_name or "", placeholder="e.g. MISR El Kheir")
                    e_sibling_id_raw = c_s3.text_input("Sibling ID (Optional)", value=str(student.sibling_id) if student.sibling_id else "")

                    e_notes = st.text_area(
                        "General Notes (Internal use)", value=student.general_notes or "",
                        placeholder="Add any specific conditions, notes or instructions regarding this student..."
                    )

                    if st.form_submit_button("💾 Save Changes", type="primary"):
                        try:
                            sib_id = None
                            if e_sibling_id_raw and e_sibling_id_raw.strip().isdigit():
                                sib_id = int(e_sibling_id_raw.strip())

                            student.name, student.college, student.price_per_hr = e_name, e_college, e_price
                            student.email, student.mobile, student.program       = e_email, e_mobile, e_program
                            student.is_sponsored  = e_is_sponsored
                            student.sponsor_name  = e_sponsor_name if e_is_sponsored else None
                            student.general_notes = e_notes
                            student.sibling_id    = sib_id

                            write_audit(db, st.session_state["logged_in_user"],
                                        "EDIT_STUDENT", f"student_id={sid}", "Master data & Notes updated")
                            db.commit()
                            st.cache_data.clear()
                            st.session_state["flash_msg"] = "Student data updated successfully!"
                            st.rerun()
                        except Exception as e:
                            db.rollback()
                            st.error(f"Save failed. Error: {str(e)}")
