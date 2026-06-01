import smtplib
import datetime
import os
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models import get_db, Student, Transaction
from api.statement import create_landscape_pdf
from api.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

# SMTP config loaded from environment
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

class EmailPreviewRequest(BaseModel):
    student_id: int
    balance_scope: str
    term: Optional[str] = None
    year: Optional[int] = None
    subject: str
    body: str

class SendEmailRequest(BaseModel):
    student_ids: List[int]
    balance_scope: str
    term: Optional[str] = None
    year: Optional[int] = None
    subject: str
    body: str

@router.post("/preview")
async def preview_email(req: EmailPreviewRequest, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == req.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
        
    tx_query = db.query(Transaction).filter(Transaction.student_id == student.id)
    scope_text = "All Terms"
    
    if req.balance_scope == "Specific Term Only" and req.term and req.year:
        tx_query = tx_query.filter(
            Transaction.term == req.term,
            Transaction.academic_year == req.year
        )
        scope_text = f"{req.term} {req.year}"
        
    txs = tx_query.order_by(Transaction.entry_date.asc()).all()
    
    total_d = sum(t.debit for t in txs)
    total_c = sum(t.credit for t in txs)
    balance = total_d - total_c
    
    # Format texts
    preview_date = datetime.date.today().strftime("%d %B %Y")
    preview_balance = f"{balance:,.2f}"
    
    try:
        formatted_subject = req.subject.format(
            name=student.name,
            id=student.id,
            balance=preview_balance,
            date=preview_date,
            scope=scope_text
        )
        formatted_body = req.body.format(
            name=student.name,
            id=student.id,
            balance=preview_balance,
            date=preview_date,
            scope=scope_text
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Formatting error in template: {e}")
        
    return {
        "student_email": student.email or "no-email@nileuniversity.edu.eg",
        "student_name": student.name,
        "formatted_subject": formatted_subject,
        "formatted_body": formatted_body,
        "current_balance": balance
    }

@router.post("/send")
async def send_emails(
    req: SendEmailRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["Admin", "Editor"]:
        raise HTTPException(status_code=403, detail="Not authorized to send emails.")
        
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        raise HTTPException(status_code=500, detail="SMTP credentials not configured on the server. Contact your administrator.")
        
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"SMTP Connection Failed: {str(e)}")
        
    scope_text = "All Terms"
    if req.balance_scope == "Specific Term Only" and req.term and req.year:
        scope_text = f"{req.term} {req.year}"
        
    success_count = 0
    skipped_count = 0
    
    for sid in req.student_ids:
        student = db.query(Student).filter(Student.id == sid).first()
        if not student or not student.email:
            skipped_count += 1
            continue
            
        tx_query = db.query(Transaction).filter(Transaction.student_id == student.id)
        if req.balance_scope == "Specific Term Only" and req.term and req.year:
            tx_query = tx_query.filter(
                Transaction.term == req.term,
                Transaction.academic_year == req.year
            )
            
        txs = tx_query.order_by(Transaction.entry_date.asc()).all()
        total_d = sum(t.debit for t in txs)
        total_c = sum(t.credit for t in txs)
        current_balance = total_d - total_c
        
        if current_balance <= 0:
            skipped_count += 1
            continue
            
        formatted_date = datetime.date.today().strftime("%d %B %Y")
        try:
            formatted_subject = req.subject.format(
                name=student.name,
                id=student.id,
                balance=f"{current_balance:,.2f}",
                date=formatted_date,
                scope=scope_text
            )
            formatted_body = req.body.format(
                name=student.name,
                id=student.id,
                balance=f"{current_balance:,.2f}",
                date=formatted_date,
                scope=scope_text
            )
        except Exception as e:
            logger.warning(f"Template formatting error for student {sid}: {e}")
            skipped_count += 1
            continue
            
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: auto; border: 1px solid #ddd; padding: 20px; border-radius: 10px;">
                    <h2 style="color: #0d47a1;">🏦 Finance Department</h2>
                    <p>{formatted_body.replace(chr(10), '<br>')}</p>
                    <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                    <small style="color: #888;">This is an automated message from the Accounts Receivable System. Please find your detailed statement attached.</small>
                </div>
            </body>
        </html>
        """
        
        msg = MIMEMultipart("mixed")
        msg["Subject"] = formatted_subject
        msg["From"] = f"Finance Department <{SMTP_EMAIL}>"
        msg["To"] = student.email
        
        msg_alternative = MIMEMultipart("alternative")
        msg_alternative.attach(MIMEText(html_content, "html"))
        msg.attach(msg_alternative)
        
        # Build rows as (Transaction, Student) tuples to match create_landscape_pdf signature
        pdf_rows = [(t, student) for t in txs]
        
        pdf_bytes = create_landscape_pdf(
            student.id, 
            student.name, 
            student.college or "", 
            pdf_rows, 
            current_balance, 
            total_d, 
            total_c
        )
        
        part = MIMEBase('application', "octet-stream")
        part.set_payload(pdf_bytes)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="Statement_{student.id}.pdf"')
        msg.attach(part)
        
        try:
            server.sendmail(SMTP_EMAIL, student.email, msg.as_string())
            success_count += 1
        except Exception as e:
            logger.warning(f"Failed to send email to {student.email}: {e}")
            skipped_count += 1
            
    server.quit()
    
    return {
        "success_count": success_count,
        "skipped_count": skipped_count
    }
