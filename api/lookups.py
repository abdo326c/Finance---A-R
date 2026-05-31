from fastapi import APIRouter, Depends
from models import get_static_lookups
from api.auth import get_current_user
from config import VALID_TERMS, VALID_STATUSES, VALID_COLLEGES

router = APIRouter()

@router.get("/")
async def get_lookups(current_user = Depends(get_current_user)):
    sch_map, db_colleges, db_years = get_static_lookups()
    
    return {
        "years": db_years,
        "colleges": VALID_COLLEGES if VALID_COLLEGES else db_colleges,
        "terms": VALID_TERMS,
        "statuses": VALID_STATUSES,
        "scholarships": sch_map
    }
