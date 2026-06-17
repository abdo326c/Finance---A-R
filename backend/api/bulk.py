import io
import datetime
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session

from models import get_db, Student, StudentStatus, StudentScholarship, ScholarshipType, Transaction, FinancialStatusHistory, write_audit, next_ref_block, get_static_lookups
from api.auth import get_current_user
from config import VALID_TERMS, DEFAULT_YEAR, MAX_BULK_ROWS
from helpers import build_auto_discount_transactions, get_semester_rank

router = APIRouter()

BULK_TYPES = [
    "Bulk Payments",
    "Bulk Invoices (Tuition)",
    "Bulk Other Fees",
    "Credit Hours Adjustments",
    "Update Student Rates",
    "General Adjustments",
    "Bulk Academic Status",
    "Bulk Financial Status",
    "Bulk Siblings",
    "Bulk Sponsors",
]

TEMPLATES = {
    "Bulk Payments":            {"ID":0,"Bank Name":"Bank","Bank Ref":"REF","Amount":0.0,"Date":"2026-04-17","Term":"Spring","Year":DEFAULT_YEAR},
    "Bulk Invoices (Tuition)":  {"ID":0,"Hours":15.0,"Date":"2026-04-17","Term":"Spring","Year":DEFAULT_YEAR},
    "Bulk Other Fees":          {"ID":0,"Fee Amount":1500.0,"Description":"Bus","Date":"2026-04-17","Term":"Spring","Year":DEFAULT_YEAR},
    "Credit Hours Adjustments": {"ID":0,"Hours_Delta":3.0,"Date":"2026-04-17","Term":"Spring","Year":DEFAULT_YEAR},
    "Update Student Rates":     {"ID":0,"New_Price_Per_Hr":5500.0},
    "General Adjustments":      {"ID":0,"Debit":0.0,"Credit":0.0,"Date":"2026-04-17","Term":"Spring","Year":DEFAULT_YEAR,"Description":"note"},
    "Bulk Academic Status":     {"ID":0,"Academic_Status":"Active","Term":"Spring","Year":DEFAULT_YEAR},
    "Bulk Financial Status":    {"ID":0,"Financial_Status":"Financial Hold","Comment":"Missing tuition","Term":"Spring","Year":DEFAULT_YEAR},
    "Bulk Siblings":            {"ID":0,"Sibling_ID":26100123},
    "Bulk Sponsors":            {"ID":0,"Is_Sponsored":"Yes","Sponsor_Name":"Ministry of Education"},
}

def _safe_float(val, default=0.0) -> float:
    try:
        if pd.isna(val) or val is None:
            return default
        return float(str(val).replace(",","").strip())
    except Exception:
        return default

