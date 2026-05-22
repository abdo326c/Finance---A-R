# pages/statement.py
import io
import datetime
import pandas as pd
import streamlit as st

from config import VALID_TERMS
from models import get_db, Transaction, Student

# استيراد أدوات بناء الـ PDF للـ Landscape مع الـ Footer
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def create_landscape_pdf(student_id, student_name, student_college, rows, current_balance, total_d, total_c):
    """توليد ملف PDF احترافي Landscape مع مربع مجاميع ملموم"""
    buffer = io.BytesIO()
    
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=40)
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=22, textColor=colors.HexColor("#004a99"), spaceAfter=12)
    subtitle_style = ParagraphStyle('DocSubtitle', parent=styles['Heading3'], fontSize=12, textColor=colors.HexColor("#555555"), spaceAfter=15)
    normal_style = ParagraphStyle('DocNormal', parent=styles['Normal'], fontSize=10, spaceAfter=6)
    cell_style = ParagraphStyle('CellText', parent=styles['Normal'], fontSize=9, leading=12)
    
    unique_terms = []
    for t, _ in rows:
        t_name = f"{t.term} {t.academic_year}"
        if t_name not in unique_terms:
            unique_terms.append(t_name)
    terms_display = " | ".join(unique_terms) if unique_terms else "All Terms"
    
    story.append(Paragraph("Nile University - Finance Department", title_style))
    story.append(Paragraph(f"Official Statement of Account", subtitle_style))
    story.append(Spacer(1, 10))
    
    story.append(Paragraph(f"<b>Student Name:</b> {student_name}", normal_style))
    story.append(Paragraph(f"<b>Student ID:</b> {student_id}", normal_style))
    story.append(Paragraph(f"<b>College:</b> {student_college}", normal_style))
    story.append(Paragraph(f"<b>Statement Date:</b> {datetime.date.today().strftime('%d %B %Y')}", normal_style))
    story.append(Paragraph(f"<b>Included Terms:</b> {terms_display}", normal_style))
    story.append(Spacer(1, 15))
    
    table_data = [["Date", "Reference", "Type", "Description", "Term / Year", "Debit (EGP)", "Credit (EGP)"]]
    
    for t, _ in rows:
        tx_date = t.entry_date.strftime("%Y-%m-%d") if hasattr(t.entry_date, 'strftime') else str(t.entry_date)
        type_p = Paragraph(t.transaction_type, cell_style)
        desc_p = Paragraph(t.description or "", cell_style)
        
        table_data.append([
            tx_date,
            t.reference_no,
            type_p,
            desc_p,
            f"{t.term} {t.academic_year}",
            f"{t.debit:,.2f}" if t.debit > 0 else "0.00",
            f"{t.credit:,.2f}" if t.credit > 0 else "0.00"
        ])
    
    # 🟢 نقلنا المجاميع للعمود الخامس عشان المربع يبقى قد الكلمة والأرقام بس
    table_data.append(["", "", "", "", "Totals:", f"{total_d:,.2f}", f"{total_c:,.2f}"])
    
    # 🟢 نقلنا الرصيد النهائي للعمود الخامس برضه
    table_data.append(["", "", "", "", "Net Balance Due:", f"{current_balance:,.2f} EGP", ""])
    
    # وسعنا العمود الخامس (90) على حساب الرابع عشان كلمة Net Balance تاخد راحتها
    t = Table(table_data, colWidths=[70, 85, 95, 192, 90, 100, 100])
    
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#004a99")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('ALIGN', (5,0), (6,-1), 'RIGHT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('TOPPADDING', (0,0), (-1,0), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        
        ('GRID', (0,0), (-1,-3), 0.5, colors.lightgrey),
        
        # 🟢 تنسيق مربع الـ Totals (يبدأ من العمود 4 اللي هو الخامس فعلياً)
        ('ALIGN', (4,-2), (4,-2), 'RIGHT'), 
        ('BACKGROUND', (4,-2), (-1,-2), colors.HexColor("#f5f5f5")),
        ('FONTNAME', (4,-2), (-1,-2), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (4,-2), (-1,-2), 8),
        ('TOPPADDING', (4,-2), (-1,-2), 8),
        ('BOX', (4,-2), (-1,-2), 1, colors.black),
        ('INNERGRID', (4,-2), (-1,-2), 0.5, colors.grey),
        
        # 🟢 تنسيق مربع الـ Net Balance 
        ('ALIGN', (4,-1), (4,-1), 'RIGHT'),
        ('SPAN', (5,-1), (6,-1)), # دمج خليتين للرصيد
        ('ALIGN', (5,-1), (6,-1), 'CENTER'),
        ('BACKGROUND', (4,-1), (-1,-1), colors.HexColor("#d4edda")),
        ('FONTNAME', (4,-1), (-1,-1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (4,-1), (-1,-1), colors.HexColor("#155724")),
        ('BOTTOMPADDING', (4,-1), (-1,-1), 10),
        ('TOPPADDING', (4,-1), (-1,-1), 10),
        ('BOX', (4,-1), (-1,-1), 1, colors.black),
        ('INNERGRID', (4,-1), (-1,-1), 0.5, colors.grey),
    ]))
    
    story.append(t)
    
    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica-Bold', 10)
        canvas.setFillColor(colors.HexColor("#004a99"))
        footer_text = "Finance Department | A/R Team ♥"
        canvas.drawCentredString(doc.pagesize[0]/2, 20, footer_text)
        canvas.restoreState()

    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    buffer.seek(0)
    return buffer.getvalue()


