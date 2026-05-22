# pdf_utils.py
# ─────────────────────────────────────────────
# PDF statement generator (fpdf2)
# ─────────────────────────────────────────────
from fpdf import FPDF
from datetime import datetime
import pandas as pd


class _PDFStatement(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 9)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, "Nile University Finance Department  ||  Accounts Receivable Team  ||  Confidential", 0, 0, "C")


def create_pdf(
    sid: int,
    student_name: str,
    df: pd.DataFrame,
    net_balance: float,
    total_debit: float,
    total_credit: float,
) -> bytes:
    pdf = _PDFStatement(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    
    # Enable automatic page breaks
    pdf.set_auto_page_break(auto=True, margin=15)

    # ── Colors ──
    NAVY = (13, 71, 161)
    LIGHT_GRAY = (245, 247, 250)
    DARK_TEXT = (31, 41, 55)
    BORDER_COLOR = (220, 224, 230)
    
    # ── Header ──
    pdf.set_text_color(*NAVY)
    pdf.set_font("helvetica", "B", 18)
    pdf.cell(0, 10, "Nile University - Statement of Account", ln=True, align="L")
    
    # Decorative line under title
    pdf.set_draw_color(*NAVY)
    pdf.set_line_width(0.8)
    pdf.line(10, 22, 287, 22)
    pdf.ln(5)
    
    # Reset line width
    pdf.set_line_width(0.2)

    # Student information block (Left side)
    pdf.set_text_color(*DARK_TEXT)
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(32, 6, "Student Name:", 0, 0, "L")
    pdf.set_font("helvetica", "", 11)
    pdf.cell(100, 6, f"{student_name}", 0, 1, "L")
    
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(32, 6, "Student ID:", 0, 0, "L")
    pdf.set_font("helvetica", "", 11)
    pdf.cell(100, 6, f"{sid}", 0, 1, "L")
    
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(32, 6, "Statement Date:", 0, 0, "L")
    pdf.set_font("helvetica", "", 11)
    pdf.cell(100, 6, f"{datetime.now().strftime('%d-%b-%Y %I:%M %p')}", 0, 1, "L")
    
    # ── Dynamic Status Stamp (Top Right) ──
    # Save current coordinates
    curr_x, curr_y = pdf.get_x(), pdf.get_y()
    
    # Draw stamp position
    stamp_x, stamp_y = 220, 25
    pdf.set_xy(stamp_x, stamp_y)
    
    if net_balance <= 0:
        stamp_text = "FULLY PAID"
        fill_color = (212, 237, 218)     # Soft green
        border_color = (40, 167, 69)      # Strong green
        text_color = (21, 87, 36)        # Dark green text
    else:
        stamp_text = "OUTSTANDING DUE"
        fill_color = (248, 215, 218)     # Soft red
        border_color = (220, 53, 69)      # Strong red
        text_color = (114, 28, 36)       # Dark red text

    pdf.set_fill_color(*fill_color)
    pdf.set_draw_color(*border_color)
    pdf.set_text_color(*text_color)
    pdf.set_font("helvetica", "B", 11)
    pdf.set_line_width(0.4)
    # Render stamp box (width=67, height=12)
    pdf.cell(67, 12, stamp_text, border=1, ln=1, align="C", fill=True)
    
    # Restore coordinates for main layout
    pdf.set_line_width(0.2)
    pdf.set_xy(10, 48)

    # ── Table Header ──
    headers = ["Ref No", "Date", "Term", "Year", "Type", "Description", "Debit", "Credit"]
    widths  = [30, 25, 20, 15, 35, 92, 30, 30] # sum = 277mm (perfect fit on A4 landscape with 10mm margins)

    pdf.set_fill_color(*NAVY)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 10)
    pdf.set_draw_color(*NAVY)
    for head, width in zip(headers, widths):
        pdf.cell(width, 10, head, 1, 0, "C", True)
    pdf.ln()

    # ── Table Body (with Alternating Rows) ──
    pdf.set_text_color(*DARK_TEXT)
    pdf.set_draw_color(*BORDER_COLOR)
    
    for i, (_, row) in enumerate(df.iterrows()):
        # Alternate row fill
        use_fill = i % 2 == 1
        if use_fill:
            pdf.set_fill_color(*LIGHT_GRAY)
            
        pdf.set_font("helvetica", "", 9)
        pdf.cell(30, 8, str(row["Ref No"]),           1, 0, "C", use_fill)
        pdf.cell(25, 8, str(row["Date"]),             1, 0, "C", use_fill)
        pdf.cell(20, 8, str(row["Term"]),             1, 0, "C", use_fill)
        pdf.cell(15, 8, str(row["Year"]),             1, 0, "C", use_fill)
        pdf.cell(35, 8, str(row["Type"])[:18],        1, 0, "L", use_fill)
        pdf.cell(92, 8, str(row["Description"])[:55], 1, 0, "L", use_fill)
        
        # Color specific formatting for Debit / Credit amounts
        # Clean amount string to check if it's non-zero
        try:
            debit_val = float(str(row["Debit"]).replace(",", "").strip())
        except ValueError:
            debit_val = 0.0
            
        try:
            credit_val = float(str(row["Credit"]).replace(",", "").strip())
        except ValueError:
            credit_val = 0.0
        
        pdf.cell(30, 8, f"{debit_val:,.2f}" if debit_val > 0 else "—", 1, 0, "R", use_fill)
        pdf.cell(30, 8, f"{credit_val:,.2f}" if credit_val > 0 else "—", 1, 1, "R", use_fill)

    # ── Table Totals ──
    pdf.set_font("helvetica", "B", 10)
    pdf.set_fill_color(235, 240, 250)
    pdf.set_draw_color(*NAVY)
    pdf.cell(217, 9, "TOTALS",                      1, 0, "R", True)
    pdf.cell(30,  9, f"{total_debit:,.2f}",         1, 0, "R", True)
    pdf.cell(30,  9, f"{total_credit:,.2f}",        1, 1, "R", True)
    pdf.ln(6)

    # ── Summary Block ──
    pdf.set_font("helvetica", "B", 13)
    if net_balance <= 0:
        pdf.set_text_color(21, 87, 36) # Dark green
        balance_text = f"ACCOUNT FULLY PAID (Credit Balance: {abs(net_balance):,.2f} EGP)" if net_balance < 0 else "ACCOUNT FULLY BALANCED (0.00 EGP)"
    else:
        pdf.set_text_color(114, 28, 36) # Dark red
        balance_text = f"OUTSTANDING NET BALANCE DUE: {net_balance:,.2f} EGP"
        
    pdf.cell(0, 10, balance_text, ln=True, align="R")

    return bytes(pdf.output())
