import io
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from models import get_db, Transaction, DeletedBatchLog, write_audit, Student
from api.auth import get_current_user

router = APIRouter()

@router.get("/active")
async def get_active_batches(db: Session = Depends(get_db)):
    summaries = (
        db.query(
            Transaction.batch_id,
            Transaction.transaction_type,
            func.count(Transaction.id).label("records"),
            func.sum(Transaction.debit).label("total_debit"),
            func.sum(Transaction.credit).label("total_credit"),
            func.max(Transaction.created_at).label("uploaded_at"),
        )
        .filter(Transaction.batch_id.isnot(None))
        .group_by(Transaction.batch_id, Transaction.transaction_type)
        .order_by(func.max(Transaction.created_at).desc())
        .all()
    )
    
    return [
        {
            "batch_id": b.batch_id,
            "type": b.transaction_type,
            "records": b.records,
            "total_debit": b.total_debit,
            "total_credit": b.total_credit,
            "uploaded_at": b.uploaded_at
        } for b in summaries
    ]

@router.get("/export/{batch_id}")
async def export_batch(batch_id: str, db: Session = Depends(get_db)):
    sql = text("""
        SELECT t.reference_no AS "Ref No", s.id AS "Student ID",
            s.name AS "Student Name", t.transaction_type AS "Type",
            t.description AS "Description", t.entry_date AS "Date",
            t.term AS "Term", t.academic_year AS "Year",
            t.hours_change AS "Hours", t.debit AS "Debit", t.credit AS "Credit"
        FROM transactions t JOIN students s ON t.student_id=s.id
        WHERE t.batch_id=:bid ORDER BY t.id
    """)
    
    df = pd.read_sql(sql, con=db.get_bind(), params={"bid": batch_id})
    if df.empty:
        raise HTTPException(status_code=404, detail="Batch ID not found or is empty.")
        
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="Batch_{batch_id}.xlsx"'}
    )

@router.delete("/{batch_id}")
async def delete_batch(
    batch_id: str, 
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Only Admins can delete batches.")
        
    summaries = (
        db.query(
            Transaction.batch_id,
            Transaction.transaction_type,
            func.count(Transaction.id).label("records"),
            func.sum(Transaction.debit).label("total_debit"),
            func.sum(Transaction.credit).label("total_credit")
        )
        .filter(Transaction.batch_id == batch_id)
        .group_by(Transaction.batch_id, Transaction.transaction_type)
        .all()
    )
    
    if not summaries:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found.")
        
    total_records = sum(b.records for b in summaries)
    
    try:
        db.add(DeletedBatchLog(
            batch_id=batch_id,
            transaction_type=" & ".join({b.transaction_type for b in summaries}),
            record_count=total_records,
            total_debit=sum(b.total_debit or 0 for b in summaries),
            total_credit=sum(b.total_credit or 0 for b in summaries),
            deleted_by=current_user.username
        ))
        
        db.query(Transaction).filter(Transaction.batch_id == batch_id).delete()
        
        write_audit(db, current_user.username, "DELETE_BATCH", batch_id, f"{total_records} records removed")
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete batch: {str(e)}")
        
    return {"message": f"Batch {batch_id} successfully deleted.", "deleted_records": total_records}

@router.get("/deleted")
async def get_deleted_batches(db: Session = Depends(get_db)):
    logs = db.query(DeletedBatchLog).order_by(DeletedBatchLog.deleted_at.desc()).all()
    
    return [
        {
            "id": l.id,
            "batch_id": l.batch_id,
            "type": l.transaction_type,
            "records": l.record_count,
            "total_debit": l.total_debit,
            "total_credit": l.total_credit,
            "deleted_by": l.deleted_by,
            "deleted_at": l.deleted_at
        } for l in logs
    ]
