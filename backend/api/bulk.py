import io
import datetime
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session

from models import get_db, Student, Transaction, write_audit, next_ref_block
from api.auth import get_current_user
from config import VALID_TERMS, DEFAULT_YEAR, MAX_BULK_ROWS
from helpers import build_auto_discount_transactions

router = APIRouter()

BULK_TYPES = [
    "Bulk Payments",
    "Bulk Invoices (Tuition)",
    "Bulk Other Fees",
    "Credit Hours Adjustments",
    "Update Student Rates",
    "General Adjustments",
]

TEMPLATES = {
    "Bulk Payments":            {"ID":0,"Bank Name":"Bank","Bank Ref":"REF","Amount":0.0,"Date":"2026-04-17","Term":"Spring","Year":DEFAULT_YEAR},
    "Bulk Invoices (Tuition)":  {"ID":0,"Hours":15.0,"Date":"2026-04-17","Term":"Spring","Year":DEFAULT_YEAR},
    "Bulk Other Fees":          {"ID":0,"Fee Amount":1500.0,"Description":"Bus","Date":"2026-04-17","Term":"Spring","Year":DEFAULT_YEAR},
    "Credit Hours Adjustments": {"ID":0,"Hours_Delta":3.0,"Date":"2026-04-17","Term":"Spring","Year":DEFAULT_YEAR},
    "Update Student Rates":     {"ID":0,"New_Price_Per_Hr":5500.0},
    "General Adjustments":      {"ID":0,"Debit":0.0,"Credit":0.0,"Date":"2026-04-17","Term":"Spring","Year":DEFAULT_YEAR,"Description":"note"},
}

def _safe_float(val, default=0.0) -> float:
    try:
        if pd.isna(val) or val is None:
            return default
        return float(str(val).replace(",","").strip())
    except Exception:
        return default

@router.get("/template/{b_type}")
async def get_template(b_type: str):
    if b_type not in TEMPLATES:
        raise HTTPException(status_code=400, detail="Invalid template type.")
        
    df = pd.DataFrame([TEMPLATES[b_type]])
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="Tpl_{b_type}.xlsx"'}
    )

