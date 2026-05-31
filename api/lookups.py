from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models import get_static_lookups, get_db, SystemConfig
from api.auth import get_current_user
from pydantic import BaseModel
from typing import List, Dict
import json
from config import VALID_TERMS, VALID_STATUSES, VALID_COLLEGES

router = APIRouter()

class ConfigUpdate(BaseModel):
    values: List[str]

def get_db_config_list(db: Session, key: str, default_list: List[str]) -> List[str]:
    conf = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if conf:
        try:
            return json.loads(conf.value)
        except:
            pass
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
    return {"message": "Config updated successfully", "key": key, "values": data.values}
