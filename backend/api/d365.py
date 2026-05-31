import io
import datetime
import pandas as pd
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from models import get_db, Transaction, Student
from api.auth import get_current_user

router = APIRouter()

@router.get("/export")
async def generate_d365_export(
    term: str,
    year: int,
    tx_type_filter: str,
    last_fti: str,
    invoice_date: str,
    due_date: str,
    revenue_account: Optional[str] = None,
    discount_account: Optional[str] = None,
    posting_profile: str = "STD",
    currency_code: str = "EGP",
    customer_ref: str = "",
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if tx_type_filter in ["All (Tuition Invoices & Discounts)", "Tuition Invoices Only"] and not revenue_account:
        raise HTTPException(status_code=400, detail="Please provide a Revenue Ledger Account.")
    if tx_type_filter in ["All (Tuition Invoices & Discounts)", "Discounts Only (Scholarships)"] and not discount_account:
        raise HTTPException(status_code=400, detail="Please provide a Discount Ledger Account.")
        
    if not last_fti or '-' not in last_fti:
        raise HTTPException(status_code=400, detail="Invalid FTI Number format (e.g. FTI-0012133).")
        
    try:
        prefix, num_str = last_fti.rsplit('-', 1)
        fti_counter = int(num_str)
        num_length = len(num_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="The part after the hyphen must be a number.")
        
    query = db.query(Transaction, Student).join(Student, Transaction.student_id == Student.id)
    query = query.filter(Transaction.term == term, Transaction.academic_year == year)
    
    if tx_type_filter == "Tuition Invoices Only":
        query = query.filter(Transaction.transaction_type.in_(['Invoice', 'Bulk Invoices (Tuition)']))
    elif tx_type_filter == "Discounts Only (Scholarships)":
        query = query.filter(Transaction.transaction_type.in_(['Discount', 'Bulk Scholarships']))
    elif tx_type_filter == "Other Fees Only":
        query = query.filter(Transaction.transaction_type.in_(['Other Fees', 'Bulk Other Fees']))
    elif tx_type_filter == "Adjustments Only":
        query = query.filter(Transaction.transaction_type.in_(['Adjustment', 'Bulk Adjustments']))
    else: 
        query = query.filter(Transaction.transaction_type.in_(['Invoice', 'Bulk Invoices (Tuition)', 'Discount', 'Bulk Scholarships']))
        
    results = query.order_by(Transaction.id).all()
    
    if not results:
        raise HTTPException(status_code=404, detail="No matching transactions found.")
        
    d365_data = []
    for idx, (tx, student) in enumerate(results, start=1):
        is_discount = tx.transaction_type in ['Discount', 'Bulk Scholarships']
        is_other_fee = tx.transaction_type in ['Other Fees', 'Bulk Other Fees']
        is_adjustment = tx.transaction_type in ['Adjustment', 'Bulk Adjustments']
        
        if is_discount:
            amount = -tx.credit
            target_ledger = discount_account or ""
        elif is_other_fee:
            amount = tx.debit
            target_ledger = ""
        elif is_adjustment:
            if tx.debit > 0:
                amount = tx.debit
            else:
                amount = -tx.credit
            target_ledger = ""
        else: 
            amount = tx.debit
            target_ledger = revenue_account or ""
            
        if amount == 0:
            continue
            
        fti_counter += 1
        current_fti = f"{prefix}-{str(fti_counter).zfill(num_length)}"
        student_id_str = str(student.id).zfill(9)
        
        dim_val = getattr(student, 'financial_dimension', None)
        if not dim_val or str(dim_val).lower() == 'nan':
            dim_val = f"Academic||||||||{student.college}|{student.program if student.program else ''}|{student_id_str}|{tx.term}|"
            
        d365_row = {
            "FREETEXTNUMBER": current_fti,
            "LINENUMBER": 1, 
            "AMOUNTCUR": amount,
            "CURRENCYCODE": currency_code,
            "CUSTOMERACCOUNT": student_id_str,
            "CUSTOMERREFERENCE": customer_ref,
            "DEFAULTDIMENSIONDISPLAYVALUE": dim_val,
            "DESCRIPTION": tx.description,
            "DOCUMENTDATE": invoice_date,
            "DUEDATE": due_date,
            "HEADERDEFAULTDIMENSIONDISPLAYVALUE": dim_val,
            "INVOICEACCOUNT": student_id_str,
            "INVOICEDATE": invoice_date,
            "LEDGERDIMENSIONDISPLAYVALUE": target_ledger, 
            "POSTINGPROFILE": posting_profile,
            "QUANTITY": 1,
            "UNITPRICE": amount
        }
        d365_data.append(d365_row)
        
    if not d365_data:
        raise HTTPException(status_code=404, detail="No valid invoice lines could be generated.")
        
    df = pd.DataFrame(d365_data)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Customer_free_text_invoice')
        
    buf.seek(0)
    
    headers = {
        'Content-Disposition': f'attachment; filename="Customer_free_text_invoice_{datetime.date.today()}.xlsx"'
    }
    return StreamingResponse(buf, headers=headers, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