@router.post("/upload")
async def process_bulk_upload(
    b_type: str = Form(...),
    file: UploadFile = File(...),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if b_type not in BULK_TYPES:
        raise HTTPException(status_code=400, detail="Invalid bulk type.")
        
    try:
        contents = await file.read()
        df_raw = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read Excel file: {e}")
        
    df_raw.columns = [str(c).strip() for c in df_raw.columns]
    
    for col in ["Amount","Hours","Hours_Delta","Fee Amount","Debit","Credit","New_Price_Per_Hr"]:
        if col in df_raw.columns:
            df_raw[col] = pd.to_numeric(
                df_raw[col].astype(str).str.replace(",","").str.strip(), errors="coerce"
            ).fillna(0.0)
            
    if len(df_raw) > MAX_BULK_ROWS:
        raise HTTPException(status_code=400, detail=f"File has {len(df_raw)} rows — limit is {MAX_BULK_ROWS}. Split the file.")
        
    batch_id = f"BCH-{datetime.datetime.now().strftime('%y%m%d-%H%M%S')}"
    total = len(df_raw)
    
    all_students = {s.id: s.price_per_hr for s in db.query(Student).all()}
    failed = []
    success = 0
    
    if b_type == "Update Student Rates":
        for i, row in df_raw.iterrows():
            rid = int(row.get("ID", 0)) if pd.notnull(row.get("ID")) else 0
            orig = row.to_dict()
            if rid <= 0 or rid not in all_students:
                orig["Error Reason"] = "Invalid or unregistered ID"
                failed.append(orig)
            else:
                try:
                    db.query(Student).filter(Student.id == rid).update({"price_per_hr": _safe_float(row.get("New_Price_Per_Hr"))})
                    success += 1
                except Exception as e:
                    orig["Error Reason"] = str(e)
                    failed.append(orig)
                    
        if success > 0:
            write_audit(db, current_user.username, "BULK_RATE_UPDATE", "batch", f"{success} students updated")
            db.commit()
            
    else:
        start = next_ref_block(db, total * 2 + 100)
        ctr = start
        txns = []
        
        for i, row in df_raw.iterrows():
            sid = int(row.get("ID", 0)) if pd.notnull(row.get("ID")) else 0
            orig = row.to_dict()
            
            if sid <= 0 or sid not in all_students:
                orig["Error Reason"] = "Invalid or unregistered ID"
                failed.append(orig)
                continue
                
            rt = all_students[sid]
            dr = cr = h_change = 0.0
            term_v = str(row.get("Term", VALID_TERMS[1]))
            year_v = int(row.get("Year", DEFAULT_YEAR)) if pd.notnull(row.get("Year")) else DEFAULT_YEAR
            raw_desc = str(row.get("Description", "")).strip()
            dsc = b_type if not raw_desc or raw_desc in ("0", "0.0", "nan") else raw_desc
            
            if b_type == "Bulk Payments":
                pfx = "PAY"
                cr = _safe_float(row.get("Amount"))
                dsc = f"Bank: {row.get('Bank Name', '')} | Ref: {row.get('Bank Ref', '')}"
            elif b_type == "Bulk Invoices (Tuition)":
                pfx = "INV"
                h_change = _safe_float(row.get("Hours", 15.0))
                dr = h_change * rt
                dsc = f"Tuition Invoice ({h_change} CH)"
            elif b_type == "Bulk Other Fees":
                pfx = "INV"
                dr = _safe_float(row.get("Fee Amount"))
                dsc = raw_desc or "Other Fee"
            elif b_type == "Credit Hours Adjustments":
                pfx = "ADJ"
                h_change = _safe_float(row.get("Hours_Delta"))
                v = abs(h_change * rt)
                dr, cr = (v, 0.0) if h_change > 0 else (0.0, v)
                dsc = f"Adj {h_change} CH"
            elif b_type == "General Adjustments":
                pfx = "TXN"
                dr = _safe_float(row.get("Debit"))
                cr = _safe_float(row.get("Credit"))
                
            entry_date = pd.to_datetime(row.get("Date", datetime.datetime.now()), errors="coerce")
            entry_date = entry_date.date() if pd.notna(entry_date) else datetime.datetime.now().date()
            
            try:
                main_tx = Transaction(
                    reference_no=f"{pfx}-{ctr:06d}",
                    batch_id=batch_id,
                    student_id=sid,
                    transaction_type=b_type,
                    description=dsc,
                    debit=dr, credit=cr,
                    hours_change=h_change,
                    entry_date=entry_date,
                    term=term_v,
                    academic_year=year_v,
                )
                txns.append(main_tx)
                ctr += 1
                success += 1
                
                if b_type in ("Bulk Invoices (Tuition)", "Credit Hours Adjustments"):
                    inv_amt = dr if b_type == "Bulk Invoices (Tuition)" else abs(h_change * rt)
                    discounts = build_auto_discount_transactions(
                        db, sid, inv_amt, term_v, year_v, entry_date,
                        ref_start=ctr, batch_id=batch_id,
                    )
                    if b_type == "Credit Hours Adjustments" and h_change < 0:
                        for t in discounts:
                            t.debit, t.credit = t.credit, t.debit
                    txns.extend(discounts)
                    ctr += len(discounts)
            except Exception as e:
                orig["Error Reason"] = str(e)
                failed.append(orig)
                
        if txns:
            try:
                db.bulk_save_objects(txns)
                write_audit(db, current_user.username, "BULK_TX", batch_id, f"{b_type} | {success} rows | batch={batch_id}")
                db.commit()
            except Exception as e:
                db.rollback()
                raise HTTPException(status_code=500, detail=f"Database error during bulk save: {str(e)}")
                
    return {
        "success_count": success,
        "failed_count": len(failed),
        "failed_rows": failed,
        "batch_id": batch_id
    }
