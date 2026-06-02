from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.sql import func
import pandas as pd

from models import get_db, Transaction, Student, StudentStatus, engine
from api.auth import get_current_user

router = APIRouter()

@router.get("/metrics")
async def get_dashboard_data(
    term: str = "All Terms",
    year: str = "All Years",
    college: str = "All Colleges",
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. Fetch Summary Metrics
    subq = db.query(
        StudentStatus.student_id,
        StudentStatus.status,
        func.row_number().over(
            partition_by=StudentStatus.student_id,
            order_by=StudentStatus.id.desc()
        ).label("rn")
    ).subquery()
    
    latest_status = db.query(subq).filter(subq.c.rn == 1).subquery()
    
    exclude_cond = func.coalesce(latest_status.c.status, 'Not Set') != 'Test'
    
    base_q    = db.query(Transaction).join(Student, Transaction.student_id == Student.id).outerjoin(latest_status, Student.id == latest_status.c.student_id).filter(exclude_cond)
    status_q  = db.query(StudentStatus).filter(StudentStatus.status == "Active")
    student_q = db.query(Student).outerjoin(latest_status, Student.id == latest_status.c.student_id).filter(exclude_cond)

    if term != "All Terms":
        base_q   = base_q.filter(Transaction.term == term)
        status_q = status_q.filter(StudentStatus.term == term)
    if year != "All Years":
        yr = int(year)
        base_q   = base_q.filter(Transaction.academic_year == yr)
        status_q = status_q.filter(StudentStatus.academic_year == yr)
    if college != "All Colleges":
        base_q    = base_q.filter(Student.college == college)
        student_q = student_q.filter(Student.college == college)
        status_q  = status_q.join(Student, StudentStatus.student_id == Student.id)\
                             .filter(Student.college == college)

    def agg(types, col="debit"):
        return base_q.filter(Transaction.transaction_type.in_(types))\
                     .with_entities(func.sum(getattr(Transaction, col))).scalar() or 0.0

    gross_billed    = float(agg(["Invoice","Bulk Invoices (Tuition)","Other Fees","Bulk Other Fees"]))
    total_discounts = float(agg(["Discount","Bulk Scholarships"],"credit") - agg(["Discount","Bulk Scholarships"],"debit"))
    total_payments  = float(agg(["Payment Receipt","Bulk Payments"],"credit") - agg(["Payment Receipt","Bulk Payments"],"debit"))
                     
    total_debit     = float(base_q.with_entities(func.sum(Transaction.debit)).scalar() or 0.0)
    total_credit    = float(base_q.with_entities(func.sum(Transaction.credit)).scalar() or 0.0)
    net_balance     = total_debit - total_credit
    net_adjustments = net_balance - (gross_billed - total_discounts - total_payments)
    
    total_students  = student_q.count()
    active_count    = status_q.distinct(StudentStatus.student_id).count()

    metrics = {
        "gross_billed": gross_billed,
        "total_discounts": total_discounts,
        "total_payments": total_payments,
        "net_balance": net_balance,
        "net_adjustments": net_adjustments,
        "total_students": total_students,
        "active_count": active_count
    }

    # 2. Fetch Breakdown Table
    with engine.connect() as conn:
        df = pd.read_sql(
            text("""
                WITH latest_status AS (
                    SELECT student_id, status, ROW_NUMBER() OVER (PARTITION BY student_id ORDER BY id DESC) AS rn
                    FROM student_statuses
                )
                SELECT s.college AS "College", COUNT(DISTINCT s.id) AS "Students",
                    COALESCE(SUM(CASE WHEN t.transaction_type IN ('Invoice','Bulk Invoices (Tuition)') THEN t.debit ELSE 0 END),0) AS "Tuition_Billed",
                    COALESCE(SUM(CASE WHEN t.transaction_type IN ('Discount','Bulk Scholarships') THEN t.credit-t.debit ELSE 0 END),0) AS "Discounts",
                    COALESCE(SUM(CASE WHEN t.transaction_type IN ('Payment Receipt','Bulk Payments') THEN t.credit ELSE 0 END),0) AS "Payments",
                    COALESCE(SUM(t.debit)-SUM(t.credit),0) AS "Net_Balance"
                FROM students s 
                LEFT JOIN latest_status ls ON ls.student_id = s.id AND ls.rn = 1
                LEFT JOIN transactions t ON s.id=t.student_id
                    AND (:tf='All Terms' OR t.term=:tf)
                    AND (:yf='All Years' OR t.academic_year=:yv)
                WHERE (:cf='All Colleges' OR s.college=:cf)
                    AND COALESCE(ls.status,'Not Set') != 'Test'
                GROUP BY s.college ORDER BY s.college
            """),
            con=conn,
            params={"tf": term, "yf": year,
                    "yv": int(year) if year != "All Years" else 0,
                    "cf": college},
        )
    
    breakdown = df.to_dict(orient="records")

    return {
        "metrics": metrics,
        "breakdown": breakdown
    }
