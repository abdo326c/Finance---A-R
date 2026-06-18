from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from models import get_static_lookups, get_db, SystemConfig, ScholarshipType, ScholarshipMapping
from api.auth import get_current_user
from typing import List
import json
import logging
import pandas as pd
import io
from config import VALID_TERMS, VALID_STATUSES, VALID_COLLEGES, get_dynamic_configs
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

class ConfigUpdate(BaseModel):
    values: List[str]

def get_db_config_list(db: Session, key: str, default_list: List[str]) -> List[str]:
    conf = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if conf:
        try:
            return json.loads(conf.value)
        except Exception as e:
            logger.warning(f"Failed to parse config '{key}' as JSON: {e}")
    return default_list

@router.get("/")
def get_lookups(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    sch_map, db_colleges, db_years = get_static_lookups()
    
    colleges = get_db_config_list(db, "VALID_COLLEGES", VALID_COLLEGES if VALID_COLLEGES else db_colleges)
    terms = get_db_config_list(db, "VALID_TERMS", VALID_TERMS)
    statuses = get_db_config_list(db, "VALID_STATUSES", VALID_STATUSES)
    
    return {
        "years": db_years,
        "colleges": colleges,
        "terms": terms,
        "statuses": statuses,
        "scholarships": sch_map
    }

@router.get("/manage")
def get_manageable_lookups(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    # Returns the lists directly for the admin UI
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")
        
    _, db_colleges, _ = get_static_lookups()
    
    return {
        "VALID_COLLEGES": get_db_config_list(db, "VALID_COLLEGES", VALID_COLLEGES if VALID_COLLEGES else db_colleges),
        "VALID_TERMS": get_db_config_list(db, "VALID_TERMS", VALID_TERMS),
        "VALID_STATUSES": get_db_config_list(db, "VALID_STATUSES", VALID_STATUSES)
    }

@router.put("/manage/{key}")
def update_lookup(key: str, data: ConfigUpdate, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")
        
    valid_keys = ["VALID_COLLEGES", "VALID_TERMS", "VALID_STATUSES"]
    if key not in valid_keys:
        raise HTTPException(status_code=400, detail="Invalid config key")
        
    conf = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    new_value = json.dumps(data.values)
    
    if conf:
        conf.value = new_value
    else:
        new_conf = SystemConfig(key=key, value=new_value)
        db.add(new_conf)
        
    db.commit()
    
    # Invalidate the cached config so changes take effect immediately
    get_dynamic_configs.cache_clear()
    
    return {"message": "Config updated successfully", "key": key, "values": data.values}

@router.get("/scholarship_types")
def get_scholarship_types(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    from models import ScholarshipType
    types = db.query(ScholarshipType).all()
    return [{"id": t.id, "name": t.name} for t in types]

@router.post("/scholarship_types")
def add_scholarship_type(data: dict, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    from models import ScholarshipType
    name = data.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    new_type = ScholarshipType(name=name)
    db.add(new_type)
    db.commit()
    get_static_lookups.cache_clear()
    return {"message": "Added", "id": new_type.id, "name": new_type.name}

@router.delete("/scholarship_types/{id}")
def delete_scholarship_type(id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    from models import ScholarshipType
    st = db.get(ScholarshipType, id)
    if st:
        db.delete(st)
        db.commit()
        get_static_lookups.cache_clear()
    return {"message": "Deleted"}

@router.get("/students/search")
def search_students(q: str, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    from models import Student
    
    query = db.query(Student)
    from sqlalchemy import or_, cast, String
    query = query.filter(or_(
        cast(Student.id, String).ilike(f"%{q}%"),
        Student.name.ilike(f"%{q}%"), 
        Student.email.ilike(f"%{q}%")
    ))
        
    students = query.limit(20).all()
    return [{"id": s.id, "name": s.name, "email": s.email or f"student{s.id}@nu.edu.eg"} for s in students]

@router.get("/scholarship_mappings")
def get_scholarship_mappings(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    mappings = db.query(ScholarshipMapping).all()
    res = []
    for m in mappings:
        st = db.query(ScholarshipType).filter(ScholarshipType.id == m.scholarship_type_id).first()
        res.append({
            "id": m.id,
            "charge_code": m.charge_code,
            "scholarship_type_name": st.name if st else "Unknown"
        })
    return res

@router.post("/scholarship_mappings/upload")
async def upload_scholarship_mappings(file: UploadFile = File(...), current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only Excel files (.xlsx, .xls) are supported.")
        
    contents = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse Excel file: {str(e)}")
        
    if len(df.columns) < 2:
        raise HTTPException(status_code=400, detail="Excel file must have at least 2 columns: Charge Code and Scholarship Category.")
        
    # Build dictionary of existing categories to map to type_id
    scholarship_types = {s.name.strip().lower(): s.id for s in db.query(ScholarshipType).all()}
    
    added_count = 0
    updated_count = 0
    errors = []
    
    for i, row in df.iterrows():
        try:
            charge_code = str(row.iloc[0]).strip()
            category_name = str(row.iloc[1]).strip()
            
            if not charge_code or pd.isna(row.iloc[0]) or charge_code.lower() == 'nan':
                continue
                
            matched_id = scholarship_types.get(category_name.lower())
            if not matched_id:
                errors.append(f"Row {i+2}: Category '{category_name}' not found in system.")
                continue
                
            # Check if charge code already mapped
            existing = db.query(ScholarshipMapping).filter(ScholarshipMapping.charge_code == charge_code).first()
            if existing:
                if existing.scholarship_type_id != matched_id:
                    existing.scholarship_type_id = matched_id
                    updated_count += 1
            else:
                new_map = ScholarshipMapping(charge_code=charge_code, scholarship_type_id=matched_id)
                db.add(new_map)
                added_count += 1
                
        except Exception as e:
            errors.append(f"Row {i+2}: Error processing - {str(e)}")
            
    db.commit()
    return {
        "message": f"Successfully mapped {added_count} new codes and updated {updated_count} existing codes.",
        "added": added_count,
        "updated": updated_count,
        "errors": errors
    }

@router.delete("/scholarship_mappings/{mapping_id}")
def delete_scholarship_mapping(mapping_id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    
    mapping = db.query(ScholarshipMapping).filter(ScholarshipMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")
        
    db.delete(mapping)
    db.commit()
    return {"message": "Mapping deleted"}
