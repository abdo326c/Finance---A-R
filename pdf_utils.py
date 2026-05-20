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
        self.set_font("helvetica", "I", 10)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, "Finance Department  ||  A/R Team", 0, 0, "C")


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

    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 15, "Nile University - Student Statement of Account", ln=True, align="C")

    pdf.set_font("helvetica", "", 11)
    pdf.cell(0, 7, f"Student: {student_name} ({sid})", ln=True, align="L")
    pdf.cell(0, 7, f"Report Date: {datetime.now().strftime('%d-%b-%Y')}", ln=True, align="L")
    pdf.ln(5)

    headers = ["Ref No", "Date", "Term", "Year", "Type", "Description", "Debit", "Credit"]
    widths  = [30, 25, 20, 15, 35, 90, 30, 30]

    pdf.set_fill_color(52, 73, 94)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 10)
    for head, width in zip(headers, widths):
        pdf.cell(width, 10, head, 1, 0, "C", True)
    pdf.ln()

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "", 9)
    for _, row in df.iterrows():
        pdf.cell(30, 8, str(row["Ref No"]),           1)
        pdf.cell(25, 8, str(row["Date"]),             1)
        pdf.cell(20, 8, str(row["Term"]),             1)
        pdf.cell(15, 8, str(row["Year"]),             1)
        pdf.cell(35, 8, str(row["Type"])[:18],        1)
        pdf.cell(90, 8, str(row["Description"])[:55], 1)
        pdf.cell(30, 8, str(row["Debit"]).replace(",",""),  1, 0, "R")
        pdf.cell(30, 8, str(row["Credit"]).replace(",",""), 1, 1, "R")

    pdf.set_font("helvetica", "B", 9)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(215, 8, "TOTALS",                      1, 0, "R", True)
    pdf.cell(30,  8, f"{total_debit:,.2f}",         1, 0, "R", True)
    pdf.cell(30,  8, f"{total_credit:,.2f}",        1, 1, "R", True)
    pdf.ln(8)

    pdf.set_font("helvetica", "B", 14)
    pdf.cell(0, 10, f"NET BALANCE: {net_balance:,.2f} EGP", ln=True, align="R")

    return bytes(pdf.output())
