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
        
        # كلمة مرور التطبيق (App Password) من إعدادات حساب مايكروسوفت
        sender_password = c2.text_input("App Password", type="password") 
        
        c3, c4 = st.columns(2)
        # 🟢 تم التعديل هنا: السيرفر الافتراضي أصبح Office 365
        smtp_server = c3.text_input("SMTP Server", value="smtp.office365.com")
        smtp_port = c4.number_input("SMTP Port", value=587, step=1)

    # 2. الفلترة واختيار الطلاب
    st.markdown("### 👥 Select Students")
