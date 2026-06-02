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
    existing_ids = {s[0] for s in db.query(Student.id).all()}
    
    new_students = []
    failed = []
    
    for i, row in df.iterrows():
        sid = int(row.get("ID", 0)) if pd.notnull(row.get("ID")) else 0
        orig = row.to_dict()
        college = str(row.get("College", "")).strip().upper()
        
        if sid <= 0 or sid in existing_ids:
            orig["Error Reason"] = "Invalid or duplicate ID"
            failed.append(orig)
            continue
            
        if college not in valid_colleges:
            orig["Error Reason"] = f"Invalid college '{college}'"
            failed.append(orig)
            continue
            
        bd = pd.to_datetime(row.get("Birth Date"), errors="coerce")
        
        new_student = Student(
            id=sid,
            name=str(row.get("Name", "Unknown")),
            college=college,
            program=str(row.get("Program", "")),
            price_per_hr=float(row.get("Price Per Hr", 0.0)),
            email=str(row.get("Email", "")),
            mobile=str(row.get("Mobile", "")),
            national_id=str(row.get("National ID", "")),
            nationality=str(row.get("Nationality", "Egyptian")),
            admit_year=int(row.get("Admit Year", DEFAULT_YEAR)),
            birth_date=bd.date() if pd.notna(bd) else None
        )
        new_students.append(new_student)
        existing_ids.add(sid) # Prevent duplicates within the same file
        
    if new_students:
        db.add_all(new_students)
        write_audit(db, current_user.username, "BULK_REGISTER", "bulk", f"{len(new_students)} students")
        db.commit()
        get_static_lookups.cache_clear()
        
    return {
        "message": f"Registered {len(new_students)} students.",
        "success_count": len(new_students),
        "failed_count": len(failed),
        "failed_rows": failed
    }
