from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from pydantic import BaseModel
from typing import Optional, List
from datetime import date

from models import get_db, Student, Transaction, RefCounter, StudentScholarship, ScholarshipType, next_ref_block, write_audit
from helpers import build_auto_discount_transactions
from api.auth import get_current_user

router = APIRouter()

class TransactionRequest(BaseModel):
    action_type: str
    student_id: int
    date: date
    term: str
    year: int
    bypass_dup: bool = False
    
    # Action specific fields
    bank_name: Optional[str] = None
    bank_ref: Optional[str] = None
    amount_paid: Optional[float] = 0.0
    
    reg_hours: Optional[float] = 0.0
    description: Optional[str] = ""
    
    hours_delta: Optional[float] = 0.0
    fee_amount: Optional[float] = 0.0
    
    debit: Optional[float] = 0.0
    credit: Optional[float] = 0.0
    
    internal_note: Optional[str] = ""

@router.get("/preview/{student_id}")
def preview_student(
    student_id: int, 
    term: str = Query(...), 
    year: int = Query(...), 
    db: Session = Depends(get_db), 
    current_user=Depends(get_current_user)
):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    schs = db.query(StudentScholarship, ScholarshipType).join(ScholarshipType).filter(
        StudentScholarship.student_id == student.id,
        StudentScholarship.term == term,
        StudentScholarship.academic_year == year,
        StudentScholarship.is_active == True
    ).all()
    
    scholarships = []
    for ss, st_type in schs:
        scholarships.append({
            "name": st_type.name,
            "percentage": ss.percentage,
            "internal_note": ss.internal_note
        })
        
    return {
        "id": student.id,
        "name": student.name,
        "college": student.college,
        "program": student.program,
        "price_per_hr": student.price_per_hr or 0.0,
        "scholarships": scholarships
    }

@router.post("/transaction")
def process_transaction(
    req: TransactionRequest, 
    db: Session = Depends(get_db), 
    current_user=Depends(get_current_user)
):
    student = db.get(Student, req.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    # Sync ref counter
    max_tx_id = db.query(func.max(Transaction.id)).scalar() or 0
    ref_row = db.get(RefCounter, 1)
    if ref_row and ref_row.seq <= max_tx_id:
        ref_row.seq = max_tx_id + 500
        db.flush()
        
    rate = student.price_per_hr or 0.0
    extra_txs = []
    action = req.action_type
    
    dr, cr, dsc, h_change = 0.0, 0.0, req.description, 0.0
    pfx = "TXN"
    
    if action == "Payment Receipt":
        pfx = "PAY"
        dsc = f"Bank: {req.bank_name} | Ref: {req.bank_ref}"
        cr = req.amount_paid
        
    elif action == "Invoice":
        pfx = "INV"
        h_change = req.reg_hours
        val = req.reg_hours * rate
        dr, cr = val, 0.0
        dsc = f"Tuition: {h_change} CH @ {rate:,.2f} | {req.description}"
        
        start = next_ref_block(db, 1 + 50)
        extra_txs = build_auto_discount_transactions(
            db, req.student_id, val, req.term, req.year, req.date, ref_start=start+1
        )
        
    elif action == "Credit Hours Adjustment":
        existing_hours = db.query(func.sum(Transaction.hours_change)).filter(
            Transaction.student_id == req.student_id,
            Transaction.term == req.term,
            Transaction.academic_year == req.year
        ).scalar() or 0.0
        
        if existing_hours <= 0:
            raise HTTPException(status_code=400, detail=f"Cannot process adjustment: Student has NO registered hours in {req.term} {req.year}.")
            
        if req.hours_delta < 0 and abs(req.hours_delta) > existing_hours:
            raise HTTPException(status_code=400, detail=f"Invalid Adjustment: Trying to drop {abs(req.hours_delta)} hours, but student only has {existing_hours} hours in {req.term} {req.year}.")
            
        pfx = "ADJ"
        h_change = req.hours_delta
        val = abs(h_change * rate)
        dr, cr = (val, 0.0) if h_change > 0 else (0.0, val)
        dsc = f"Adj: {h_change} CH @ {rate:,.2f}"
        start = next_ref_block(db, 1 + 50)
        extra_txs = build_auto_discount_transactions(
            db, req.student_id, val, req.term, req.year, req.date, ref_start=start+1
        )
        if h_change < 0:
            for t in extra_txs:
                t.debit, t.credit = t.credit, t.debit
                
    elif action == "Other Fees":
        pfx = "FEE"
        dr = req.fee_amount
        
    elif action == "General Adjustment":
        pfx = "TXN"
        dr = req.debit
        cr = req.credit
        
    if action not in ["Credit Hours Adjustment", "Invoice"]:
        start = next_ref_block(db, 1)
        
    check_val = dr if dr > 0 else cr
    if not req.bypass_dup and check_val > 0:
        dup = db.query(Transaction).filter(
            Transaction.student_id == req.student_id,
            Transaction.transaction_type == action,
            Transaction.entry_date == req.date,
            (Transaction.debit == check_val) | (Transaction.credit == check_val),
        ).first()
        if dup:
            raise HTTPException(status_code=409, detail=f"Duplicate: a {action} of {check_val:,.2f} EGP was already posted today for this student. Enable 'Bypass Duplicate Check' to force it.")
            
    new_tx = Transaction(
        reference_no = f"{pfx}-{start:06d}",
        student_id = req.student_id,
        transaction_type = action,
        description = dsc,
        internal_note = req.internal_note,
        debit = dr, credit = cr,
        hours_change = h_change,
        entry_date = req.date,
        term = req.term,
        academic_year = req.year
    )
    db.add(new_tx)
    for t in extra_txs:
        db.add(t)
        
    write_audit(
        db, current_user.username,
        "POST_TX", f"student_id={req.student_id}",
        f"{action} | {new_tx.reference_no} | dr={dr} cr={cr}"
    )
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database Integrity Error: Reference Number conflict.")
        
    suffix = f" + {len(extra_txs)} auto-discount(s)" if extra_txs else ""
    return {"message": f"Posted {new_tx.reference_no} for {student.name}{suffix}!"}
