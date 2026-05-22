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

# استيراد أدوات بناء الـ PDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def generate_statement_pdf(student, transactions, current_balance, scope_text):
    """دالة فرعية لتوليد ملف الـ PDF الخاص بكشف الحساب التفصيلي في الذاكرة"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    
    # تنسيقات مخصصة للكشف الرياضي/المالي
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=22, textColor=colors.HexColor("#004a99"), spaceAfter=12)
    subtitle_style = ParagraphStyle('DocSubtitle', parent=styles['Heading3'], fontSize=12, textColor=colors.HexColor("#555555"), spaceAfter=15)
    normal_style = ParagraphStyle('DocNormal', parent=styles['Normal'], fontSize=10, spaceAfter=6)
    
    # الهيدر الأساسي للجامعة
    story.append(Paragraph("Nile University - Finance Department", title_style))
    story.append(Paragraph(f"Official Statement of Account ({scope_text})", subtitle_style))
    story.append(Spacer(1, 10))
    
    # بيانات الطالب
    story.append(Paragraph(f"<b>Student Name:</b> {student.name}", normal_style))
    story.append(Paragraph(f"<b>Student ID:</b> {student.id}", normal_style))
    story.append(Paragraph(f"<b>College:</b> {student.college}", normal_style))
    story.append(Paragraph(f"<b>Statement Date:</b> {datetime.date.today().strftime('%d %B %Y')}", normal_style))
    story.append(Spacer(1, 15))
    
    # بناء جدول الحركات التفصيلية
    table_data = [["Date", "Reference", "Description", "Term / Year", "Debit (EGP)", "Credit (EGP)"]]
    
    for tx in transactions:
        tx_date = tx.entry_date.strftime("%Y-%m-%d") if hasattr(tx.entry_date, 'strftime') else str(tx.entry_date)
        table_data.append([
            tx_date,
            tx.reference_no,
            tx.description or "",
            f"{tx.term} {tx.academic_year}",
            f"{tx.debit:,.2f}" if tx.debit > 0 else "0.00",
            f"{tx.credit:,.2f}" if tx.credit > 0 else "0.00"
        ])
    
    # سطر المجموع النهائي للرصيد
    table_data.append(["", "", "", "Outstanding Balance:", f"{current_balance:,.2f} EGP", ""])
    
    # تحديد عرض الأعمدة ليكون متناسقاً مع حجم الصفحة
    t = Table(table_data, colWidths=[65, 75, 155, 75, 85, 85])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#004a99")), # اللون الأزرق لهوية الجامعة
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('TOPPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-2), 0.5, colors.lightgrey),
        # تنسيق سطر المجموع النهائي
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#f0f4ff")),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('LINEABOVE', (0,-1), (-1,-1), 1.5, colors.HexColor("#004a99")),
        ('TOPPADDING', (0,-1), (-1,-1), 8),
    ]))
    
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def render(engine, available_years):
    st.subheader("📩 Automated Email Follow-up")
    st.markdown("Send real-time statement of accounts with detailed PDF attachments to students.")
    require_role("Admin", "Editor")

    # 1. إعدادات السيرفر والإيميل المرسل
    with st.expander("⚙️ SMTP Email Settings", expanded=False):
        c1, c2 = st.columns(2)
        sender_email = c1.text_input("Sender Email Address")
        sender_password = c2.text_input("App Password", type="password") 
        
        c3, c4 = st.columns(2)
        smtp_server = c3.text_input("SMTP Server", value="smtp.gmail.com")
        smtp_port = c4.number_input("SMTP Port", value=587, step=1)

    # 🟢 2. اوبشن تحديد نطاق الرصيد (التيرمات)
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

    # 3. اختيار الطلاب
    st.markdown("### 👥 Select Students")
    with get_db() as db:
        all_students = db.query(Student).all()
        student_options = {f"{s.id} - {s.name}": s for s in all_students}
        
        selected_student_keys = st.multiselect(
            "Search and select students:", 
            options=list(student_options.keys())
        )

    # 4. إعداد نص الرسالة
    st.markdown("### 📝 Email Template")
    st.info("💡 Placeholders: `{name}`, `{id}`, `{balance}`, `{date}`, `{scope}`")
    
    default_subject = "Nile University - Statement of Account Update"
    default_body = """Dear {name},

Please find attached your detailed Statement of Account for {scope} as of {date}.

Your outstanding balance for this period is {balance} EGP. Kindly review the attached PDF for full transaction details.

Best Regards,
Finance Department
Nile University
"""
    email_subject = st.text_input("Subject", value=default_subject)
    email_body = st.text_area("Message Body", value=default_body, height=200)

    # 5. زر الإرسال واللوجيك
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
            server.login(sender_email.strip(), sender_password.strip())
            
            total_students = len(selected_student_keys)
            
            with get_db() as db_session:
                for idx, key in enumerate(selected_student_keys):
                    student = student_options[key]
                    
                    if not student.email:
                        st.toast(f"⚠️ Skipped {student.name} (No Email Address)")
                        skipped_count += 1
                        continue

                    # 🟢 سحب الحركات بناءً على النطاق المحدد (كل التيرمات أو تيرم محدد)
                    tx_query = db_session.query(Transaction).filter(Transaction.student_id == student.id)
                    if balance_scope == "Specific Term Only":
                        tx_query = tx_query.filter(
                            Transaction.term == selected_term, 
                            Transaction.academic_year == int(selected_year)
                        )
                    
                    student_txs = tx_query.order_by(Transaction.entry_date.asc()).all()
                    
                    # حساب الرصيد الخاص بالنطاق المحدد
                    total_debit = sum(t.debit for t in student_txs)
                    total_credit = sum(t.credit for t in student_txs)
                    current_balance = total_debit - total_credit
                    
                    # تجاوز الطالب لو الرصيد صفر أو دائن
                    if current_balance <= 0:
                        st.toast(f"⏭️ Skipped {student.name} (Zero or Credit Balance)")
                        skipped_count += 1
                        continue

                    # تجهيز نص الرسالة الديناميكي
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

                    # بناء الإيميل والمرفقات
                    msg = MIMEMultipart("mixed")
                    msg["Subject"] = email_subject
                    msg["From"] = f"Finance Department <{sender_email.strip()}>"
                    msg["To"] = student.email
                    
                    # الجزء النصي (HTML)
                    msg_alternative = MIMEMultipart("alternative")
                    msg_alternative.attach(MIMEText(html_content, "html"))
                    msg.attach(msg_alternative)

                    # 🟢 توليد وإرفاق ملف الـ PDF
                    pdf_bytes = generate_statement_pdf(student, student_txs, current_balance, scope_text)
                    part = MIMEBase('application', "octet-stream")
                    part.set_payload(pdf_bytes)
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename="Statement_{student.id}.pdf"')
                    msg.attach(part)

                    # إرسال الحزمة بالكامل
                    server.sendmail(sender_email.strip(), student.email, msg.as_string())
                    success_count += 1
                    
                    progress_bar.progress((idx + 1) / total_students, text=f"Sent to {student.name}...")
                    time.sleep(2)

            server.quit()
            progress_bar.empty()
            
            if success_count > 0:
                st.success(f"✅ Successfully sent {success_count} emails with PDF statements attached!")
            if skipped_count > 0:
                st.info(f"💡 {skipped_count} students were skipped (Either have 0 balance or missing email).")

        except Exception as e:
            progress_bar.empty()
            st.error("❌ Failed to send emails. Please check your SMTP settings and App Password.")
            st.exception(e)
