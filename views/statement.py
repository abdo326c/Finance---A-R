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
    """توليد ملف PDF احترافي Landscape مع طابع الدفع الممتاز والتصميم الفاخر"""
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
    for t, _ in rows:
        t_name = f"{t.term} {t.academic_year}"
        if t_name not in unique_terms:
            unique_terms.append(t_name)
    terms_display = " | ".join(unique_terms) if unique_terms else "All Terms"
    
    story.append(Paragraph("Nile University - Finance Department", title_style))
    story.append(Paragraph("Official Student Statement of Account", subtitle_style))
    story.append(Spacer(1, 5))
    
    # ── 1. Student Info Box (Left) ──
    info_text = f"""<b>Student Name:</b> {student_name}<br/>
<b>Student ID:</b> {student_id}<br/>
<b>College:</b> {student_college}<br/>
<b>Statement Date:</b> {datetime.date.today().strftime('%d %B %Y')}<br/>
<b>Included Terms:</b> {terms_display}"""
    
    info_p = Paragraph(info_text, normal_style)
    story.append(info_p)
    story.append(Spacer(1, 20))
    
    # ── 2. Table Data Construction ──
    table_data = [["Date", "Reference", "Type", "Description", "Term / Year", "Debit (EGP)", "Credit (EGP)"]]
    
    for t, _ in rows:
        tx_date = t.entry_date.strftime("%Y-%m-%d") if hasattr(t.entry_date, 'strftime') else str(t.entry_date)
        type_p = Paragraph(t.transaction_type, cell_style)
        desc_p = Paragraph(t.description or "", cell_style)
        
        debit_str = f"{t.debit:,.2f}" if t.debit > 0 else "—"
        credit_str = f"{t.credit:,.2f}" if t.credit > 0 else "—"
        
        table_data.append([
            tx_date,
            t.reference_no,
            type_p,
            desc_p,
            f"{t.term} {t.academic_year}",
            debit_str,
            credit_str
        ])
    
    # Totals Row
    table_data.append(["", "", "", "", "Totals:", f"{total_d:,.2f}", f"{total_c:,.2f}"])
    
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
    for idx in range(1, len(rows) + 1):
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

    # 🟢 التعديل: إضافة Internal Note و Sibling ID لملف الإكسيل فقط، ومخفية في الواجهة والـ PDF
    df = pd.DataFrame([{
        "Student ID": s.id, "Name": s.name, "College": s.college,
        "Is Sponsored": s.is_sponsored, "Sponsor Name": s.sponsor_name, 
        "Sibling ID": s.sibling_id, "General Notes": s.general_notes,
        "Ref No": t.reference_no, "Date": t.entry_date, "Term": t.term, "Year": t.academic_year,
        "Type": t.transaction_type, "Description": t.description,
        "Internal Note": t.internal_note, # 🟢 عمود النوتس الداخلي
        "Debit": t.debit, "Credit": t.credit,
    } for t, s in rows])

    # 🟢 نعرض الداتا الأساسية في شاشة السيستم بس عشان الزحمة (نفس شكل الـ PDF تقريباً)
    st.dataframe(df[["Student ID", "Name", "Ref No", "Date", "Term", "Year", "Type", "Description", "Debit", "Credit"]], 
                 use_container_width=True, 
                 column_config={
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

        from helpers import run_in_background

        b1, b2 = st.columns(2)
        with b1:
            fut_key = f"pdf_future_{p['sid']}"
            if st.button("⚙️ Generate PDF Statement", use_container_width=True, type="secondary", key=f"gen_pdf_{p['sid']}"):
                st.session_state[fut_key] = run_in_background(
                    create_landscape_pdf, p["sid"], student_name, student_college, rows, net, total_d, total_c
                )
                st.toast("PDF generation started...", icon="⏳")
                st.rerun()

            fut = st.session_state.get(fut_key)
            if fut:
                if fut.done():
                    try:
                        pdf_bytes = fut.result()
                        st.download_button("📄 Download PDF Statement", pdf_bytes,
                                           file_name=f"SOA_{p['sid']}.pdf", use_container_width=True, type="primary",
                                           key=f"dl_pdf_statement_{p['sid']}_{net}")
                    except Exception as e:
                        st.error(f"Error generating PDF: {e}")
                else:
                    st.markdown("<div class='skeleton' style='height:40px; width:100%; border-radius:8px; margin-top:0px;'></div>", unsafe_allow_html=True)
        with b2:
            df_xl = df.copy()
            df_xl.loc[len(df_xl)] = {
                "Student ID":"","Name":"","College":"","Is Sponsored":"","Sponsor Name":"",
                "Sibling ID":"","General Notes":"","Ref No":"","Date":"","Term":"","Year":"",
                "Type":"","Description":"TOTALS","Internal Note":"","Debit":total_d,"Credit":total_c,
            }
            buf = io.BytesIO()
            df_xl.to_excel(buf, index=False)
            st.download_button("📗 Download Excel Sheet", buf.getvalue(),
                               file_name=f"SOA_{p['sid']}.xlsx", use_container_width=True)
