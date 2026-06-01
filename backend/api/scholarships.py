from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import pandas as pd
import io

from models import (
    get_db, Student, StudentScholarship, ScholarshipType, Transaction,
    next_ref_block, write_audit, engine
)
from helpers import (
    get_retroactive_scholarship_tx, enforce_scholarship_cap, _pct
)
from api.auth import get_current_user
from config import VALID_TERMS, DEFAULT_YEAR

router = APIRouter()

class ScholarshipResponse(BaseModel):
    id: int
    student_id: int
    scholarship_type_id: int
    scholarship_name: str
    percentage: float
    term: str
    academic_year: int
    is_active: bool
    internal_note: Optional[str]

class AddScholarshipRequest(BaseModel):
    student_id: int
    scholarship_type_id: int
    percentage: float
    term: str
    academic_year: int
    internal_note: Optional[str] = None
    sibling_id: Optional[int] = None

class UpdateScholarshipRequest(BaseModel):
    is_active: Optional[bool] = None
    internal_note: Optional[str] = None
    reverse_past: Optional[bool] = False

@router.get("/student/{student_id}", response_model=List[ScholarshipResponse])
async def get_student_scholarships_api(student_id: int, term: str, year: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(StudentScholarship, ScholarshipType)
        .join(ScholarshipType)
        .filter(
            StudentScholarship.student_id == student_id,
            StudentScholarship.term == term,
            StudentScholarship.academic_year == year
        )
        .all()
    )
    
    result = []
    for ss, st_type in rows:
        result.append(ScholarshipResponse(
            id=ss.id,
            student_id=ss.student_id,
            scholarship_type_id=ss.scholarship_type_id,
            scholarship_name=st_type.name,
            percentage=ss.percentage,
            term=ss.term,
            academic_year=ss.academic_year,
            is_active=ss.is_active,
            internal_note=ss.internal_note
        ))
    return result

