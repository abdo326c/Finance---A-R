import io
import datetime
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from pydantic import BaseModel

from models import get_db, Student, StudentStatus, StudentScholarship, ScholarshipType, Transaction, write_audit
from api.auth import get_current_user

router = APIRouter()

class MasterDataUpdate(BaseModel):
    name: str
    college: str
    program: str
    email: str
    mobile: str
    price_per_hr: float
    is_sponsored: bool
    sponsor_name: str
    sibling_id: str
    general_notes: str

class StatusUpdate(BaseModel):
    term: str
    year: int
    status: str

@router.get("/profile/{student_id}")
async def get_student_profile(student_id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    latest_status = db.query(StudentStatus).filter_by(student_id=student.id).order_by(StudentStatus.academic_year.desc(), StudentStatus.id.desc()).first()
    status_val = latest_status.status if latest_status else "Active"
    
    # Calc balance
    rows = db.query(Transaction).filter(Transaction.student_id == student.id).all()
    total_d = sum(t.debit for t in rows)
    total_c = sum(t.credit for t in rows)
    net_bal = total_d - total_c
    
    # Status history
    statuses = db.query(StudentStatus).filter_by(student_id=student.id).order_by(StudentStatus.academic_year.desc(), StudentStatus.id.desc()).all()
    
    # Scholarships
    sch_rows = db.query(StudentScholarship, ScholarshipType).join(ScholarshipType).filter(StudentScholarship.student_id == student.id).order_by(StudentScholarship.academic_year.desc()).all()
    
    return {
        "student": {
            "id": student.id,
            "name": student.name,
            "college": student.college,
            "program": student.program,
            "email": student.email,
            "mobile": student.mobile,
            "national_id": student.national_id,
            "nationality": student.nationality,
            "admit_year": student.admit_year,
            "price_per_hr": student.price_per_hr,
            "is_sponsored": student.is_sponsored,
            "sponsor_name": student.sponsor_name,
            "sibling_id": student.sibling_id,
            "general_notes": student.general_notes
        },
        "status": status_val,
        "balance": net_bal,
        "status_history": [{"term": s.term, "year": s.academic_year, "status": s.status} for s in statuses],
        "scholarships": [{"term": ss.term, "year": ss.academic_year, "name": st.name, "percentage": ss.percentage, "is_active": ss.is_active} for ss, st in sch_rows]
    }

@router.put("/profile/{student_id}")
async def update_student_profile(student_id: int, data: MasterDataUpdate, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["Admin", "Editor"]:
        raise HTTPException(status_code=403, detail="Not authorized to edit master data")
        
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    student.name = data.name
    student.college = data.college
    student.program = data.program
    student.email = data.email
    student.mobile = data.mobile
    student.price_per_hr = data.price_per_hr
    student.is_sponsored = data.is_sponsored
    student.sponsor_name = data.sponsor_name if data.is_sponsored else None
    student.general_notes = data.general_notes
    student.sibling_id = int(data.sibling_id) if data.sibling_id and data.sibling_id.isdigit() else None
    
    write_audit(db, current_user.username, "EDIT_STUDENT", f"student_id={student.id}", "Master data & Notes updated")
    db.commit()
    return {"message": "Student data updated successfully"}

@router.post("/status/{student_id}")
async def update_student_status(student_id: int, data: StatusUpdate, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.query(StudentStatus).filter_by(student_id=student_id, term=data.term, academic_year=data.year).first()
    if existing:
        existing.status = data.status
    else:
        db.add(StudentStatus(student_id=student_id, term=data.term, academic_year=data.year, status=data.status))
        
    write_audit(db, current_user.username, "UPDATE_STATUS", f"student_id={student_id}", f"{data.term} {data.year} -> {data.status}")
    db.commit()
    return {"message": "Status updated successfully"}

@router.get("/clearance/{student_id}")
async def issue_clearance(student_id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    rows = db.query(Transaction).filter(Transaction.student_id == student.id).all()
    net_bal = sum(t.debit for t in rows) - sum(t.credit for t in rows)
    
    if net_bal > 0:
        raise HTTPException(status_code=400, detail="Cannot issue clearance for a student with an outstanding balance.")
        
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)
        story = []
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle('ClearanceTitle', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor('#0d47a1'), spaceAfter=20, alignment=1)
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
        
        body_text = f"This is to officially certify that the student listed below has fully settled all financial accounts, tuition fees, and administrative charges with the Finance Department at Nile University.<br/><br/><b>Student Name:</b> {student.name}<br/><b>Student ID:</b> {student.id}<br/><b>College / Department:</b> {student.college} - {student.program or '---'}<br/><b>Current Status:</b> Account Fully Settled and Cleared (Balance: {abs(net_bal):,.2f} EGP credit / balanced).<br/><br/>Accordingly, the student is hereby granted full financial clearance, and is cleared of any outstanding liabilities towards the University Accounts Receivable as of this date."
        
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
        pdf_bytes = buffer.getvalue()
        
        write_audit(db, current_user.username, "ISSUE_CLEARANCE", f"student_id={student.id}", "Generated Financial Clearance PDF")
        db.commit()
        
        return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=Clearance_{student.id}.pdf"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export")
async def export_all_students(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    students = db.query(Student).all()
    if not students:
        raise HTTPException(status_code=404, detail="No students found")
        
    df = pd.DataFrame([{
        "Student ID": s.id, "Name": s.name, "College": s.college, "Program": s.program,
        "Email": s.email, "Mobile": s.mobile, "National ID": s.national_id,
        "Nationality": s.nationality, "Admit Year": s.admit_year,
        "Price / Hr (EGP)": s.price_per_hr, "Is Sponsored": s.is_sponsored,
        "Sponsor Name": s.sponsor_name, "Sibling ID": s.sibling_id,
        "General Notes": s.general_notes
    } for s in students])
    
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    
    write_audit(db, current_user.username, "EXPORT_ALL_STUDENTS", "master_data", "Exported Master Data to Excel")
    db.commit()
    
    return Response(content=buf.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=All_Students_Master_Data.xlsx"})
