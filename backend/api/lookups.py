from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models import get_static_lookups, get_db, SystemConfig
from api.auth import get_current_user
from typing import List
import json
import logging
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
async def get_lookups(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
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
async def get_manageable_lookups(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
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
async def update_lookup(key: str, data: ConfigUpdate, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
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
async def get_scholarship_types(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    from models import ScholarshipType
    types = db.query(ScholarshipType).all()
    return [{"id": t.id, "name": t.name} for t in types]

@router.post("/scholarship_types")
async def add_scholarship_type(data: dict, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
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
async def delete_scholarship_type(id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
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
async def search_students(q: str, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    from models import Student
    
    query = db.query(Student)
    if q.isdigit():
        query = query.filter(Student.id == int(q))
    else:
        query = query.filter(Student.name.ilike(f"%{q}%"))
        
    students = query.limit(20).all()
    return [{"id": s.id, "name": s.name, "email": s.email or f"student{s.id}@nu.edu.eg"} for s in students]
