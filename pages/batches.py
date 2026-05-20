# pages/batches.py
import io
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.sql import func

from auth import require_role
from models import get_db, Transaction, DeletedBatchLog, write_audit


def render(engine):
    st.subheader("🗑️ Batch Management")

    action = st.radio(
        "Action:",
        ["📂 View Active Batches", "📥 Export Batch Details",
         "🗑️ Delete Batch (Admin Only)", "📜 Deleted Batches History"],
        horizontal=True,
    )

    with get_db() as db:
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

        if action == "📂 View Active Batches":
            if summaries:
                st.dataframe(pd.DataFrame([{
                    "Batch ID": b.batch_id, "Type": b.transaction_type,
                    "Records": b.records,
                    "Total Debit":  f"{b.total_debit:,.2f}",
                    "Total Credit": f"{b.total_credit:,.2f}",
                    "Uploaded At":  b.uploaded_at.strftime("%Y-%m-%d %H:%M") if b.uploaded_at else "—",
                } for b in summaries]), use_container_width=True)
            else:
                st.info("No active batches found.")

        elif action == "📥 Export Batch Details":
            bid = st.text_input("Batch ID to export:", placeholder="e.g. BCH-260417-153000").strip()
            if st.button("📥 Load") and bid:
                sql = text("""
                    SELECT t.reference_no AS "Ref No", s.id AS "Student ID",
                        s.name AS "Student Name", t.transaction_type AS "Type",
                        t.description AS "Description", t.entry_date AS "Date",
                        t.term AS "Term", t.academic_year AS "Year",
                        t.hours_change AS "Hours", t.debit AS "Debit", t.credit AS "Credit"
                    FROM transactions t JOIN students s ON t.student_id=s.id
                    WHERE t.batch_id=:bid ORDER BY t.id
                """)
                df = pd.read_sql(sql, con=engine, params={"bid": bid})
                if df.empty:
                    st.error("Batch ID not found.")
                else:
                    st.success(f"✅ {len(df)} records in {bid}.")
                    st.dataframe(df.style.format({"Hours":"{:,.1f}","Debit":"{:,.2f}","Credit":"{:,.2f}"}),
                                 use_container_width=True)
                    buf = io.BytesIO()
                    df.to_excel(buf, index=False)
                    st.download_button("📗 Download Excel", buf.getvalue(),
                                       file_name=f"Batch_{bid}.xlsx", use_container_width=True)

        elif action == "🗑️ Delete Batch (Admin Only)":
            require_role("Admin")
            if not summaries:
                st.info("No active batches.")
                return
            with st.form("del_batch_form", clear_on_submit=True):
                bid_del  = st.text_input("Batch ID to delete:").strip()
                confirmed= st.checkbox("⚠️ I confirm deletion of this entire batch.")
                if st.form_submit_button("🗑️ Delete"):
                    if not bid_del or not confirmed:
                        st.error("Enter the Batch ID and check the confirmation box.")
                    else:
                        matching = [b for b in summaries if b.batch_id == bid_del]
                        if not matching:
                            st.error(f"Batch '{bid_del}' not found.")
                        else:
                            try:
                                db.add(DeletedBatchLog(
                                    batch_id         = bid_del,
                                    transaction_type = " & ".join({b.transaction_type for b in matching}),
                                    record_count     = sum(b.records for b in matching),
                                    total_debit      = sum(b.total_debit for b in matching),
                                    total_credit     = sum(b.total_credit for b in matching),
                                    deleted_by       = st.session_state.get("logged_in_user"),
                                ))
                                db.query(Transaction).filter(Transaction.batch_id == bid_del).delete()
                                write_audit(db, st.session_state["logged_in_user"],
                                            "DELETE_BATCH", bid_del,
                                            f"{sum(b.records for b in matching)} records removed")
                                db.commit()
                                st.session_state["flash_msg"] = f"Batch {bid_del} deleted."
                                st.rerun()
                            except Exception:
                                db.rollback()
                                st.error("Deletion failed. Try again.")

        elif action == "📜 Deleted Batches History":
            logs = db.query(DeletedBatchLog).order_by(DeletedBatchLog.deleted_at.desc()).all()
            if logs:
                st.dataframe(pd.DataFrame([{
                    "Batch ID":     l.batch_id,
                    "Type(s)":      l.transaction_type,
                    "Records":      l.record_count,
                    "Total Debit":  f"{l.total_debit:,.2f}",
                    "Total Credit": f"{l.total_credit:,.2f}",
                    "Deleted By":   l.deleted_by,
                    "Deleted At":   l.deleted_at.strftime("%Y-%m-%d %H:%M"),
                } for l in logs]), use_container_width=True)
            else:
                st.info("No deleted batches on record.")
