# pages/lookup.py
import io
import streamlit as st
import pandas as pd

from config import VALID_TERMS, VALID_STATUSES, VALID_COLLEGES, DEFAULT_YEAR
from auth import require_role
from models import get_db, Student, StudentStatus, StudentScholarship, ScholarshipType, Transaction, write_audit

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


@st.cache_data(ttl=60)
def get_cached_students_list():
    with get_db() as db:
        return db.query(Student.id, Student.name).order_by(Student.name.asc()).all()


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


def generate_clearance_pdf(student, net_balance):
    """توليد كشف براءة ذمة مالية معتمد ومختوم للطالب"""
    import io
    import datetime
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)
    story = []
    styles = getSampleStyleSheet()
    
    NAVY_HEX = "#0d47a1"
    
    title_style = ParagraphStyle('ClearanceTitle', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor(NAVY_HEX), spaceAfter=20, alignment=1)
    body_style = ParagraphStyle('ClearanceBody', parent=styles['Normal'], fontSize=12, leading=20, spaceAfter=15)
    meta_style = ParagraphStyle('ClearanceMeta', parent=styles['Normal'], fontSize=11, leading=16, spaceAfter=8)
    footer_style = ParagraphStyle('ClearanceFooter', parent=styles['Normal'], fontSize=9, textColor=colors.grey, alignment=1)
    
    story.append(Paragraph("Nile University", title_style))
    story.append(Paragraph("<b>FINANCIAL CLEARANCE CERTIFICATE</b>", ParagraphStyle('Sub', parent=title_style, fontSize=16, spaceAfter=30)))
    story.append(Spacer(1, 15))
    
    serial_no = f"NU-CL-{student.id}-{datetime.date.today().strftime('%Y%m%d')}"
    
    story.append(Paragraph(f"<b>Certificate No:</b> {serial_no}", meta_style))
    story.append(Paragraph(f"<b>Date of Issue:</b> {datetime.date.today().strftime('%d %B %Y')}", meta_style))
    story.append(Spacer(1, 20))
    
    body_text = f"""This is to officially certify that the student listed below has fully settled all financial accounts, tuition fees, and administrative charges with the Finance Department at Nile University.<br/><br/>
<b>Student Name:</b> {student.name}<br/>
<b>Student ID:</b> {student.id}<br/>
<b>College / Department:</b> {student.college} - {student.program or '—'}<br/>
<b>Current Status:</b> Account Fully Settled and Cleared (Balance: {abs(net_balance):,.2f} EGP credit / balanced).<br/><br/>
Accordingly, the student is hereby granted full financial clearance, and is cleared of any outstanding liabilities towards the University Accounts Receivable as of this date."""
    
    story.append(Paragraph(body_text, body_style))
    story.append(Spacer(1, 40))
    
    sig_data = [
        ["Prepared By:", "Approved By:"],
        ["________________________", "________________________"],
        ["Accounts Receivable Team", "Director of Finance"],
        ["Nile University", "Nile University"]
    ]
    sig_table = Table(sig_data, colWidths=[250, 250])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 50))
    
    story.append(Paragraph("<i>This is an official document issued by Nile University Finance Office. Any alteration voids this certificate.</i>", footer_style))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


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

    # Autocomplete Search Lookup
    students_list = get_cached_students_list()
    student_options = ["— Start typing Student ID or Name —"] + [f"{s.id} — {s.name}" for s in students_list]
    
    prev_id = st.session_state.get("lookup_id", 0)
    default_idx = 0
    if prev_id > 0:
        for idx, opt in enumerate(student_options):
            if opt.startswith(f"{prev_id} —"):
                default_idx = idx
                break

    selected_opt = st.selectbox(
        "🔍 Search Student ID or Name:",
        options=student_options,
        index=default_idx,
        key="student_autocomplete_search"
    )

    if selected_opt != "— Start typing Student ID or Name —":
        sid = int(selected_opt.split(" — ")[0])
        st.session_state["lookup_id"] = sid
    else:
        st.session_state["lookup_id"] = 0

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
        
        # Color coding outstanding vs. credit balance in the header card
        if net_bal > 0:
            bal_html = f'<div style="text-align: right; margin-right: 15px;"><span style="font-size:11px; text-transform:uppercase; opacity:0.8; font-weight:600; letter-spacing:0.5px; display:block;">Outstanding Balance</span><span style="font-size:22px; font-weight:800; color: #ff8a80;">{net_bal:,.2f} EGP</span></div>'
        else:
            bal_html = f'<div style="text-align: right; margin-right: 15px;"><span style="font-size:11px; text-transform:uppercase; opacity:0.8; font-weight:600; letter-spacing:0.5px; display:block;">Credit Balance</span><span style="font-size:22px; font-weight:800; color: #b9f6ca;">{abs(net_bal):,.2f} EGP</span></div>'

        card_html = (
            f'<div style="background: linear-gradient(135deg, #0d47a1, #1a237e); padding: 24px; border-radius: 16px; color: white; display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);">'
            f'<div style="display: flex; align-items: center; gap: 20px;">'
            f'<div style="width: 64px; height: 64px; background-color: rgba(255, 255, 255, 0.2); border: 2px solid rgba(255, 255, 255, 0.4); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 22px; font-weight: 700; letter-spacing: 1px;">{initials}</div>'
            f'<div><h2 style="margin: 0; font-size: 24px; font-weight: 700; color: white;">{student.name}</h2>'
            f'<p style="margin: 4px 0 0; opacity: 0.85; font-size: 14px;">🆔 Student ID: <b>{student.id}</b> &nbsp;|&nbsp; admit: {student.admit_year}</p></div>'
            f'</div>'
            f'<div style="display: flex; align-items: center; gap: 20px;">'
            f'{bal_html}'
            f'<div style="padding: 8px 16px; border-radius: 30px; font-weight: 700; font-size: 13px; text-transform: uppercase; letter-spacing: 0.8px; {status_style}">● {status_val}</div>'
            f'</div>'
            f'</div>'
        )
        st.markdown(card_html, unsafe_allow_html=True)

        # ── 3. Quick Actions row ──
        if net_bal <= 0:
            act_col1, act_col2, act_col3, act_col4 = st.columns([1.5, 1.5, 1.8, 1.2])
        else:
            act_col1, act_col2, act_col4 = st.columns([1.5, 1.5, 1.2])
            act_col3 = None
            
        with act_col1:
            from views.statement import create_landscape_pdf
            pdf_bytes = create_landscape_pdf(student.id, student.name, student.college, rows, net_bal, total_d, total_c)
            st.download_button(
                "📄 Download Statement", pdf_bytes,
                file_name=f"SOA_{student.id}.pdf",
                type="primary" if net_bal > 0 else "secondary", use_container_width=True,
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
                        st.success("✅ Email statement sent successfully!")
                    else:
                        st.error(f"❌ Failed to send email: {msg}")

        if act_col3:
            with act_col3:
                clearance_bytes = generate_clearance_pdf(student, net_bal)
                st.download_button(
                    "🏆 Issue Financial Clearance", clearance_bytes,
                    file_name=f"Clearance_{student.id}.pdf",
                    type="primary", use_container_width=True,
                    key=f"quick_clearance_dl_{student.id}"
                )
                        
        with act_col4:
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
            st.markdown("### 💳 Student Ledger Account")
            st.write("Complete transaction history for this student, including debits, credits, and running balance.")
            
            if not rows:
                st.info("⚠️ No financial transactions posted yet for this student.")
            else:
                # Build ledger dataframe
                ledger_data = []
                running_balance = 0.0
                for t, _ in rows:
                    running_balance += (t.debit - t.credit)
                    ledger_data.append({
                        "Date": t.entry_date.strftime("%Y-%m-%d") if hasattr(t.entry_date, 'strftime') else str(t.entry_date),
                        "Reference No": t.reference_no,
                        "Type": t.transaction_type,
                        "Description": t.description or "—",
                        "Term": t.term,
                        "Year": t.academic_year,
                        "Debit (EGP)": t.debit if t.debit > 0 else 0.0,
                        "Credit (EGP)": t.credit if t.credit > 0 else 0.0,
                        "Running Balance (EGP)": running_balance
                    })
                
                df_ledger = pd.DataFrame(ledger_data)
                
                st.dataframe(
                    df_ledger,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Debit (EGP)": st.column_config.NumberColumn(format="%,.2f"),
                        "Credit (EGP)": st.column_config.NumberColumn(format="%,.2f"),
                        "Running Balance (EGP)": st.column_config.NumberColumn(format="%,.2f"),
                    }
                )
                
                # Render Net Balance Box below the table
                bal_card_style = "background-color: #d4edda; color: #155724; border: 1.5px solid #28a745;" if net_bal <= 0 else "background-color: #f8d7da; color: #721c24; border: 1.5px solid #dc3545;"
                bal_card_text = f"Balanced / In Credit: {abs(net_bal):,.2f} EGP" if net_bal <= 0 else f"Outstanding Balance Due: {net_bal:,.2f} EGP"
                
                st.markdown(f"""
                <div style="padding: 12px; border-radius: 8px; font-weight: 700; text-align: center; font-size: 15px; margin-top: 15px; {bal_card_style}">
                    ⚖️ Current {bal_card_text}
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
