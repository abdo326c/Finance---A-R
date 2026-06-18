from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import date
import pandas as pd
import io

from models import get_db, Student, write_audit, get_static_lookups
from api.auth import get_current_user
from api.lookups import get_db_config_list
from config import VALID_COLLEGES, DEFAULT_YEAR

router = APIRouter()

class RegisterStudentRequest(BaseModel):
    id: int
    name: str
    college: str
    program: Optional[str] = None
    price_per_hr: float
    email: Optional[str] = None
    mobile: Optional[str] = None
    national_id: Optional[str] = None
    nationality: str = "Egyptian"
    birth_date: Optional[date] = None
    admit_year: int = DEFAULT_YEAR

@router.post("/")
async def register_student(req: RegisterStudentRequest, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["Admin", "Editor"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
        
    valid_colleges = get_db_config_list(db, "VALID_COLLEGES", VALID_COLLEGES)
    if req.college not in valid_colleges:
        raise HTTPException(status_code=400, detail=f"Invalid college code. Must be one of: {', '.join(valid_colleges)}")
        
    existing = db.get(Student, req.id)
    if existing:
        raise HTTPException(status_code=400, detail=f"Student ID {req.id} already exists")
        
    new_student = Student(
        id=req.id,
        name=req.name,
        college=req.college,
        program=req.program,
        price_per_hr=req.price_per_hr,
        email=req.email,
        mobile=req.mobile,
        national_id=req.national_id,
        nationality=req.nationality,
        admit_year=req.admit_year,
        birth_date=req.birth_date
    )
    
    db.add(new_student)
    write_audit(db, current_user.username, "REGISTER_STUDENT", f"student_id={req.id}", req.name)
    db.commit()
    get_static_lookups.cache_clear()
    
    return {"message": f"Student '{req.name}' registered successfully"}

@router.post("/bulk")
async def bulk_register(file: UploadFile = File(...), current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["Admin", "Editor"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
        
    contents = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(contents))
        df.columns = [str(c).strip() for c in df.columns]
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to read bulk registration Excel file: {e}")
        raise HTTPException(status_code=400, detail="Invalid Excel file format")
        
    valid_colleges = get_db_config_list(db, "VALID_COLLEGES", VALID_COLLEGES)
    existing_students = {s.id: s for s in db.query(Student).all()}
    
    new_students = []
    updated_count = 0
    failed = []
    
    for i, row in df.iterrows():
        # Support both 'ID' and 'Student ID' headers
        raw_id = row.get("Student ID", row.get("ID", 0))
        sid = int(raw_id) if pd.notna(raw_id) else 0
        orig = row.to_dict()
        college = str(row.get("College", "")).strip().upper()
        
        if sid <= 0:
            orig["Error Reason"] = "Invalid ID"
            failed.append(orig)
            continue
            
        if college not in valid_colleges:
            orig["Error Reason"] = f"Invalid college '{college}'"
            failed.append(orig)
            continue
            
        bd = pd.to_datetime(row.get("Birth Date"), errors="coerce")
        price = float(row.get("Price / Hr (EGP)", row.get("Price Per Hr", 0.0)))
        is_sponsored_raw = row.get("Is Sponsored", False)
        is_sponsored = str(is_sponsored_raw).strip().lower() in ["true", "yes", "1", "y"] if pd.notna(is_sponsored_raw) else False
        sponsor = str(row.get("Sponsor Name", "")).strip() if pd.notna(row.get("Sponsor Name")) else None
        notes = str(row.get("General Notes", "")).strip() if pd.notna(row.get("General Notes")) else None
        
        sib_raw = row.get("Sibling ID")
        sib_id = int(sib_raw) if pd.notna(sib_raw) and str(sib_raw).strip() != "" else None
        
        if sid in existing_students:
            st = existing_students[sid]
            changed = False
            
            def set_if_changed(obj, attr, new_val):
                if getattr(obj, attr) != new_val:
                    setattr(obj, attr, new_val)
                    return True
                return False

            changed |= set_if_changed(st, "name", str(row.get("Name", st.name)))
            changed |= set_if_changed(st, "college", college)
            changed |= set_if_changed(st, "program", str(row.get("Program", st.program)))
            changed |= set_if_changed(st, "price_per_hr", price)
            
            if pd.notna(row.get("Email")): changed |= set_if_changed(st, "email", str(row.get("Email")))
            if pd.notna(row.get("Mobile")): changed |= set_if_changed(st, "mobile", str(row.get("Mobile")))
            if pd.notna(row.get("National ID")): changed |= set_if_changed(st, "national_id", str(row.get("National ID")))
            if pd.notna(row.get("Nationality")): changed |= set_if_changed(st, "nationality", str(row.get("Nationality")))
            if pd.notna(row.get("Admit Year")): changed |= set_if_changed(st, "admit_year", int(row.get("Admit Year")))
            if pd.notna(bd): changed |= set_if_changed(st, "birth_date", bd.date())
            
            changed |= set_if_changed(st, "is_sponsored", is_sponsored)
            changed |= set_if_changed(st, "sponsor_name", sponsor)
            changed |= set_if_changed(st, "general_notes", notes)
            changed |= set_if_changed(st, "sibling_id", sib_id)
            
            if changed:
                updated_count += 1
        else:
            # Create new student
            new_student = Student(
                id=sid,
                name=str(row.get("Name", "Unknown")),
                college=college,
                program=str(row.get("Program", "")),
                price_per_hr=price,
                email=str(row.get("Email", "")) if pd.notna(row.get("Email")) else None,
                mobile=str(row.get("Mobile", "")) if pd.notna(row.get("Mobile")) else None,
                national_id=str(row.get("National ID", "")) if pd.notna(row.get("National ID")) else None,
                nationality=str(row.get("Nationality", "Egyptian")) if pd.notna(row.get("Nationality")) else "Egyptian",
                admit_year=int(row.get("Admit Year", DEFAULT_YEAR)) if pd.notna(row.get("Admit Year")) else DEFAULT_YEAR,
                birth_date=bd.date() if pd.notna(bd) else None,
                is_sponsored=is_sponsored,
                sponsor_name=sponsor,
                general_notes=notes,
                sibling_id=sib_id
            )
            new_students.append(new_student)
            existing_students[sid] = new_student # Prevent duplicates within the same file from causing errors
        
    if new_students or updated_count > 0:
        if new_students:
            db.add_all(new_students)
        write_audit(db, current_user.username, "BULK_UPSERT_STUDENTS", "bulk", f"{len(new_students)} new, {updated_count} updated")
        db.commit()
        get_static_lookups.cache_clear()
        
    return {
        "message": f"Processed successfully: {len(new_students)} new, {updated_count} updated.",
        "success_count": len(new_students) + updated_count,
        "failed_count": len(failed),
        "failed_rows": failed
    }
