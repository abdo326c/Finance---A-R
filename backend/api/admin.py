from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import io

from models import get_db, SystemUser, Student, StudentScholarship, AuditLog, write_audit
from api.auth import get_current_user, hash_pw

router = APIRouter()

class UserCreate(BaseModel):
    username: str
    password: str
    role: str

class UserUpdate(BaseModel):
    role: str
    is_active: bool
    password: Optional[str] = None

@router.get("/users")
async def get_users(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    users = db.query(SystemUser).order_by(SystemUser.id).all()
    return [{"id": u.id, "username": u.username, "role": u.role, "is_active": u.is_active} for u in users]

@router.post("/users")
async def create_user(data: UserCreate, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if db.query(SystemUser).filter(func.lower(SystemUser.username) == data.username.lower().strip()).first():
        raise HTTPException(status_code=400, detail="Username already exists")
        
    new_user = SystemUser(
        username=data.username.strip(),
        password_hash=hash_pw(data.password),
        role=data.role,
        is_active=True
    )
    db.add(new_user)
    write_audit(db, current_user.username, "CREATE_USER", f"username={data.username}", "Created new user")
    db.commit()
    return {"message": "User created successfully"}

@router.put("/users/{user_id}")
async def update_user(user_id: int, data: UserUpdate, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")
        
    user = db.get(SystemUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.role = data.role
    user.is_active = data.is_active
    if data.password:
        user.password_hash = hash_pw(data.password)
        
    write_audit(db, current_user.username, "UPDATE_USER", f"user_id={user_id}", "Updated user details")
    db.commit()
    return {"message": "User updated successfully"}

@router.post("/fixes/college-names")
async def fix_college_names(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")
        
    fixed = 0
    students = db.query(Student).all()
    for s in students:
        if s.college:
            clean = s.college.strip().upper()
            if clean != s.college:
                s.college = clean
                fixed += 1
                
    if fixed > 0:
        write_audit(db, current_user.username, "DB_FIX", "college_names", f"Fixed {fixed} records")
        db.commit()
        
    return {"message": f"Fixed {fixed} college names."}

@router.post("/fixes/scholarships")
async def fix_scholarships(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")
        
    fixed = 0
    scholarships = db.query(StudentScholarship).all()
    for ss in scholarships:
        if ss.percentage <= 1.0 and ss.percentage > 0:
            ss.percentage = round(ss.percentage * 100.0, 4)
            fixed += 1
            
    if fixed > 0:
        write_audit(db, current_user.username, "DB_FIX", "scholarship_percentages", f"Converted {fixed} records")
        db.commit()
        
    return {"message": f"Converted {fixed} scholarship percentages."}

@router.get("/fixes/template")
async def download_template(current_user = Depends(get_current_user)):
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")
        
    sample_data = {
        "ID": [211000224, 211001595],
        "Dimension": [
            "Academic||||||||EAS (AC02)|Civil and Infrastructure|211000224|Spring|",
            "Academic||||||||BA (AC02)|General Business|211001595|Fall|"
        ]
    }
    df_sample = pd.DataFrame(sample_data)
    
    template_buffer = io.BytesIO()
    with pd.ExcelWriter(template_buffer, engine='openpyxl') as writer:
        df_sample.to_excel(writer, index=False, sheet_name='D365_Template')
        
    from fastapi.responses import Response
    return Response(
        content=template_buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=D365_Students_Dimensions_Template.xlsx"}
    )

@router.post("/fixes/bulk-dimensions")
async def bulk_update_dimensions(file: UploadFile = File(...), current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")
        
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="Must be an Excel (.xlsx) file")
        
    try:
        content = await file.read()
        df = pd.read_excel(io.BytesIO(content), engine='openpyxl')
        
        if 'ID' not in df.columns or 'Dimension' not in df.columns:
            raise HTTPException(status_code=400, detail="File must contain exactly two columns named 'ID' and 'Dimension'")
            
        update_list = []
        for index, row in df.iterrows():
            if pd.isna(row['ID']) or pd.isna(row['Dimension']):
                continue
                
            student_id = int(row['ID'])
            dimension_val = str(row['Dimension']).strip()
            
            if student_id > 0 and dimension_val and dimension_val.lower() != 'nan':
                update_list.append({
                    "id": student_id,
                    "financial_dimension": dimension_val
                })
                
        if update_list:
            chunk_size = 2000
            for i in range(0, len(update_list), chunk_size):
                chunk = update_list[i:i+chunk_size]
                db.bulk_update_mappings(Student, chunk)
                db.commit()
                
            write_audit(db, current_user.username, "BULK_UPDATE_DIMENSIONS", "students", f"Updated {len(update_list)} dimensions")
            db.commit()
            return {"message": f"Successfully updated financial dimensions for {len(update_list)} students!"}
        else:
            return {"message": "No valid data found in the uploaded file.", "warning": True}
            
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/audit-logs")
async def get_audit_logs(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")
        
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(500).all()
    return [{
        "id": l.id,
        "time": l.created_at.isoformat(),
        "user": l.username,
        "action": l.action,
        "target": l.target,
        "detail": l.detail
    } for l in logs]