def render(engine, available_years):
    st.subheader("Transaction Search & Statement of Account")
    st.markdown("💡 Leave Student ID blank and enter a Bank Ref or System Ref to search globally.")

    if "stmt_params" not in st.session_state:
        st.session_state["stmt_params"] = None

    with st.form("stmt_search_form", clear_on_submit=False):
        c1, c2, c3 = st.columns(3)
        default_id = str(st.session_state.get("lookup_id","")) if st.session_state.get("lookup_id",0)>0 else ""
        sid_raw        = c1.text_input("Student ID", value=default_id, placeholder="e.g. 26100123")
        sys_ref        = c2.text_input("System Ref No", placeholder="e.g. INV-004751")
        bank_ref       = c3.text_input("Bank Ref / Description", placeholder="e.g. 12345 or CIB")
        f1, f2, f3     = st.columns(3)
        date_range     = f1.date_input("Date Range", [])
        sel_terms      = f2.multiselect("Terms", VALID_TERMS)
        sel_years      = f3.multiselect("Years", available_years)
        if st.form_submit_button("🔍 Search Transactions"):
            st.session_state["stmt_params"] = {
                "sid":   int(sid_raw) if sid_raw.strip().isdigit() else 0,
                "sys":   sys_ref, "bank": bank_ref,
                "dates": date_range,
                "terms": sel_terms, "years": sel_years,
            }

    p = st.session_state.get("stmt_params")
    if not p:
        return
    if not any([p["sid"]>0, p["sys"], p["bank"], len(p["dates"])==2, p["terms"], p["years"]]):
        return

    with get_db() as db:
        q = db.query(Transaction, Student).join(Student, Transaction.student_id == Student.id)
        if p["sid"]  > 0:          q = q.filter(Transaction.student_id == p["sid"])
        if p["sys"]:               q = q.filter(Transaction.reference_no.ilike(f"%{p['sys']}%"))
        if p["bank"]:              q = q.filter(Transaction.description.ilike(f"%{p['bank']}%"))
        if len(p["dates"]) == 2:   q = q.filter(Transaction.entry_date.between(*p["dates"]))
        if p["terms"]:             q = q.filter(Transaction.term.in_(p["terms"]))
        if p["years"]:             q = q.filter(Transaction.academic_year.in_(p["years"]))

        rows = q.order_by(Transaction.entry_date.asc()).limit(5000).all()

    if not rows:
        st.warning("⚠️ No transactions found matching these criteria.")
        return

    df = pd.DataFrame([{
        "Student ID": s.id, "Name": s.name, "Ref No": t.reference_no,
        "Date": t.entry_date, "Term": t.term, "Year": t.academic_year,
        "Type": t.transaction_type, "Description": t.description,
        "Debit": t.debit, "Credit": t.credit,
    } for t, s in rows])

    st.dataframe(df, use_container_width=True, column_config={
        "Debit":  st.column_config.NumberColumn(format="%,.2f"),
        "Credit": st.column_config.NumberColumn(format="%,.2f"),
    })

    if p["sid"] > 0:
        total_d = sum(t.debit  for t, _ in rows)
        total_c = sum(t.credit for t, _ in rows)
        net     = total_d - total_c
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Debit",     f"{total_d:,.2f} EGP")
        m2.metric("Total Credit",    f"{total_c:,.2f} EGP")
        m3.metric("Net Balance Due", f"{net:,.2f} EGP")

        student_name = rows[0][1].name
        student_college = rows[0][1].college

        b1, b2 = st.columns(2)
        with b1:
            pdf_bytes = create_landscape_pdf(p["sid"], student_name, student_college, rows, net, total_d, total_c)
            st.download_button("📄 Download PDF Statement", pdf_bytes,
                               file_name=f"SOA_{p['sid']}.pdf", use_container_width=True, type="primary")
        with b2:
            df_xl = df.copy()
            df_xl.loc[len(df_xl)] = {
                "Student ID":"","Name":"","Ref No":"","Date":"","Term":"","Year":"",
                "Type":"","Description":"TOTALS","Debit":total_d,"Credit":total_c,
            }
            buf = io.BytesIO()
            df_xl.to_excel(buf, index=False)
            st.download_button("📗 Download Excel Sheet", buf.getvalue(),
                               file_name=f"SOA_{p['sid']}.xlsx", use_container_width=True)
