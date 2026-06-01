import io
import pandas as pd
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text, bindparam

from models import get_db, get_db_engine
from api.auth import get_current_user

router = APIRouter()

FORMATS = [
    "Accounting Summary",
    "Full Detailed Log",
    "Period Closing (Activity Summary)",
    "Student Academic Status Report",
]

def fetch_df(engine, sql, params):
    with engine.connect() as conn:
        result = conn.execute(sql, params)
        rows = result.fetchall()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows, columns=result.keys())

def generate_report_df(
    engine,
    rep_format: str,
    cols: List[str] = [],
    terms: List[str] = [],
    years: List[int] = [],
    stats: List[str] = [],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> pd.DataFrame:
    
    common = {
        "c_cnt": len(cols),   "cls":  tuple(cols) if cols else ("",),
        "t_cnt": len(terms),  "trms": tuple(terms) if terms else ("",),
        "y_cnt": len(years),  "yrs":  tuple(years) if years else (-1,),
        "s_cnt": len(stats),  "stats":tuple(stats) if stats else ("",),
    }

    if rep_format == "Student Academic Status Report":
        sql = text("""
            SELECT s.id AS "Student ID", s.name AS "Student Name",
                s.college AS "College", s.program AS "Program",
                ss.term AS "Term", ss.academic_year AS "Year", ss.status AS "Academic Status"
            FROM student_statuses ss JOIN students s ON ss.student_id=s.id
            WHERE (:c_cnt=0 OR s.college IN :cls)
                AND (:t_cnt=0 OR ss.term IN :trms)
                AND (:y_cnt=0 OR ss.academic_year IN :yrs)
                AND (
                    (:s_cnt=0 AND COALESCE((SELECT status FROM student_statuses WHERE student_id=s.id ORDER BY id DESC LIMIT 1),'Not Set') != 'Test')
                    OR (:s_cnt>0 AND ss.status IN :stats)
                )
            ORDER BY ss.academic_year DESC, ss.term, s.college, s.id
        """).bindparams(
            bindparam('cls', expanding=True),
            bindparam('trms', expanding=True),
            bindparam('yrs', expanding=True),
            bindparam('stats', expanding=True)
        )
        return fetch_df(engine, sql, common)

    elif rep_format == "Accounting Summary":
        sql = text("""
            SELECT s.id AS "ID", s.name AS "Student Name", s.college AS "College",
                s.email AS "Email",
                COALESCE((SELECT status FROM student_statuses WHERE student_id=s.id ORDER BY id DESC LIMIT 1),'Not Set') AS "Current Status",
                s.current_academic_status AS "Academic Status",
                s.price_per_hr AS "Price/Hr",
                COALESCE(SUM(t.hours_change),0) AS "Reg. Hours",
                COALESCE(SUM(CASE WHEN t.transaction_type IN ('Invoice','Bulk Invoices (Tuition)') THEN t.debit ELSE 0 END),0) AS "Tuition Billed",
                COALESCE(SUM(CASE WHEN t.transaction_type IN ('Other Fees','Bulk Other Fees') THEN t.debit ELSE 0 END),0) AS "Other Fees",
                COALESCE(SUM(CASE WHEN t.transaction_type IN ('Discount','Bulk Scholarships') THEN t.credit-t.debit ELSE 0 END),0) AS "Discounts",
                COALESCE(SUM(CASE WHEN t.transaction_type IN ('Payment Receipt','Bulk Payments') THEN t.credit-t.debit ELSE 0 END),0) AS "Payments",
                COALESCE(SUM(CASE WHEN t.transaction_type IN ('Credit Hours Adjustment','Credit Hours Adjustments','General Adjustment','General Adjustments') THEN t.debit-t.credit ELSE 0 END),0) AS "Adjustments",
                COALESCE(SUM(t.debit)-SUM(t.credit),0) AS "Balance"
            FROM students s LEFT JOIN transactions t ON s.id=t.student_id
                AND (:t_cnt=0 OR t.term IN :trms)
                AND (:y_cnt=0 OR t.academic_year IN :yrs)
            WHERE (:c_cnt=0 OR s.college IN :cls)
                AND (
                    (:s_cnt=0 AND COALESCE((SELECT status FROM student_statuses WHERE student_id=s.id ORDER BY id DESC LIMIT 1),'Not Set') != 'Test')
                    OR (:s_cnt>0 AND COALESCE((SELECT status FROM student_statuses WHERE student_id=s.id ORDER BY id DESC LIMIT 1),'Not Set') IN :stats)
                )
            GROUP BY s.id,s.name,s.college,s.email,s.price_per_hr 
            HAVING COUNT(t.id) > 0 OR (:t_cnt=0 AND :y_cnt=0 AND COALESCE(SUM(t.debit)-SUM(t.credit),0) != 0)
            ORDER BY s.id
        """).bindparams(
            bindparam('cls', expanding=True),
            bindparam('trms', expanding=True),
            bindparam('yrs', expanding=True),
            bindparam('stats', expanding=True)
        )
        df = fetch_df(engine, sql, common)
        if not df.empty:
            num_cols = ["Price/Hr","Reg. Hours","Tuition Billed","Other Fees",
                        "Discounts","Payments","Adjustments","Balance"]
            totals = {}
            for c in df.columns:
                if c in num_cols:
                    totals[c] = df[c].sum()
                elif c == "Student Name":
                    totals[c] = "TOTAL"
                else:
                    totals[c] = ""
            df = pd.concat([df, pd.DataFrame([totals])], ignore_index=True)
            for col in num_cols:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    elif rep_format == "Period Closing (Activity Summary)":
        if not start_date or not end_date:
            raise ValueError("Start and End dates are required for Period Closing.")
            
        params = {**common, "s_date": start_date, "e_date": end_date}
        sql = text("""
            SELECT s.id AS "ID", s.name AS "Student Name", s.college AS "College",
                COALESCE((SELECT status FROM student_statuses WHERE student_id=s.id ORDER BY id DESC LIMIT 1),'Not Set') AS "Current Status",
                COALESCE(SUM(t.hours_change),0) AS "CH Changed",
                COALESCE(SUM(CASE WHEN t.transaction_type IN ('Invoice','Bulk Invoices (Tuition)') THEN t.debit ELSE 0 END),0) AS "Tuition Billed",
                COALESCE(SUM(CASE WHEN t.transaction_type IN ('Other Fees','Bulk Other Fees') THEN t.debit ELSE 0 END),0) AS "Other Fees",
                COALESCE(SUM(CASE WHEN t.transaction_type IN ('Discount','Bulk Scholarships') THEN t.credit-t.debit ELSE 0 END),0) AS "New Discounts",
                COALESCE(SUM(CASE WHEN t.transaction_type IN ('Payment Receipt','Bulk Payments') THEN t.credit-t.debit ELSE 0 END),0) AS "Payments Received",
                COALESCE(SUM(CASE WHEN t.transaction_type IN ('Credit Hours Adjustment','Credit Hours Adjustments','General Adjustment','General Adjustments') THEN t.debit-t.credit ELSE 0 END),0) AS "Adjustments",
                COALESCE(SUM(t.debit)-SUM(t.credit),0) AS "Net Period Change"
            FROM transactions t JOIN students s ON t.student_id=s.id
            WHERE (:c_cnt=0 OR s.college IN :cls)
                AND (:t_cnt=0 OR t.term IN :trms)
                AND (:y_cnt=0 OR t.academic_year IN :yrs)
                AND (
                    (:s_cnt=0 AND COALESCE((SELECT status FROM student_statuses WHERE student_id=s.id ORDER BY id DESC LIMIT 1),'Not Set') != 'Test')
                    OR (:s_cnt>0 AND COALESCE((SELECT status FROM student_statuses WHERE student_id=s.id ORDER BY id DESC LIMIT 1),'Not Set') IN :stats)
                )
                AND t.entry_date BETWEEN :s_date AND :e_date
            GROUP BY s.id,s.name,s.college
            HAVING COALESCE(SUM(t.debit),0)>0 OR COALESCE(SUM(t.credit),0)>0
            ORDER BY s.id
        """).bindparams(
            bindparam('cls', expanding=True),
            bindparam('trms', expanding=True),
            bindparam('yrs', expanding=True),
            bindparam('stats', expanding=True)
        )
        df = fetch_df(engine, sql, params)
        if not df.empty:
            num_cols = ["CH Changed","Tuition Billed","Other Fees","New Discounts",
                        "Payments Received","Adjustments","Net Period Change"]
            totals = {}
            for c in df.columns:
                if c in num_cols:
                    totals[c] = df[c].sum()
                elif c == "Student Name":
                    totals[c] = "TOTAL"
                else:
                    totals[c] = ""
            df = pd.concat([df, pd.DataFrame([totals])], ignore_index=True)
            for col in num_cols:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    elif rep_format == "Full Detailed Log":
        params = {**common,
                  "has_dates": 1 if start_date and end_date else 0,
                  "s_date": start_date,
                  "e_date": end_date}
        sql = text("""
            SELECT t.student_id AS "Student ID", s.name AS "Student Name", s.college AS "College",
                COALESCE((SELECT status FROM student_statuses WHERE student_id=s.id ORDER BY id DESC LIMIT 1),'Not Set') AS "Current Status",
                s.current_academic_status AS "Academic Status",
                t.reference_no AS "Ref No", t.entry_date AS "Date", t.term AS "Term", t.academic_year AS "Year",
                t.description AS "Description", t.hours_change AS "Hours", t.debit AS "Debit", t.credit AS "Credit"
            FROM transactions t JOIN students s ON t.student_id=s.id
            WHERE (:c_cnt=0 OR s.college IN :cls)
                AND (:t_cnt=0 OR t.term IN :trms)
                AND (:y_cnt=0 OR t.academic_year IN :yrs)
                AND (
                    (:s_cnt=0 AND COALESCE((SELECT status FROM student_statuses WHERE student_id=s.id ORDER BY id DESC LIMIT 1),'Not Set') != 'Test')
                    OR (:s_cnt>0 AND COALESCE((SELECT status FROM student_statuses WHERE student_id=s.id ORDER BY id DESC LIMIT 1),'Not Set') IN :stats)
                )
                AND (:has_dates=0 OR (t.entry_date BETWEEN :s_date AND :e_date))
            ORDER BY t.student_id, t.entry_date DESC
        """).bindparams(
            bindparam('cls', expanding=True),
            bindparam('trms', expanding=True),
            bindparam('yrs', expanding=True),
            bindparam('stats', expanding=True)
        )
        return fetch_df(engine, sql, params)
        
    else:
        raise ValueError("Invalid format")


@router.get("/generate")
async def get_report_data(
    format: str,
    colleges: Optional[List[str]] = Query([]),
    terms: Optional[List[str]] = Query([]),
    years: Optional[List[int]] = Query([]),
    statuses: Optional[List[str]] = Query([]),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if format not in FORMATS:
        raise HTTPException(status_code=400, detail="Invalid report format.")
        
    engine = get_db_engine()
    
    try:
        df = generate_report_df(engine, format, colleges, terms, years, statuses, start_date, end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    return {
        "columns": df.columns.tolist() if not df.empty else [],
        "data": df.fillna("").to_dict(orient="records") if not df.empty else []
    }


@router.get("/excel")
async def download_report_excel(
    format: str,
    colleges: Optional[List[str]] = Query([]),
    terms: Optional[List[str]] = Query([]),
    years: Optional[List[int]] = Query([]),
    statuses: Optional[List[str]] = Query([]),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if format not in FORMATS:
        raise HTTPException(status_code=400, detail="Invalid report format.")
        
    engine = get_db_engine()
    
    try:
        df = generate_report_df(engine, format, colleges, terms, years, statuses, start_date, end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    if df.empty:
        raise HTTPException(status_code=404, detail="No data found for the selected criteria.")
        
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="Report_{format.replace(" ","_")}.xlsx"'}
    )
