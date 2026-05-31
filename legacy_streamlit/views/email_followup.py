# views/email_followup.py
import io
import time
import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

import streamlit as st
from sqlalchemy.sql import func
from models import get_db, Student, Transaction
from auth import require_role
from config import VALID_TERMS

# استيراد أدوات بناء الـ PDF للـ Landscape مع الـ Footer
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def generate_statement_pdf(student, transactions, current_balance, scope_text):
    """دالة فرعية لتوليد ملف الـ PDF الخاص بكشف الحساب التفصيلي في الذاكرة"""
    buffer = io.BytesIO()
    
    # 30 left/right margins, 30 top, 40 bottom
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=40)
    story = []
    styles = getSampleStyleSheet()
    
    NAVY_HEX = "#0d47a1"
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=22, textColor=colors.HexColor(NAVY_HEX), spaceAfter=6)
    subtitle_style = ParagraphStyle('DocSubtitle', parent=styles['Heading3'], fontSize=11, textColor=colors.HexColor("#555555"), spaceAfter=15)
    normal_style = ParagraphStyle('DocNormal', parent=styles['Normal'], fontSize=10, leading=14)
    cell_style = ParagraphStyle('CellText', parent=styles['Normal'], fontSize=9, leading=12)
    
    unique_terms = []
    for tx in transactions:
        t_name = f"{tx.term} {tx.academic_year}"
        if t_name not in unique_terms:
            unique_terms.append(t_name)
    terms_display = " | ".join(unique_terms) if unique_terms else scope_text
    
    story.append(Paragraph("Nile University - Finance Department", title_style))
    story.append(Paragraph("Official Student Statement of Account", subtitle_style))
    story.append(Spacer(1, 5))
    
    # ── 1. Student Info Box (Left) ──
    info_text = f"""<b>Student Name:</b> {student.name}<br/>
<b>Student ID:</b> {student.id}<br/>
<b>College:</b> {student.college}<br/>
<b>Statement Date:</b> {datetime.date.today().strftime('%d %B %Y')}<br/>
<b>Included Terms:</b> {terms_display}"""
    
    info_p = Paragraph(info_text, normal_style)
    story.append(info_p)
    story.append(Spacer(1, 20))
    
    # ── 2. Table Data Construction ──
    table_data = [["Date", "Reference", "Type", "Description", "Term / Year", "Debit (EGP)", "Credit (EGP)"]]
    
    sum_debit = 0.0
    sum_credit = 0.0
    for tx in transactions:
        sum_debit += tx.debit
        sum_credit += tx.credit
        tx_date = tx.entry_date.strftime("%Y-%m-%d") if hasattr(tx.entry_date, 'strftime') else str(tx.entry_date)
        
        type_p = Paragraph(tx.transaction_type, cell_style)
        desc_p = Paragraph(tx.description or "", cell_style)
        
        debit_str = f"{tx.debit:,.2f}" if tx.debit > 0 else "—"
        credit_str = f"{tx.credit:,.2f}" if tx.credit > 0 else "—"
        
        table_data.append([
            tx_date,
            tx.reference_no,
            type_p,
            desc_p,
            f"{tx.term} {tx.academic_year}",
            debit_str,
            credit_str
        ])
    
    # Totals Row
    table_data.append(["", "", "", "", "Totals:", f"{sum_debit:,.2f}", f"{sum_credit:,.2f}"])
    
    # Net Balance Row
    balance_label = "Account Balanced:" if current_balance <= 0 else "Net Balance Due:"
    balance_val = f"{current_balance:,.2f} EGP" if current_balance >= 0 else f"({abs(current_balance):,.2f}) EGP Credit"
    table_data.append(["", "", "", "", balance_label, balance_val, ""])
    
    t = Table(table_data, colWidths=[70, 85, 95, 192, 90, 100, 100])
    
    # Base styling
    t_style = [
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor(NAVY_HEX)),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('ALIGN', (5,0), (6,-1), 'RIGHT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('TOPPADDING', (0,0), (-1,0), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-3), 0.5, colors.HexColor("#dcdee6")),
    ]
    
    # Alternating light row backgrounds
    for idx in range(1, len(transactions) + 1):
        if idx % 2 == 1:
            t_style.append(('BACKGROUND', (0, idx), (-1, idx), colors.HexColor("#f8f9fa")))
            
    # Totals Row Styling
    t_style.extend([
        ('ALIGN', (4,-2), (4,-2), 'RIGHT'), 
        ('BACKGROUND', (4,-2), (-1,-2), colors.HexColor("#ebf0fa")),
        ('FONTNAME', (4,-2), (-1,-2), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (4,-2), (-1,-2), 8),
        ('TOPPADDING', (4,-2), (-1,-2), 8),
        ('BOX', (4,-2), (-1,-2), 1, colors.HexColor(NAVY_HEX)),
        ('INNERGRID', (4,-2), (-1,-2), 0.5, colors.HexColor("#b3c6ff")),
    ])
    
    # Net Balance Row Styling
    balance_bg = colors.HexColor("#d4edda") if current_balance <= 0 else colors.HexColor("#f8d7da")
    balance_text = colors.HexColor("#155724") if current_balance <= 0 else colors.HexColor("#721c24")
    
    t_style.extend([
        ('ALIGN', (4,-1), (4,-1), 'RIGHT'),
        ('SPAN', (5,-1), (6,-1)), 
        ('ALIGN', (5,-1), (6,-1), 'CENTER'),
        ('BACKGROUND', (4,-1), (-1,-1), balance_bg),
        ('FONTNAME', (4,-1), (-1,-1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (4,-1), (-1,-1), balance_text),
        ('BOTTOMPADDING', (4,-1), (-1,-1), 10),
        ('TOPPADDING', (4,-1), (-1,-1), 10),
        ('BOX', (4,-1), (-1,-1), 1.5, balance_text),
    ])
    
    t.setStyle(TableStyle(t_style))
    story.append(t)
    
    # ── رسم الـ Footer المخصص للميل في أسفل الصفحة
    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica-Bold', 10)
        canvas.setFillColor(colors.HexColor(NAVY_HEX))
        footer_text = "Nile University Finance Department | Accounts Receivable Team ♥"
        canvas.drawCentredString(doc.pagesize[0]/2, 20, footer_text)
        canvas.restoreState()

    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    buffer.seek(0)
    return buffer.getvalue()


def render(engine, available_years):
    st.subheader("📩 Automated Email Follow-up")
    st.markdown("Send real-time statement of accounts with detailed PDF attachments to students.")
    require_role("Admin", "Editor")

    with st.expander("⚙️ SMTP Email Settings", expanded=False):
        c1, c2 = st.columns(2)
        sender_email = c1.text_input("Sender Email Address", value="abdo.325c@gmail.com")
        sender_password = c2.text_input("App Password", type="password", value="ivpxvvnyyamgqavg") 
        
        c3, c4 = st.columns(2)
        smtp_server = c3.text_input("SMTP Server", value="smtp.gmail.com")
        smtp_port = c4.number_input("SMTP Port", value=587, step=1)

    st.markdown("### 🔍 Balance Scope Settings")
    c_scope, c_t, c_y = st.columns([2, 1, 1])
    balance_scope = c_scope.selectbox(
        "Calculate Balance Based On:", 
        ["Total Historical Balance (All Terms)", "Specific Term Only"]
    )
    
    selected_term = None
    selected_year = None
    scope_text = "All Terms"
    
    if balance_scope == "Specific Term Only":
        selected_term = c_t.selectbox("Select Term:", VALID_TERMS)
        selected_year = c_y.selectbox("Select Year:", available_years)
        scope_text = f"{selected_term} {selected_year}"

    st.markdown("### 👥 Select Students")
    with get_db() as db:
        all_students = db.query(Student).all()
        student_options = {f"{s.id} - {s.name}": s for s in all_students}
        
        selected_student_keys = st.multiselect(
            "Search and select students:", 
            options=list(student_options.keys())
        )

    st.markdown("### 📝 Email Template & Live Preview")
    st.info("💡 Placeholders: `{name}`, `{id}`, `{balance}`, `{date}`, `{scope}`")
    
    default_subject = "Nile University - Statement of Account Update"
    default_body = """Dear {name},

Please find attached your detailed Statement of Account for {scope} as of {date}.

Your outstanding balance for this period is {balance} EGP. Kindly review the attached PDF for full transaction details.

Best Regards,
Finance Department
Nile University
"""
    col_editor, col_preview = st.columns([1.1, 0.9])
    
    with col_editor:
        email_subject = st.text_input("Subject", value=default_subject)
        email_body = st.text_area("Message Body", value=default_body, height=250)

    # ── WYSIWYG Live Email Preview Mockup Card ──
    with col_preview:
        # Resolve values
        preview_name = "John Doe"
        preview_id = "20260001"
        preview_balance = "15,250.00"
        preview_date = datetime.date.today().strftime("%d %B %Y")
        preview_scope = scope_text
        preview_email = "john.doe@nileuniversity.edu.eg"

        if selected_student_keys:
            first_key = selected_student_keys[0]
            first_student = student_options[first_key]
            preview_name = first_student.name
            preview_id = str(first_student.id)
            preview_email = first_student.email or "no-email@nileuniversity.edu.eg"
            
            with get_db() as db_session:
                tx_query = db_session.query(Transaction).filter(Transaction.student_id == first_student.id)
                if balance_scope == "Specific Term Only":
                    tx_query = tx_query.filter(
                        Transaction.term == selected_term, 
                        Transaction.academic_year == int(selected_year)
                    )
                first_txs = tx_query.all()
                t_debit = sum(t.debit for t in first_txs)
                t_credit = sum(t.credit for t in first_txs)
                preview_balance = f"{t_debit - t_credit:,.2f}"

        formatted_subject_preview = email_subject
        formatted_body_preview = email_body
        
        try:
            formatted_subject_preview = email_subject.format(
                name=preview_name,
                id=preview_id,
                balance=preview_balance,
                date=preview_date,
                scope=preview_scope
            )
            formatted_body_preview = email_body.format(
                name=preview_name,
                id=preview_id,
                balance=preview_balance,
                date=preview_date,
                scope=preview_scope
            )
        except KeyError as ke:
            st.caption(f"⚠️ Placeholder error: Missing key {ke}")
        except ValueError as ve:
            st.caption(f"⚠️ Formatting error: {ve}")
        except Exception as e:
            st.caption(f"⚠️ Formatter error: {e}")

        # Render modern mockup email client container
        # Use st.markdown with CSS + HTML
        st.markdown(
            f"""
            <style>
            .email-client-mockup {{
                background: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 12px;
                box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.15);
                font-family: 'Outfit', 'Inter', sans-serif;
                color: #f1f2f6;
                overflow: hidden;
                margin-top: 10px;
                animation: fadeIn 0.4s ease-out;
            }}
            .email-header-bar {{
                background: rgba(255, 255, 255, 0.05);
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                padding: 10px 15px;
                display: flex;
                align-items: center;
                gap: 8px;
            }}
            .dot {{
                width: 10px;
                height: 10px;
                border-radius: 50%;
                display: inline-block;
            }}
            .dot-red {{ background-color: #ff5f56; }}
            .dot-yellow {{ background-color: #ffbd2e; }}
            .dot-green {{ background-color: #27c93f; }}
            .email-client-title {{
                margin-left: auto;
                font-size: 11px;
                font-weight: 500;
                opacity: 0.6;
                letter-spacing: 0.5px;
                text-transform: uppercase;
            }}
            .email-meta {{
                padding: 12px 15px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.06);
                font-size: 13px;
                display: flex;
                flex-direction: column;
                gap: 6px;
            }}
            .email-meta-row {{
                display: flex;
            }}
            .email-meta-label {{
                width: 65px;
                font-weight: 600;
                opacity: 0.7;
            }}
            .email-meta-value {{
                flex: 1;
            }}
            .email-body-content {{
                padding: 20px 24px;
                font-size: 14px;
                line-height: 1.6;
            }}
            .email-container-inner {{
                border: 1px solid rgba(255, 255, 255, 0.08);
                background: rgba(255, 255, 255, 0.02);
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 15px;
            }}
            .email-logo-section {{
                display: flex;
                align-items: center;
                gap: 10px;
                margin-bottom: 15px;
            }}
            .email-logo-icon {{
                width: 24px;
                height: 24px;
                background: linear-gradient(135deg, #0d47a1 0%, #1976d2 100%);
                border-radius: 5px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-size: 11px;
                font-weight: bold;
            }}
            .email-logo-text {{
                font-size: 13px;
                font-weight: 700;
                color: #4facfe;
            }}
            .email-attachment-pill {{
                display: flex;
                align-items: center;
                gap: 8px;
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                padding: 8px 12px;
                border-radius: 6px;
                font-size: 12px;
                width: fit-content;
                transition: all 0.2s ease;
            }}
            .email-attachment-pill:hover {{
                transform: translateY(-1px);
                box-shadow: 0 4px 10px rgba(0,0,0,0.1);
            }}
            @keyframes fadeIn {{
                from {{ opacity: 0; transform: translateY(5px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
            
            /* Light theme variables overrides */
            [data-theme="light"] .email-client-mockup,
            .stApp:not([data-theme="dark"]) .email-client-mockup {{
                background: rgba(255, 255, 255, 0.9);
                border: 1px solid rgba(0, 0, 0, 0.08);
                box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.06);
                color: #2c3e50;
            }}
            [data-theme="light"] .email-header-bar,
            .stApp:not([data-theme="dark"]) .email-header-bar {{
                background: #f8f9fa;
                border-bottom: 1px solid #e9ecef;
            }}
            [data-theme="light"] .email-meta,
            .stApp:not([data-theme="dark"]) .email-meta {{
                border-bottom: 1px solid #f1f3f5;
            }}
            [data-theme="light"] .email-container-inner,
            .stApp:not([data-theme="dark"]) .email-container-inner {{
                border: 1px solid #eef1f6;
                background: #fdfefe;
            }}
            [data-theme="light"] .email-attachment-pill,
            .stApp:not([data-theme="dark"]) .email-attachment-pill {{
                background: #f1f3f5;
                border: 1px solid #dee2e6;
            }}
            [data-theme="light"] .email-logo-text,
            .stApp:not([data-theme="dark"]) .email-logo-text {{
                color: #0d47a1;
            }}
            </style>
            
            <div class="email-client-mockup">
                <div class="email-header-bar">
                    <span class="dot dot-red"></span>
                    <span class="dot dot-yellow"></span>
                    <span class="dot dot-green"></span>
                    <span class="email-client-title">Live Preview Client</span>
                </div>
                <div class="email-meta">
                    <div class="email-meta-row">
                        <span class="email-meta-label">To:</span>
                        <span class="email-meta-value" style="color: #1976d2; font-weight: 500;">{preview_name} &lt;{preview_email}&gt;</span>
                    </div>
                    <div class="email-meta-row">
                        <span class="email-meta-label">Subject:</span>
                        <span class="email-meta-value" style="font-weight: 600;">{formatted_subject_preview}</span>
                    </div>
                </div>
                <div class="email-body-content">
                    <div class="email-container-inner">
                        <div class="email-logo-section">
                            <div class="email-logo-icon">NU</div>
                            <div class="email-logo-text">Nile University - Finance Department</div>
                        </div>
                        <div style="font-size: 13px; opacity: 0.95; white-space: pre-line;">{formatted_body_preview}</div>
                        <hr style="border: none; border-top: 1px solid rgba(120, 120, 120, 0.2); margin: 15px 0;">
                        <small style="opacity: 0.6; font-size: 11px; display: block; line-height: 1.4;">
                            This is an automated message from the Accounts Receivable System. Please find your detailed statement attached.
                        </small>
                    </div>
                    <div class="email-attachment-pill">
                        <span>📄</span>
                        <strong>Statement_{preview_id}.pdf</strong>
                        <span style="opacity: 0.6;">(ReportLab Statement)</span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    if st.button("🚀 Send Follow-up Emails", type="primary"):
        if not sender_email or not sender_password:
            st.error("⚠️ Please configure your SMTP Settings first.")
            return
        
        if not selected_student_keys:
            st.warning("⚠️ Please select at least one student.")
            return

        progress_text = "Connecting to email server..."
        progress_bar = st.progress(0, text=progress_text)
        
        success_count = 0
        skipped_count = 0
        
        try:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            # 🟢 استخدام replace لمسح الفراغات الداخلية في الباسورد نهائياً
            server.login(sender_email.strip(), sender_password.replace(" ", ""))
            
            total_students = len(selected_student_keys)
            
            with get_db() as db_session:
                for idx, key in enumerate(selected_student_keys):
                    student = student_options[key]
                    
                    if not student.email:
                        st.toast(f"⚠️ Skipped {student.name} (No Email Address)")
                        skipped_count += 1
                        continue

                    tx_query = db_session.query(Transaction).filter(Transaction.student_id == student.id)
                    if balance_scope == "Specific Term Only":
                        tx_query = tx_query.filter(
                            Transaction.term == selected_term, 
                            Transaction.academic_year == int(selected_year)
                        )
                    
                    student_txs = tx_query.order_by(Transaction.entry_date.asc()).all()
                    
                    total_debit = sum(t.debit for t in student_txs)
                    total_credit = sum(t.credit for t in student_txs)
                    current_balance = total_debit - total_credit
                    
                    if current_balance <= 0:
                        st.toast(f"⏭️ Skipped {student.name} (Zero or Credit Balance)")
                        skipped_count += 1
                        continue

                    formatted_body = email_body.format(
                        name=student.name,
                        id=student.id,
                        balance=f"{current_balance:,.2f}",
                        date=datetime.date.today().strftime("%d %B %Y"),
                        scope=scope_text
                    )
                    
                    html_content = f"""
                    <html>
                        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                            <div style="max-width: 600px; margin: auto; border: 1px solid #ddd; padding: 20px; border-radius: 10px;">
                                <h2 style="color: #004a99;">🏦 Finance Department</h2>
                                <p>{formatted_body.replace(chr(10), '<br>')}</p>
                                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                                <small style="color: #888;">This is an automated message from the Accounts Receivable System. Please find your detailed statement attached.</small>
                            </div>
                        </body>
                    </html>
                    """

                    msg = MIMEMultipart("mixed")
                    msg["Subject"] = email_subject
                    msg["From"] = f"Finance Department <{sender_email.strip()}>"
                    msg["To"] = student.email
                    
                    msg_alternative = MIMEMultipart("alternative")
                    msg_alternative.attach(MIMEText(html_content, "html"))
                    msg.attach(msg_alternative)

                    # توليد المرفق بالتنسيق الجديد الملموم والـ Landscape والـ Footer
                    pdf_bytes = generate_statement_pdf(student, student_txs, current_balance, scope_text)
                    part = MIMEBase('application', "octet-stream")
                    part.set_payload(pdf_bytes)
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename="Statement_{student.id}.pdf"')
                    msg.attach(part)

                    server.sendmail(sender_email.strip(), student.email, msg.as_string())
                    success_count += 1
                    
                    progress_bar.progress((idx + 1) / total_students, text=f"Sent to {student.name}...")
                    time.sleep(2)

            server.quit()
            progress_bar.empty()
            
            if success_count > 0:
                st.toast(f"✅ Successfully sent {success_count} emails with formatted PDF statements!", icon="✅")
            if skipped_count > 0:
                st.info(f"💡 {skipped_count} students were skipped (Either have 0 balance or missing email).")

        except Exception as e:
            progress_bar.empty()
            st.error("❌ Failed to send emails. Please check your SMTP settings and App Password.")
            st.exception(e)