@router.get("/template/{b_type}")
async def get_template(b_type: str, current_user = Depends(get_current_user)):
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

    elif b_type == "Bulk Academic Status":
        histories = []
        for i, row in df_raw.iterrows():
            rid = int(row.get("ID", 0)) if pd.notnull(row.get("ID")) else 0
            orig = row.to_dict()
            if rid <= 0 or rid not in all_students:
                orig["Error Reason"] = "Invalid or unregistered ID"
                failed.append(orig)
            else:
                try:
                    term_v = str(row.get("Term", VALID_TERMS[1]))
                    year_v = int(row.get("Year", DEFAULT_YEAR)) if pd.notnull(row.get("Year")) else DEFAULT_YEAR
                    status_v = str(row.get("Academic_Status", "Active")).strip()
                    
                    db.query(StudentStatus).filter_by(student_id=rid, term=term_v, academic_year=year_v).delete()
                    
                    history = StudentStatus(
                        student_id=rid,
                        status=status_v,
                        term=term_v,
                        academic_year=year_v,
                    )
                    histories.append(history)
                    success += 1
                except Exception as e:
                    orig["Error Reason"] = str(e)
                    failed.append(orig)
        
        if success > 0:
            db.add_all(histories)
            write_audit(db, current_user.username, "BULK_STATUS_UPDATE", "batch", f"{success} statuses updated")
            db.commit()

    elif b_type == "Bulk Financial Status":
        histories = []
        for i, row in df_raw.iterrows():
            rid = int(row.get("ID", 0)) if pd.notnull(row.get("ID")) else 0
            orig = row.to_dict()
            if rid <= 0 or rid not in all_students:
                orig["Error Reason"] = "Invalid or unregistered ID"
                failed.append(orig)
            else:
                try:
                    term_v = str(row.get("Term", VALID_TERMS[1]))
                    year_v = int(row.get("Year", DEFAULT_YEAR)) if pd.notnull(row.get("Year")) else DEFAULT_YEAR
                    status_v = str(row.get("Financial_Status", "Good Standing")).strip()
                    comment_v = str(row.get("Comment", "")).strip()
                    
                    history = FinancialStatusHistory(
                        student_id=rid,
                        status=status_v,
                        comment=comment_v,
                        term=term_v,
                        academic_year=year_v,
                        created_by=current_user.username
                    )
                    histories.append(history)
                    success += 1
                except Exception as e:
                    orig["Error Reason"] = str(e)
                    failed.append(orig)
        
        if success > 0:
            db.add_all(histories)
            write_audit(db, current_user.username, "BULK_FIN_STATUS_UPDATE", "batch", f"{success} financial statuses updated")
            db.commit()

    else:
        from sqlalchemy import func
        max_schs = db.query(func.count(StudentScholarship.id)).filter(
            StudentScholarship.is_active == True
        ).group_by(StudentScholarship.student_id).order_by(
            func.count(StudentScholarship.id).desc()
        ).limit(1).scalar() or 1
        
        start = next_ref_block(db, total * (1 + max_schs) + 100)
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
            
            if b_type == "Bulk Invoices (Tuition)":
                latest_status = db.query(FinancialStatusHistory).filter_by(student_id=sid).order_by(FinancialStatusHistory.created_at.desc()).first()
                if latest_status and latest_status.status == "Financial Hold":
                    hold_rank = get_semester_rank(latest_status.term, latest_status.academic_year)
                    inv_rank = get_semester_rank(term_v, year_v)
                    if inv_rank > hold_rank:
                        orig["Error Reason"] = f"Financial Hold from {latest_status.term} {latest_status.academic_year}"
                        failed.append(orig)
                        continue
                        
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
                get_static_lookups.cache_clear()
            except Exception as e:
                db.rollback()
                raise HTTPException(status_code=500, detail=f"Database error during bulk save: {str(e)}")
                
    return {
        "success_count": success,
        "failed_count": len(failed),
        "failed_rows": failed,
        "batch_id": batch_id
    }


import json

