import io
import datetime
import pandas as pd
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from models import get_db, Transaction, Student
from api.auth import get_current_user
from config import VALID_TERMS

from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT, TA_CENTER

router = APIRouter()

def create_landscape_pdf(student_id, student_name, student_college, rows, current_balance, total_d, total_c):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=40)
    story = []
    styles = getSampleStyleSheet()
    NAVY_HEX = "#0d47a1"
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=22, textColor=colors.HexColor(NAVY_HEX), spaceAfter=6)
    subtitle_style = ParagraphStyle('DocSubtitle', parent=styles['Heading3'], fontSize=11, textColor=colors.HexColor("#555555"), spaceAfter=15)
    normal_style = ParagraphStyle('DocNormal', parent=styles['Normal'], fontSize=10, leading=14)
    cell_style = ParagraphStyle('CellText', parent=styles['Normal'], fontSize=9, leading=12)
    
    unique_terms = []
    for t, _ in rows:
        t_name = f"{t.term} {t.academic_year}"
        if t_name not in unique_terms:
            unique_terms.append(t_name)
    terms_display = " | ".join(unique_terms) if unique_terms else "All Terms"
    
    story.append(Paragraph("Nile University - Finance Department", title_style))
    story.append(Paragraph("Official Student Statement of Account", subtitle_style))
    story.append(Spacer(1, 5))
    
    info_text = f"""<b>Student Name:</b> {student_name}<br/>
<b>Student ID:</b> {student_id}<br/>
<b>College:</b> {student_college}<br/>
<b>Statement Date:</b> {datetime.date.today().strftime('%d %B %Y')}<br/>
<b>Included Terms:</b> {terms_display}"""
    
    info_p = Paragraph(info_text, normal_style)
    story.append(info_p)
    story.append(Spacer(1, 20))
    
    table_data = [["Date", "Reference", "Type", "Description", "Term / Year", "Debit (EGP)", "Credit (EGP)"]]
    
    for t, _ in rows:
        tx_date = t.entry_date.strftime("%Y-%m-%d") if hasattr(t.entry_date, 'strftime') else str(t.entry_date)
        type_p = Paragraph(t.transaction_type, cell_style)
        desc_p = Paragraph(t.description or "", cell_style)
        debit_str = f"{t.debit:,.2f}" if t.debit > 0 else "—"
        credit_str = f"{t.credit:,.2f}" if t.credit > 0 else "—"
        table_data.append([tx_date, t.reference_no, type_p, desc_p, f"{t.term} {t.academic_year}", debit_str, credit_str])
    
    table_data.append(["", "", "", "", "Totals:", f"{total_d:,.2f}", f"{total_c:,.2f}"])
    
    balance_label_text = "Account Balanced:" if current_balance <= 0 else "Net Balance Due:"
    balance_val_text = f"{current_balance:,.2f} EGP" if current_balance >= 0 else f"({abs(current_balance):,.2f}) EGP Credit"
    balance_color = colors.HexColor("#155724") if current_balance <= 0 else colors.HexColor("#721c24")
    
    lbl_style = ParagraphStyle('BalanceLabel', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=12, alignment=TA_RIGHT, textColor=balance_color)
    val_style = ParagraphStyle('BalanceVal', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=12, alignment=TA_CENTER, textColor=balance_color)
    table_data.append(["", "", "", "", Paragraph(balance_label_text, lbl_style), Paragraph(balance_val_text, val_style), ""])
    
    t = Table(table_data, colWidths=[70, 85, 95, 192, 90, 100, 100])
    
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
    
    for idx in range(1, len(rows) + 1):
        if idx % 2 == 1:
            t_style.append(('BACKGROUND', (0, idx), (-1, idx), colors.HexColor("#f8f9fa")))
            
    t_style.extend([
        ('ALIGN', (4,-2), (4,-2), 'RIGHT'), 
        ('BACKGROUND', (4,-2), (-1,-2), colors.HexColor("#ebf0fa")),
        ('FONTNAME', (4,-2), (-1,-2), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (4,-2), (-1,-2), 8),
        ('TOPPADDING', (4,-2), (-1,-2), 8),
        ('BOX', (4,-2), (-1,-2), 1, colors.HexColor(NAVY_HEX)),
        ('INNERGRID', (4,-2), (-1,-2), 0.5, colors.HexColor("#b3c6ff")),
    ])
    
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
    
    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica-Bold', 10)
        canvas.setFillColor(colors.HexColor(NAVY_HEX))
        canvas.drawCentredString(doc.pagesize[0]/2, 20, "Nile University Finance Department | Accounts Receivable Team")
        canvas.restoreState()

    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    buffer.seek(0)
    return buffer.getvalue()


