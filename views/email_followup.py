# views/email_followup.py
import smtplib
import time
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import streamlit as st
from sqlalchemy.sql import func
from models import get_db, Student, Transaction
from auth import require_role

def render(engine, available_years):
    st.subheader("📩 Automated Email Follow-up")
    st.markdown("Send real-time statement of accounts and follow-up reminders to students.")
    require_role("Admin", "Editor") # السماح للمشرفين والمحررين

    # 1. إعدادات السيرفر والإيميل المرسل
    with st.expander("⚙️ SMTP Email Settings", expanded=True):
        c1, c2 = st.columns(2)
        sender_email = c1.text_input("Sender Email Address")
        # يفضل استخدام App Password لو بتستخدم Gmail أو Office 365
        sender_password = c2.text_input("App Password", type="password") 
        
        c3, c4 = st.columns(2)
        smtp_server = c3.text_input("SMTP Server", value="smtp.gmail.com")
        smtp_port = c4.number_input("SMTP Port", value=587, step=1)

    # 2. الفلترة واختيار الطلاب
    st.markdown("### 👥 Select Students")
    with get_db() as db:
        # هنجيب كل الطلاب عشان نختار منهم
        all_students = db.query(Student).all()
        student_options = {f"{s.id} - {s.name}": s for s in all_students}
        
        selected_student_keys = st.multiselect(
            "Search and select students (Leave empty to select none):", 
            options=list(student_options.keys())
        )

    # 3. إعداد نص الرسالة
    st.markdown("### 📝 Email Template")
    st.info("💡 You can use these placeholders: `{name}`, `{id}`, `{balance}`, `{date}`")
    
    default_subject = "Nile University - Statement of Account Update"
    default_body = """Dear {name},

Please be advised that as of {date}, your current outstanding balance is {balance} EGP.

Kindly review your account and proceed with the necessary payments to avoid any late fees or registration holds.

If you have already made a payment, please disregard this email.

Best Regards,
Finance Department
Nile University
"""
    email_subject = st.text_input("Subject", value=default_subject)
    email_body = st.text_area("Message Body", value=default_body, height=250)

    # 4. زر الإرسال واللوجيك
    if st.button("🚀 Send Follow-up Emails", type="primary"):
        if not sender_email or not sender_password:
            st.error("⚠️ Please configure your SMTP Settings first.")
            return
        
        if not selected_student_keys:
            st.warning("⚠️ Please select at least one student.")
            return

        # شريط التقدم لحماية السيرفر
        progress_text = "Connecting to email server..."
        progress_bar = st.progress(0, text=progress_text)
        
        success_count = 0
        error_count = 0
        
        try:
            # الاتصال بالسيرفر
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(sender_email, sender_password)
            
            total_students = len(selected_student_keys)
            
            with get_db() as db_session:
                for idx, key in enumerate(selected_student_keys):
                    student = student_options[key]
                    
                    # حساب الرصيد الفعلي اللحظي (إجمالي المدين - الدائن)
                    total_debit = db_session.query(func.sum(Transaction.debit)).filter(Transaction.student_id == student.id).scalar() or 0.0
                    total_credit = db_session.query(func.sum(Transaction.credit)).filter(Transaction.student_id == student.id).scalar() or 0.0
                    current_balance = total_debit - total_credit
                    
                    # تجاوز الطالب لو مفيش عليه مديونية (اختياري، ممكن تشيله لو عايز تبعت رصيد صفر)
                    if current_balance <= 0:
                        st.toast(f"⏭️ Skipped {student.name} (Zero or Credit Balance)")
                        continue
                        
                    if not student.email:
                        st.toast(f"⚠️ Skipped {student.name} (No Email Address)")
                        error_count += 1
                        continue

                    # تجهيز الرسالة
                    formatted_body = email_body.format(
                        name=student.name,
                        id=student.id,
                        balance=f"{current_balance:,.2f}",
                        date=datetime.date.today().strftime("%d %B %Y")
                    )
                    
                    # تحويل النص لـ HTML عشان يكون شكله احترافي
                    html_content = f"""
                    <html>
                        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                            <div style="max-width: 600px; margin: auto; border: 1px solid #ddd; padding: 20px; border-radius: 10px;">
                                <h2 style="color: #004a99;">🏦 Finance Department</h2>
                                <p>{formatted_body.replace(chr(10), '<br>')}</p>
                                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                                <small style="color: #888;">This is an automated message from the Accounts Receivable System.</small>
                            </div>
                        </body>
                    </html>
                    """

                    msg = MIMEMultipart("alternative")
                    msg["Subject"] = email_subject
                    msg["From"] = f"Finance Department <{sender_email}>"
                    msg["To"] = student.email
                    
                    msg.attach(MIMEText(html_content, "html"))

                    # إرسال الإيميل
                    server.sendmail(sender_email, student.email, msg.as_string())
                    success_count += 1
                    
                    # تحديث شريط التقدم وعمل فاصل زمني (عشان ميتعملناش حظر)
                    progress_bar.progress((idx + 1) / total_students, text=f"Sent to {student.name}...")
                    time.sleep(2) # انتظار ثانيتين بين كل إيميل والتاني

            server.quit()
            progress_bar.empty()
            
            if success_count > 0:
                st.success(f"✅ Successfully sent {success_count} emails!")
            if error_count > 0:
                st.warning(f"⚠️ {error_count} emails failed (Missing email addresses).")

        except Exception as e:
            progress_bar.empty()
            st.error("❌ Failed to send emails. Please check your SMTP settings and App Password.")
            st.exception(e)
