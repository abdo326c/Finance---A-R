import io
import datetime
import pandas as pd
import polars as pl
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from models import get_db, Student, Transaction, write_audit, next_ref_block, DisputeLog
from api.auth import get_current_user

router = APIRouter()

def map_term_name(term):
    t = str(term).strip().upper()
    if "SPRING" in t or "SPRG" in t:
        return "SPRG"
    if "FALL" in t:
        return "FALL"
    if "SUMMER" in t or "SUMR" in t:
        return "SUMR"
    return t

@router.post("/analyze")
async def analyze_reconciliation(
    file: UploadFile = File(...),
    target_term: str = Form(...),
    target_year: int = Form(...),
    recon_mode: str = Form(...),
    cohort_scope: str = Form(...),
    pay_cutoff: Optional[str] = Form(None),
    enable_charge_date: bool = Form(False),
    charge_cutoff: Optional[str] = Form(None),
    id_col: str = Form(...),
    fname_col: str = Form(...),
    lname_col: str = Form(...),
    type_col: str = Form(...),
    amount_col: str = Form(...),
    date_col: str = Form(...),
    desc_col: str = Form(...),
    code_col: str = Form(...),
    term_col: str = Form(...),
    year_col: str = Form(...),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        content = await file.read()
        if file.filename.endswith(".csv"):
            df_ext = None
            for enc in ['utf-8', 'utf-8-sig', 'windows-1256', 'cp1252', 'latin1', 'iso-8859-1']:
                try:
                    df_ext = pd.read_csv(io.BytesIO(content), encoding=enc)
                    break
                except:
                    continue
            if df_ext is None:
                df_ext = pd.read_csv(io.BytesIO(content))
        else:
            df_ext = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")

    df_pl = pl.from_pandas(df_ext)
    
    # Ensure proper types
    df_pl = df_pl.with_columns([
        pl.col(id_col).cast(pl.String).str.replace(".0", "", literal=True).str.strip_chars(),
        pl.col(amount_col).cast(pl.Float64, strict=False).fill_null(0.0),
        pl.col(type_col).cast(pl.String).str.to_uppercase().str.strip_chars()
    ])
    
    target_pc_term = map_term_name(target_term)

    charges_discounts_mask = (
        (pl.col(type_col).is_in(['C', 'D'])) &
        (pl.col(term_col).cast(pl.String).map_elements(map_term_name, return_dtype=pl.String) == target_pc_term) &
        (pl.col(year_col).cast(pl.String).str.contains(str(target_year)))
    )
    
    if enable_charge_date and charge_cutoff:
        try:
            cutoff_date = datetime.datetime.strptime(charge_cutoff, "%Y-%m-%d").date()
            df_pl = df_pl.with_columns(pl.col(date_col).cast(pl.Datetime, strict=False).cast(pl.Date, strict=False))
            charges_discounts_mask = charges_discounts_mask & (pl.col(date_col) >= cutoff_date)
        except:
            pass

    payments_mask = (pl.col(type_col) == 'R')
    if pay_cutoff:
        try:
            cutoff_date = datetime.datetime.strptime(pay_cutoff, "%Y-%m-%d").date()
            df_pl = df_pl.with_columns(pl.col(date_col).cast(pl.Datetime, strict=False).cast(pl.Date, strict=False))
            payments_mask = payments_mask & (pl.col(date_col) >= cutoff_date)
        except:
            pass

    df_charges_discounts = df_pl.filter(charges_discounts_mask)
    df_payments = df_pl.filter(payments_mask)
    df_filtered = pl.concat([df_charges_discounts, df_payments], how="vertical")

    if df_filtered.is_empty():
        return {"matched": [], "mismatched": [], "missing_local": [], "missing_ext": [], "message": "No matching records"}

    ext_students = {}
    for row in df_filtered.iter_rows(named=True):
        sid = str(row[id_col])
        tx_type = row[type_col]
        amt = float(row[amount_col])
        
        f_name = str(row.get(fname_col, "")) if fname_col in row and row[fname_col] is not None else ""
        l_name = str(row.get(lname_col, "")) if lname_col in row and row[lname_col] is not None else ""
        full_name = f"{f_name} {l_name}".replace("  ", " ").strip()
        
        code_val = str(row[code_col]) if code_col in row and row[code_col] is not None else ""
        desc_val = str(row[desc_col]) if desc_col in row and row[desc_col] is not None else ""
        tx_date = row[date_col]
        
        if sid not in ext_students:
            ext_students[sid] = {
                "name": full_name or f"Student {sid}",
                "charges": 0.0, "discounts": 0.0, "payments": 0.0,
                "transactions": []
            }
        
        ext_students[sid]["transactions"].append({
            "type": tx_type, "amount": amt, "code": code_val, "desc": desc_val, "date": str(tx_date)
        })

        if tx_type == 'C':
            ext_students[sid]["charges"] += amt
        elif tx_type == 'D':
            ext_students[sid]["discounts"] += amt
        elif tx_type == 'R':
            ext_students[sid]["payments"] += amt

    for sid, details in ext_students.items():
        details["net_balance"] = details["charges"] - details["discounts"] - details["payments"]

    local_active_student_ids = {str(s.id) for s in db.query(Student.id).all()}
    
    is_local_only = "Active Local Student" in cohort_scope
    if is_local_only:
        ext_students = {sid: data for sid, data in ext_students.items() if sid in local_active_student_ids}

    local_students = {}
    db_txs = (
        db.query(Transaction, Student)
        .join(Student, Transaction.student_id == Student.id)
        .filter(Transaction.term == target_term, Transaction.academic_year == target_year)
        .all()
    )
    
    for tx, student in db_txs:
        sid_str = str(student.id)
        if sid_str not in local_students:
            local_students[sid_str] = {
                "name": student.name,
                "charges": 0.0, "discounts": 0.0, "payments": 0.0,
                "transactions": []
            }
            
        local_students[sid_str]["transactions"].append({
            "type": tx.transaction_type,
            "debit": float(tx.debit),
            "credit": float(tx.credit),
            "desc": tx.description,
            "date": str(tx.entry_date)
        })
        
        if tx.debit > 0:
            local_students[sid_str]["charges"] += float(tx.debit)
        elif tx.credit > 0:
            if tx.transaction_type in ['Discount', 'Bulk Scholarships']:
                local_students[sid_str]["discounts"] += float(tx.credit)
            else:
                local_students[sid_str]["payments"] += float(tx.credit)

    for sid_str, details in local_students.items():
        details["net_balance"] = details["charges"] - details["discounts"] - details["payments"]

    matched_list = []
    mismatch_list = []
    missing_local_list = []
    missing_ext_list = []
    
    # Fetch dispute statuses in bulk
    disputes = {str(d.student_id): {"is_disputed": d.is_disputed, "notes": d.notes} for d in db.query(DisputeLog).all()}

    for sid, ext_data in ext_students.items():
        ext_bal = ext_data["net_balance"]
        disp = disputes.get(sid, {"is_disputed": False, "notes": ""})
        
        if sid in local_students:
            loc_data = local_students[sid]
            loc_bal = loc_data["net_balance"]
            diff = ext_bal - loc_bal
            
            record = {
                "student_id": sid,
                "name": ext_data["name"],
                "pc_charges": ext_data["charges"],
                "pc_discounts": ext_data["discounts"],
                "pc_payments": ext_data["payments"],
                "pc_balance": ext_bal,
                "loc_charges": loc_data["charges"],
                "loc_discounts": loc_data["discounts"],
                "loc_payments": loc_data["payments"],
                "loc_balance": loc_bal,
                "discrepancy": diff,
                "is_disputed": disp["is_disputed"],
                "dispute_notes": disp["notes"],
                "ext_transactions": ext_data["transactions"],
                "loc_transactions": loc_data["transactions"]
            }
            
            if abs(diff) < 0.01:
                matched_list.append(record)
            else:
                mismatch_list.append(record)
        else:
            missing_local_list.append({
                "student_id": sid,
                "name": ext_data["name"],
                "pc_charges": ext_data["charges"],
                "pc_discounts": ext_data["discounts"],
                "pc_payments": ext_data["payments"],
                "pc_balance": ext_bal,
                "ext_transactions": ext_data["transactions"],
            })

    for sid, loc_data in local_students.items():
        if sid not in ext_students:
            missing_ext_list.append({
                "student_id": sid,
                "name": loc_data["name"],
                "loc_charges": loc_data["charges"],
                "loc_discounts": loc_data["discounts"],
                "loc_payments": loc_data["payments"],
                "loc_balance": loc_data["net_balance"],
                "loc_transactions": loc_data["transactions"]
            })

    return {
        "matched": matched_list,
        "mismatched": mismatch_list,
        "missing_local": missing_local_list,
        "missing_ext": missing_ext_list
    }

class DisputeRequest(BaseModel):
    is_disputed: bool
    notes: str

@router.post("/dispute/{student_id}")
async def update_dispute(
    student_id: int,
    req: DisputeRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    entry = db.query(DisputeLog).filter_by(student_id=student_id).first()
    if entry:
        entry.is_disputed = req.is_disputed
        entry.notes = req.notes
        entry.updated_by = current_user
    else:
        db.add(DisputeLog(
            student_id=student_id,
            is_disputed=req.is_disputed,
            notes=req.notes,
            updated_by=current_user
        ))
    write_audit(db, current_user, "RECON_DISPUTE_UPDATE", f"student_id={student_id}", f"Disputed={req.is_disputed}")
    db.commit()
    return {"message": "Dispute updated"}

class ResolveRequest(BaseModel):
    student_id: int
    term: str
    year: int
    amount: float
    description: str = "Reconciliation Adjustment"

@router.post("/resolve/{action}")
async def resolve_discrepancy(
    action: str,
    req: ResolveRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    student = db.query(Student).filter_by(id=req.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found in local DB.")
        
    start_ref_num = next_ref_block(db, 1)
    
    if action == "payment":
        new_ref_no = f"PAY-{start_ref_num:06d}"
        tx_type = "Payment"
        debit, credit = 0.0, req.amount
    elif action == "charge":
        new_ref_no = f"INV-{start_ref_num:06d}"
        tx_type = "Invoice"
        debit, credit = req.amount, 0.0
    elif action == "discount":
        new_ref_no = f"DSC-{start_ref_num:06d}"
        tx_type = "Discount"
        debit, credit = 0.0, req.amount
    elif action == "adjustment":
        new_ref_no = f"ADJ-{start_ref_num:06d}"
        tx_type = "Adjustment"
        if req.amount > 0:
            debit, credit = req.amount, 0.0
        else:
            debit, credit = 0.0, abs(req.amount)
    else:
        raise HTTPException(status_code=400, detail="Invalid action.")
        
    tx = Transaction(
        reference_no=new_ref_no,
        batch_id="RECONCILIATION",
        student_id=req.student_id,
        transaction_type=tx_type,
        description=req.description,
        internal_note="Reconciliation Engine Resolution",
        debit=debit,
        credit=credit,
        hours_change=0.0,
        entry_date=datetime.date.today(),
        term=req.term,
        academic_year=req.year
    )
    db.add(tx)
    write_audit(db, current_user, f"RECON_RESOLVE_{action.upper()}", f"student_id={req.student_id}", f"Amount={req.amount}")
    db.commit()
    return {"message": "Resolution applied successfully"}