def get_transactions_query(
    db: Session,
    sid: Optional[int] = None,
    sys: Optional[str] = None,
    bank: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    terms: Optional[List[str]] = Query(None),
    years: Optional[List[int]] = Query(None)
):
    q = db.query(Transaction, Student).join(Student, Transaction.student_id == Student.id)
    if sid:
        q = q.filter(Transaction.student_id == sid)
    if sys:
        q = q.filter(Transaction.reference_no.ilike(f"%{sys}%"))
    if bank:
        q = q.filter(Transaction.description.ilike(f"%{bank}%"))
    if start_date and end_date:
        q = q.filter(Transaction.entry_date.between(start_date, end_date))
    if terms and len(terms) > 0:
        q = q.filter(Transaction.term.in_(terms))
    if years and len(years) > 0:
        q = q.filter(Transaction.academic_year.in_(years))
    
    return q.order_by(Transaction.entry_date.asc()).limit(5000).all()


@router.get("/search")
async def search_statement(
    sid: Optional[int] = None,
    sys: Optional[str] = None,
    bank: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    terms: Optional[List[str]] = Query(None),
    years: Optional[List[int]] = Query(None),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    rows = get_transactions_query(db, sid, sys, bank, start_date, end_date, terms, years)
    
    results = []
    total_debit = 0
    total_credit = 0
    
    is_staff = current_user.role in ['Admin', 'Editor']
    for t, s in rows:
        total_debit += t.debit
        total_credit += t.credit
        row = {
            "Student ID": s.id, "Name": s.name, "College": s.college,
            "Is Sponsored": s.is_sponsored, "Sponsor Name": s.sponsor_name, 
            "Sibling ID": s.sibling_id, "General Notes": s.general_notes,
            "Ref No": t.reference_no, "Date": t.entry_date.isoformat() if hasattr(t.entry_date, 'isoformat') else str(t.entry_date),
            "Term": t.term, "Year": t.academic_year,
            "Type": t.transaction_type, "Description": t.description,
            "Debit": t.debit, "Credit": t.credit,
        }
        if is_staff:
            row["Internal Note"] = t.internal_note
        results.append(row)
        
    net_balance = total_debit - total_credit
    
    return {
        "transactions": results,
        "metrics": {
            "total_debit": total_debit,
            "total_credit": total_credit,
            "net_balance": net_balance
        }
    }


@router.get("/pdf")
async def download_statement_pdf(
    sid: Optional[int] = None,
    sys: Optional[str] = None,
    bank: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    terms: Optional[List[str]] = Query(None),
    years: Optional[List[int]] = Query(None),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not sid:
        raise HTTPException(status_code=400, detail="Student ID is required to generate a PDF statement.")
        
    rows = get_transactions_query(db, sid, sys, bank, start_date, end_date, terms, years)
    if not rows:
        raise HTTPException(status_code=404, detail="No transactions found")
        
    total_d = sum(t.debit for t, _ in rows)
    total_c = sum(t.credit for t, _ in rows)
    net = total_d - total_c
    student_name = rows[0][1].name
    student_college = rows[0][1].college
    
    pdf_bytes = create_landscape_pdf(sid, student_name, student_college, rows, net, total_d, total_c)
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="SOA_{sid}.pdf"'}
    )


@router.get("/excel")
async def download_statement_excel(
    sid: Optional[int] = None,
    sys: Optional[str] = None,
    bank: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    terms: Optional[List[str]] = Query(None),
    years: Optional[List[int]] = Query(None),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    rows = get_transactions_query(db, sid, sys, bank, start_date, end_date, terms, years)
    if not rows:
        raise HTTPException(status_code=404, detail="No transactions found")
        
    is_staff = current_user.role in ['Admin', 'Editor']
    data = []
    for t, s in rows:
        row = {
            "Student ID": s.id, "Name": s.name, "College": s.college,
            "Is Sponsored": s.is_sponsored, "Sponsor Name": s.sponsor_name, 
            "Sibling ID": s.sibling_id, "General Notes": s.general_notes,
            "Ref No": t.reference_no, "Date": t.entry_date, "Term": t.term, "Year": t.academic_year,
            "Type": t.transaction_type, "Description": t.description,
            "Debit": t.debit, "Credit": t.credit,
        }
        if is_staff:
            row["Internal Note"] = t.internal_note
        data.append(row)
        
    df = pd.DataFrame(data)
    
    total_d = sum(t.debit for t, _ in rows)
    total_c = sum(t.credit for t, _ in rows)
    
    total_row = {
        "Student ID":"","Name":"","College":"","Is Sponsored":"","Sponsor Name":"",
        "Sibling ID":"","General Notes":"","Ref No":"","Date":"","Term":"","Year":"",
        "Type":"","Description":"TOTALS","Debit":total_d,"Credit":total_c,
    }
    if is_staff:
        total_row["Internal Note"] = ""
        
    df.loc[len(df)] = total_row
    
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="SOA_{sid or "Search"}.xlsx"'}
    )