@router.post("/power-campus/preview")
async def preview_power_campus(
    file: UploadFile = File(...),
    filters: str = Form(...),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        filter_data = json.loads(filters)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid filters JSON")

    contents = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")

    # Ensure required columns exist
    required_cols = ["PEOPLE_ORG_ID", "AMOUNT", "SUMMARY_TYPE", "CHARGE_CREDIT_TYPE", "VOID_FLAG", "CRG_CRD_DESC", "CHARGE_CREDIT_CODE"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"CSV missing required columns: {', '.join(missing)}")

    # Apply VOID_FLAG filter unconditionally
    df = df[df["VOID_FLAG"] != "Y"]

    # Apply user filters
    if filter_data.get("term"):
        df = df[df["ACADEMIC_TERM"] == filter_data["term"]]
    if filter_data.get("year"):
        df = df[df["ACADEMIC_YEAR"] == int(filter_data["year"])]
    if filter_data.get("chargeType"):
        df = df[df["CHARGE_CREDIT_TYPE"] == filter_data["chargeType"]]
    if filter_data.get("summaryType"):
        df = df[df["SUMMARY_TYPE"] == filter_data["summaryType"]]
    if filter_data.get("chargeCode"):
        df = df[df["CHARGE_CREDIT_CODE"] == filter_data["chargeCode"]]

    if filter_data.get("startDate") and filter_data.get("endDate"):
        try:
            sd = pd.to_datetime(filter_data["startDate"]).date()
            ed = pd.to_datetime(filter_data["endDate"]).date()
            df["_parsed_date"] = pd.to_datetime(df["ENTRY_DATE"], errors="coerce").dt.date
            df = df[(df["_parsed_date"] >= sd) & (df["_parsed_date"] <= ed)]
        except Exception:
            pass

    # Fetch all students and scholarships mapping
    students = {s.id: s for s in db.query(Student).all()}
    scholarship_types = {s.name.strip().lower(): s.id for s in db.query(ScholarshipType).all()}
    
    # Extract unique CHARGECREDITNUMBERs and RECEIPT_NUMBERs already in DB to prevent duplicates
    existing_ccs = set(r[0] for r in db.query(Transaction.pc_charge_credit_number).filter(Transaction.pc_charge_credit_number.isnot(None)).all())
    existing_rcs = set(r[0] for r in db.query(Transaction.pc_receipt_number).filter(Transaction.pc_receipt_number.isnot(None)).all())

    # Pre-calculate TUIT sum per student in the CSV for scholarship percentage calculation
    tuit_df = df[df["SUMMARY_TYPE"] == "TUIT"]
    student_tuit_sums = tuit_df.groupby("PEOPLE_ORG_ID")["AMOUNT"].sum().to_dict()

    valid_rows = []
    skipped_rows = []
    summary_counts = {}

    for i, row in df.iterrows():
        orig = row.to_dict()
        sid = int(row.get("PEOPLE_ORG_ID", 0)) if pd.notna(row.get("PEOPLE_ORG_ID")) else 0
        cc_num = str(row.get("CHARGECREDITNUMBER", "")).strip()
        rc_num = str(row.get("RECEIPT_NUMBER", "")).strip()
        amt = float(row.get("AMOUNT", 0.0))
        c_type = str(row.get("CHARGE_CREDIT_TYPE", "")).strip()
        s_type = str(row.get("SUMMARY_TYPE", "")).strip()
        c_code = str(row.get("CHARGE_CREDIT_CODE", "")).strip()
        desc = str(row.get("CRG_CRD_DESC", "")).strip()
        
        # Increment summary count
        summary_counts[s_type] = summary_counts.get(s_type, 0) + 1

        if cc_num and cc_num in existing_ccs:
            orig["Error Reason"] = "Duplicate: CHARGECREDITNUMBER already exists in DB"
            skipped_rows.append(orig)
            continue
        if rc_num and rc_num in existing_rcs:
            orig["Error Reason"] = "Duplicate: RECEIPT_NUMBER already exists in DB"
            skipped_rows.append(orig)
            continue
            
        if sid not in students:
            orig["Error Reason"] = f"Student ID {sid} not found in database"
            skipped_rows.append(orig)
            continue

        student = students[sid]
        
        # Prepare valid row payload
        valid_row = {
            "csv_row_index": i,
            "student_id": sid,
            "student_name": student.name,
            "pc_charge_credit_number": cc_num if cc_num else None,
            "pc_receipt_number": rc_num if rc_num else None,
            "entry_date": str(row.get("ENTRY_DATE", "")),
            "term": str(row.get("ACADEMIC_TERM", "")),
            "academic_year": int(row.get("ACADEMIC_YEAR", 0)) if pd.notna(row.get("ACADEMIC_YEAR")) else 0,
            "summary_type": s_type,
            "charge_credit_type": c_type,
            "amount": amt,
            "raw_desc": desc,
            "charge_code": c_code,
            "scholarship_type_id": None,
            "scholarship_percentage": None
        }

        # TUIT Logic
        if s_type == "TUIT":
            if not student.price_per_hr or student.price_per_hr <= 0:
                orig["Error Reason"] = f"Student missing price_per_hr in DB"
                skipped_rows.append(orig)
                continue
            ch = round(amt / student.price_per_hr, 2)
            valid_row["computed_desc"] = f"Tuition: {ch} CH @ {student.price_per_hr}"
            valid_row["hours_change"] = ch
            valid_row["transaction_type"] = "Invoice"

        # BANK / Payment Logic
        elif s_type == "BANK" or c_type == "R":
            valid_row["computed_desc"] = f"Bank: {c_code} | Ref: {desc}"
            valid_row["hours_change"] = 0.0
            valid_row["transaction_type"] = "Payment Receipt"

        # SCHL Logic
        elif s_type == "SCHL":
            # Map by matching charge code or description
            matched_id = scholarship_types.get(c_code.lower()) or scholarship_types.get(desc.lower())
            if not matched_id:
                # Provide a generic fallback or skip. We will skip for safety.
                orig["Error Reason"] = f"Unmapped Scholarship Code: {c_code} / {desc}"
                skipped_rows.append(orig)
                continue
            
            valid_row["scholarship_type_id"] = matched_id
            
            # Calculate Percentage
            csv_tuition = student_tuit_sums.get(sid, 0.0)
            if csv_tuition > 0:
                pct = round((amt / csv_tuition) * 100, 2)
            else:
                # Fallback to DB tuition (requires calculating from existing DB transactions for this term/year)
                db_tuition = db.query(func.sum(Transaction.debit)).filter(
                    Transaction.student_id == sid,
                    Transaction.term == valid_row["term"],
                    Transaction.academic_year == valid_row["academic_year"],
                    Transaction.transaction_type.in_(["Invoice", "Bulk Invoices (Tuition)"])
                ).scalar() or 0.0
                
                if db_tuition > 0:
                    pct = round((amt / db_tuition) * 100, 2)
                else:
                    orig["Error Reason"] = f"Cannot calculate SCHL %: No tuition found in CSV or DB"
                    skipped_rows.append(orig)
                    continue

            valid_row["scholarship_percentage"] = min(pct, 100.0)
            valid_row["computed_desc"] = desc
            valid_row["hours_change"] = 0.0
            valid_row["transaction_type"] = "Discount"

        # General/Other Logic
        else:
            valid_row["computed_desc"] = desc
            valid_row["hours_change"] = 0.0
            valid_row["transaction_type"] = "Invoice" if c_type == "C" else "Adjustment"

        valid_rows.append(valid_row)

    return {
        "valid_rows": valid_rows,
        "skipped_rows": skipped_rows,
        "summary_counts": summary_counts
    }


from pydantic import BaseModel
from typing import List, Optional

class PCCommitRow(BaseModel):
    student_id: int
    pc_charge_credit_number: Optional[str]
    pc_receipt_number: Optional[str]
    entry_date: str
    term: str
    academic_year: int
    charge_credit_type: str
    amount: float
    computed_desc: str
    hours_change: float
    transaction_type: str
    summary_type: str
    scholarship_type_id: Optional[int]
    scholarship_percentage: Optional[float]

class PCCommitRequest(BaseModel):
    rows: List[PCCommitRow]

@router.post("/power-campus/commit")
async def commit_power_campus(
    req: PCCommitRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not req.rows:
        raise HTTPException(status_code=400, detail="No rows to commit")

    batch_id = f"PC-BULK-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Get max ref for generating our own ref numbers
    from sqlalchemy import func
    max_id = db.query(func.max(Transaction.id)).scalar() or 0
    start_ref = max_id + 100
    
    txns = []
    scholarships_to_add = []
    
    for i, row in enumerate(req.rows):
        # Determine PFX based on transaction type
        if row.transaction_type == "Invoice": pfx = "INV"
        elif row.transaction_type == "Payment Receipt": pfx = "PAY"
        elif row.transaction_type == "Discount": pfx = "SCH"
        else: pfx = "TXN"
        
        dr = row.amount if row.charge_credit_type == "C" else 0.0
        cr = row.amount if row.charge_credit_type == "R" else 0.0
        
        entry_dt = pd.to_datetime(row.entry_date, errors="coerce").date() if row.entry_date else datetime.datetime.now().date()
        
        txn = Transaction(
            reference_no=f"{pfx}-{(start_ref + i):06d}",
            batch_id=batch_id,
            student_id=row.student_id,
            scholarship_type_id=row.scholarship_type_id,
            transaction_type=row.transaction_type,
            description=row.computed_desc,
            hours_change=row.hours_change,
            debit=dr,
            credit=cr,
            entry_date=entry_dt,
            term=row.term,
            academic_year=row.academic_year,
            pc_charge_credit_number=row.pc_charge_credit_number,
            pc_receipt_number=row.pc_receipt_number
        )
        txns.append(txn)
        
        if row.summary_type == "SCHL" and row.scholarship_type_id and row.scholarship_percentage:
            # Check if student already has this scholarship active
            existing_sch = db.query(StudentScholarship).filter_by(
                student_id=row.student_id,
                scholarship_type_id=row.scholarship_type_id,
                term=row.term,
                academic_year=row.academic_year
            ).first()
            
            if existing_sch:
                existing_sch.is_active = True
                existing_sch.percentage = row.scholarship_percentage
            else:
                scholarships_to_add.append(
                    StudentScholarship(
                        student_id=row.student_id,
                        scholarship_type_id=row.scholarship_type_id,
                        percentage=row.scholarship_percentage,
                        term=row.term,
                        academic_year=row.academic_year,
                        is_active=True,
                        internal_note=f"Imported from {batch_id}"
                    )
                )

    try:
        db.bulk_save_objects(txns)
        if scholarships_to_add:
            db.bulk_save_objects(scholarships_to_add)
            
        write_audit(db, current_user.username, "BULK_PC_SYNC", batch_id, f"Synced {len(txns)} transactions")
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Commit failed: {str(e)}")

    return {"message": "Success", "batch_id": batch_id, "imported_count": len(txns)}
