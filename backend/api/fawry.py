import datetime
import requests
import os
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from models import get_db, Student, Transaction, write_audit, next_ref_block
from api.auth import get_current_user

router = APIRouter()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

def fetch_supabase_transactions():
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    all_transactions = []
    limit = 1000
    offset = 0
    
    try:
        while True:
            url = f"{SUPABASE_URL}/rest/v1/transactions?id_status=eq.Valid&limit={limit}&offset={offset}"
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                all_transactions.extend(data)
                if len(data) < limit:
                    break
                offset += limit
            else:
                raise Exception(f"Supabase connection error: HTTP {response.status_code}")
                
        return all_transactions
    except Exception as e:
        raise Exception(f"Failed to connect to Supabase: {e}")

@router.get("/fetch")
async def fetch_unsynced_fawry(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        supabase_txs = fetch_supabase_transactions()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
        
    if not supabase_txs:
        return {"unsynced": [], "message": "No valid transactions found in Supabase."}
        
    # Get all local synced transactions
    synced_txs = db.query(Transaction).filter(
        (Transaction.reference_no.like("FAWRY-%")) |
        (Transaction.internal_note.like("FAWRY_SYNC:%"))
    ).all()
    
    local_fawry_keys = set()
    for tx in synced_txs:
        if tx.reference_no and tx.reference_no.startswith("FAWRY-"):
            local_fawry_keys.add(tx.reference_no)
        if tx.internal_note and tx.internal_note.startswith("FAWRY_SYNC:"):
            parts = tx.internal_note.split(" | ")[0].split(":")
            if len(parts) >= 3:
                f_ref = parts[1]
                f_item = parts[2]
                local_fawry_keys.add(f"FAWRY-{f_ref}-{f_item}")
                local_fawry_keys.add(f"FAWRY-{f_ref}") # Legacy
                
    local_students = {s.id: s for s in db.query(Student).all()}
    unsynced_txs = []
    
    for stx in supabase_txs:
        ref = str(stx.get("reference_number"))
        item_name = stx.get("item_name", "TUI")
        
        expected_ref = f"FAWRY-{ref}-{item_name}"
        legacy_ref = f"FAWRY-{ref}"
        
        if expected_ref in local_fawry_keys or legacy_ref in local_fawry_keys:
            continue
            
        student_id_str = stx.get("student_id")
        student_id = None
        student_found = False
        student_name = "Not Registered"
        
        try:
            if student_id_str and str(student_id_str).isdigit():
                student_id = int(student_id_str)
                if student_id in local_students:
                    student_found = True
                    student_name = local_students[student_id].name
        except Exception:
            pass
            
        unsynced_txs.append({
            "reference_number": ref,
            "student_id": student_id_str,
            "student_id_int": student_id,
            "student_found": student_found,
            "student_name": student_name,
            "payment_date": stx.get("payment_date"),
            "item_name": item_name,
            "item_price": float(stx.get("item_price", 0.0)),
            "bank": stx.get("bank", "NUADCB136"),
            "fawry_fees": float(stx.get("fawry_fees", 0.0)),
            "net_amount": float(stx.get("net_amount", 0.0))
        })
        
    return {"unsynced": unsynced_txs}

class FawrySyncRequest(BaseModel):
    refs_to_sync: List[str]
    term: str
    year: int

@router.post("/sync")
async def sync_fawry_payments(
    req: FawrySyncRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        supabase_txs = fetch_supabase_transactions()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
        
    valid_to_sync = [tx for tx in supabase_txs if str(tx.get("reference_number")) in req.refs_to_sync]
    if not valid_to_sync:
        raise HTTPException(status_code=400, detail="No matching transactions found to sync.")
        
    sync_count = 0
    sync_amount = 0.0
    failed_count = 0
    failed_details = []
    
    batch_id = f"FAWRY-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    start_ref_num = next_ref_block(db, len(valid_to_sync))
    current_ref_idx = start_ref_num
    
    for tx in valid_to_sync:
        try:
            with db.begin_nested():
                p_date = datetime.date.today()
                if tx.get("payment_date"):
                    try:
                        p_date = datetime.datetime.strptime(tx["payment_date"], "%Y-%m-%d").date()
                    except:
                        pass
                
                item_name = tx.get("item_name", "TUI")
                bank = tx.get("bank", "NUADCB136")
                ref = str(tx.get("reference_number"))
                fawry_fees = float(tx.get("fawry_fees", 0.0))
                net_amount = float(tx.get("net_amount", 0.0))
                item_price = float(tx.get("item_price", 0.0))
                student_id = int(tx.get("student_id"))
                
                new_ref_no = f"PAY-{current_ref_idx:06d}"
                
                new_tx = Transaction(
                    reference_no=new_ref_no,
                    batch_id=batch_id,
                    student_id=student_id,
                    transaction_type="Bulk Payments",
                    description=f"Bank: {bank} | Ref: {ref}",
                    internal_note=f"FAWRY_SYNC:{ref}:{item_name} | Fawry Fees: {fawry_fees} EGP | Net Amount: {net_amount} EGP",
                    debit=0.0,
                    credit=item_price,
                    hours_change=0.0,
                    entry_date=p_date,
                    term=req.term,
                    academic_year=req.year
                )
                db.add(new_tx)
                
                write_audit(
                    db, current_user.username, "FAWRY_SYNC",
                    f"student_id={student_id}",
                    f"Synced Fawry Ref={ref} as {new_ref_no} | batch={batch_id}"
                )
                
            sync_count += 1
            sync_amount += item_price
            current_ref_idx += 1
        except Exception as inner_ex:
            failed_count += 1
            failed_details.append(f"Ref {tx.get('reference_number')}: {str(inner_ex)}")
            
    db.commit()
    
    return {
        "message": "Sync completed",
        "sync_count": sync_count,
        "sync_amount": sync_amount,
        "failed_count": failed_count,
        "failed_details": failed_details,
        "batch_id": batch_id
    }
