# config.py
# ─────────────────────────────────────────────
# Centralized constants & environment config
# ─────────────────────────────────────────────
import os
from functools import lru_cache

MAX_BULK_ROWS  = 25_000         # guard against huge uploads freezing the app
TIMEOUT_MIN    = 30             # session idle timeout in minutes
DB_URL = os.environ.get("DB_URL", "sqlite:///finance.db")


@lru_cache(maxsize=1)
def get_dynamic_configs():
    """
    Dynamically loads configuration lists from the database.
    If the database is not ready or the keys don't exist,
    it populates them with initial defaults and returns them.
    """
    from contextlib import contextmanager
    from models import get_db, SystemConfig
    
    defaults = {
        "VALID_TERMS": '["Fall", "Spring", "Summer"]',
        "VALID_STATUSES": '["Active", "Inactive", "Graduated", "Program Withdraw", "Semester Withdraw"]',
        "VALID_COLLEGES": '["ENG", "BBA", "IT_CS", "BIO_TECH"]',
        "VALID_ROLES": '["Admin", "Editor", "Viewer"]',
        "DEFAULT_YEAR": "2026"
    }
    
    configs = {}
    try:
        with contextmanager(get_db)() as db:
            for key, def_val in defaults.items():
                row = db.query(SystemConfig).filter_by(key=key).first()
                if not row:
                    row = SystemConfig(key=key, value=def_val)
                    db.add(row)
                    db.commit()
                configs[key] = row.value
    except Exception:
        configs = defaults
        
    import json
    
    def _parse_list(val):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass
        return [x.strip() for x in str(val).split(",") if x.strip()]

    return {
        "VALID_TERMS": _parse_list(configs["VALID_TERMS"]),
        "VALID_STATUSES": _parse_list(configs["VALID_STATUSES"]),
        "VALID_COLLEGES": _parse_list(configs["VALID_COLLEGES"]),
        "VALID_ROLES": _parse_list(configs["VALID_ROLES"]),
        "DEFAULT_YEAR": int(configs["DEFAULT_YEAR"])
    }


# Expose dynamic constants so that imports across the app work out-of-the-box
_cfg = get_dynamic_configs()
VALID_TERMS    = _cfg["VALID_TERMS"]
VALID_STATUSES = _cfg["VALID_STATUSES"]
VALID_COLLEGES = _cfg["VALID_COLLEGES"]
VALID_ROLES    = _cfg["VALID_ROLES"]
DEFAULT_YEAR   = _cfg["DEFAULT_YEAR"]