@router.post("/", response_model=dict)
async def add_scholarship(req: AddScholarshipRequest, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    student = db.get(Student, req.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    st_type = db.get(ScholarshipType, req.scholarship_type_id)
    if not st_type:
        raise HTTPException(status_code=404, detail="Scholarship type not found")
        
    if st_type.name == "SCH: Sibiling %" and not req.sibling_id:
        raise HTTPException(status_code=400, detail="Sibling ID is required for Sibling scholarship")
        
    if req.sibling_id and not student.sibling_id:
        student.sibling_id = req.sibling_id
        
    existing = db.query(StudentScholarship).filter_by(
        student_id=req.student_id, 
        scholarship_type_id=req.scholarship_type_id,
        term=req.term, 
        academic_year=req.academic_year
    ).first()
    
    if existing:
        existing.percentage = req.percentage
        existing.is_active = True
        existing.internal_note = req.internal_note
    else:
        new_sch = StudentScholarship(
            student_id=req.student_id,
            scholarship_type_id=req.scholarship_type_id,
            percentage=req.percentage,
            term=req.term,
            academic_year=req.academic_year,
            is_active=True,
            internal_note=req.internal_note
        )
        db.add(new_sch)
        
    enforce_scholarship_cap(db, req.student_id, req.term, req.academic_year)
    db.commit()
    
    # Check if it's still active after cap enforcement
    still_active = db.query(StudentScholarship.is_active).filter_by(
        student_id=req.student_id, 
        scholarship_type_id=req.scholarship_type_id,
        term=req.term, 
        academic_year=req.academic_year
    ).scalar()
    
    if still_active:
        seq = next_ref_block(db, 1)
        r_tx = get_retroactive_scholarship_tx(
            db, req.student_id, req.term, req.academic_year,
            req.scholarship_type_id, st_type.name, req.percentage, seq,
            internal_note=req.internal_note
        )
        if r_tx:
            db.add(r_tx)
            
    write_audit(db, current_user.username, "ADD_SCHOLARSHIP", f"student_id={req.student_id}", f"{st_type.name} {req.percentage}% {req.term} {req.academic_year}")
    db.commit()
    
    return {"message": "Scholarship added successfully"}

@router.put("/{sch_id}")
async def update_scholarship(sch_id: int, req: UpdateScholarshipRequest, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    ss = db.get(StudentScholarship, sch_id)
    if not ss:
        raise HTTPException(status_code=404, detail="Scholarship not found")
        
    st_type = db.get(ScholarshipType, ss.scholarship_type_id)
        
    if req.internal_note is not None:
        ss.internal_note = req.internal_note
        
    if req.is_active is not None and req.is_active != ss.is_active:
        ss.is_active = req.is_active
        db.commit()
        
        if not req.is_active and req.reverse_past:
            if current_user.role != "Admin":
                raise HTTPException(status_code=403, detail="Admin role required to reverse past discounts")
            seq = next_ref_block(db, 1)
            r_tx = get_retroactive_scholarship_tx(
                db, ss.student_id, ss.term, ss.academic_year,
                ss.scholarship_type_id, st_type.name, 0.0, seq,
                internal_note=ss.internal_note
            )
            if r_tx:
                db.add(r_tx)
                db.commit()
                
        elif req.is_active:
            enforce_scholarship_cap(db, ss.student_id, ss.term, ss.academic_year)
            db.commit()
            still_active = db.query(StudentScholarship.is_active).filter_by(id=ss.id).scalar()
            if still_active:
                seq = next_ref_block(db, 1)
                r_tx = get_retroactive_scholarship_tx(
                    db, ss.student_id, ss.term, ss.academic_year,
                    ss.scholarship_type_id, st_type.name, _pct(ss.percentage), seq,
                    internal_note=ss.internal_note
                )
                if r_tx:
                    db.add(r_tx)
                    db.commit()
                    
    db.commit()
    return {"message": "Scholarship updated successfully"}

class SyncRequest(BaseModel):
    term: str
    year: int

@router.post("/sync")
async def sync_scholarships(req: SyncRequest, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    active_schs = (
        db.query(StudentScholarship, ScholarshipType)
        .join(ScholarshipType)
        .filter(
            StudentScholarship.term == req.term,
            StudentScholarship.academic_year == req.year,
            StudentScholarship.is_active == True
        )
        .all()
    )
    if not active_schs:
        return {"message": "No active scholarships found for this term", "applied": 0}
        
    batch_id = f"BCH-SYNC-{datetime.now().strftime('%y%m%d-%H%M%S')}"
    curr = next_ref_block(db, len(active_schs) + 1)
    retro = []
    
    for ss, st_type in active_schs:
        r_tx = get_retroactive_scholarship_tx(
            db, ss.student_id, req.term, req.year,
            ss.scholarship_type_id, st_type.name,
            _pct(ss.percentage), curr, batch_id,
            internal_note=ss.internal_note
        )
        if r_tx:
            retro.append(r_tx)
            curr += 1
            
    if retro:
        db.bulk_save_objects(retro)
        db.commit()
        return {"message": f"Applied {len(retro)} missing discounts", "applied": len(retro)}
    else:
        return {"message": "All discounts are already aligned", "applied": 0}

@router.get("/report/data")
async def get_report_data(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    sql = text("""
        SELECT s.id AS "student_id", s.name AS "student_name", s.college AS "college",
            ss.term AS "term", ss.academic_year AS "year", st.name AS "scholarship_name",
            ss.percentage AS "configured_pct",
            CASE WHEN ss.is_active THEN 'Active' ELSE 'Inactive' END AS "status",
            COALESCE((SELECT SUM(t.debit-t.credit) FROM transactions t
                        WHERE t.student_id=s.id AND t.term=ss.term AND t.academic_year=ss.academic_year
                        AND t.transaction_type IN ('Invoice','Bulk Invoices (Tuition)','Credit Hours Adjustment','Credit Hours Adjustments')),0) AS "tuition_billed",
            COALESCE((SELECT SUM(t.credit-t.debit) FROM transactions t
                        WHERE t.student_id=s.id AND t.term=ss.term AND t.academic_year=ss.academic_year
                        AND t.reference_no LIKE 'SCH-%' AND t.scholarship_type_id=ss.scholarship_type_id),0) AS "actual_discount"
        FROM student_scholarships ss
        JOIN students s  ON ss.student_id=s.id
        JOIN scholarship_types st ON ss.scholarship_type_id=st.id
        ORDER BY ss.academic_year DESC, ss.term, s.id
    """)
    df = pd.read_sql(sql, con=engine)
    return df.to_dict(orient="records")
