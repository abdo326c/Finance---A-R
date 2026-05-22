import streamlit as st
from datetime import datetime
from sqlalchemy.sql import func
from sqlalchemy.exc import IntegrityError

from config import VALID_TERMS, DEFAULT_YEAR
from auth import require_role
from models import (
    get_db, Student, Transaction, RefCounter,
    next_ref_block, write_audit,
)
from helpers import build_auto_discount_transactions

TX_TYPES = ["Payment Receipt", "Invoice", "Credit Hours Adjustment", "Other Fees", "General Adjustment"]

def render():
    st.subheader("Post Manual Transaction")
    require_role("Admin", "Editor")

    action = st.selectbox("Action Type", TX_TYPES)
    bypass_dup = st.checkbox("⚠️ Bypass Duplicate Check (force posting)")

    with st.form(f"manual_tx_{action}", clear_on_submit=True):
        default_id = str(st.session_state.get("lookup_id","")) if st.session_state.get("lookup_id",0)>0 else ""
        sid_raw = st.text_input("Student ID", value=default_id, placeholder="e.g. 26100123")

        c1, c2, c3 = st.columns(3)
        ed   = c1.date_input("Date")
        term = c2.selectbox("Term", VALID_TERMS)
        year = c3.number_input("Year", value=DEFAULT_YEAR, step=1)

        dr, cr, dsc, h_change, b_name, b_ref, reg_hours = 0.0, 0.0, "", 0.0, "", "", 0.0

        if action == "Payment Receipt":
            b_name = st.text_input("Bank Name")
            b_ref  = st.text_input("Bank Ref No")
            cr     = st.number_input("Amount Paid (EGP)", min_value=0.0)
            
        elif action == "Invoice":
            reg_hours = st.number_input("Registered Credit Hours", min_value=0.0, step=1.0)
            dsc = st.text_input("Description", value="Tuition Invoice")
            
        elif action == "Credit Hours Adjustment":
            h_change = st.number_input("Hours Delta (+/−)")
            
        elif action == "Other Fees":
            dr  = st.number_input("Fee Amount (EGP)", min_value=0.0)
            dsc = st.text_input("Description")
            
        elif action == "General Adjustment":
            gc1, gc2 = st.columns(2)
            dr  = gc1.number_input("Debit (EGP)",  min_value=0.0)
            cr  = gc2.number_input("Credit (EGP)", min_value=0.0)
            dsc = st.text_input("Description")

        submitted = st.form_submit_button("🚀 Process Transaction")

    if not submitted:
        return

    sid = int(sid_raw) if sid_raw.strip().isdigit() else 0
    if sid == 0:
        st.error("Please enter a valid Student ID.")
        return

    with get_db() as db:
        student = db.get(Student, sid)
        if not student:
            st.error("Student ID not found. Register the student first.")
            return

        # 🛠️ التعديل الأول: أداة التصحيح الذاتي لعداد القيود (Auto-Heal)
        # لو العداد الداخلي متأخر بسبب رفع شيتات إكسيل قبل كده، السيستم هيحدثه فوراً قبل ما يبدأ
        max_tx_id = db.query(func.max(Transaction.id)).scalar() or 0
        ref_row = db.get(RefCounter, 1)
        if ref_row and ref_row.seq <= max_tx_id:
            ref_row.seq = max_tx_id + 500
            db.flush()

        rate = student.price_per_hr or 0.0
        extra_txs = []

        if action == "Payment Receipt":
            pfx, dsc = "PAY", f"Bank: {b_name} | Ref: {b_ref}"
            
        elif action == "Invoice":
            pfx = "INV"
            h_change = reg_hours
            val = reg_hours * rate
            dr, cr = val, 0.0
            dsc = f"Tuition: {h_change} CH @ {rate:,.2f} | {dsc}"
            
            start = next_ref_block(db, 1 + 50)
            extra_txs = build_auto_discount_transactions(
                db, sid, val, term, int(year), ed, ref_start=start+1
            )
            
        elif action == "Credit Hours Adjustment":
            existing_hours = db.query(func.sum(Transaction.hours_change)).filter(
                Transaction.student_id == sid,
                Transaction.term == term,
                Transaction.academic_year == int(year)
            ).scalar() or 0.0

            if existing_hours <= 0:
                st.error(f"🛑 Cannot process adjustment: Student has NO registered hours in {term} {year}.")
                return
                
            if h_change < 0 and abs(h_change) > existing_hours:
                st.error(f"🛑 Invalid Adjustment: Trying to drop {abs(h_change)} hours, but student only has {existing_hours} hours in {term} {year}.")
                return

            pfx       = "ADJ"
            val       = abs(h_change * rate)
            dr, cr    = (val, 0.0) if h_change > 0 else (0.0, val)
            dsc       = f"Adj: {h_change} CH @ {rate:,.2f}"
            start     = next_ref_block(db, 1 + 50)
            extra_txs = build_auto_discount_transactions(
                db, sid, val, term, int(year), ed, ref_start=start+1
            )
            if h_change < 0:
                for t in extra_txs:
                    t.debit, t.credit = t.credit, t.debit
                    
        elif action == "Other Fees":
            pfx = "FEE"
        elif action == "General Adjustment":
            pfx = "TXN"

        if action not in ["Credit Hours Adjustment", "Invoice"]:
            start = next_ref_block(db, 1)

        check_val = dr if dr > 0 else cr
        if not bypass_dup and check_val > 0:
            dup = db.query(Transaction).filter(
                Transaction.student_id       == sid,
                Transaction.transaction_type == action,
                Transaction.entry_date       == ed,
                (Transaction.debit == check_val) | (Transaction.credit == check_val),
            ).first()
            if dup:
                st.error(
                    f"🛑 Duplicate: a {action} of {check_val:,.2f} EGP was already posted "
                    f"today for this student. Enable 'Bypass Duplicate Check' to force it."
                )
                return

        new_tx = Transaction(
            reference_no     = f"{pfx}-{start:06d}",
            student_id       = sid,
            transaction_type = action,
            description      = dsc,
            debit=dr, credit=cr,
            hours_change     = h_change,
            entry_date       = ed,
            term             = term,
            academic_year    = int(year),
        )
        db.add(new_tx)
        for t in extra_txs:
            db.add(t)

        write_audit(
            db, st.session_state["logged_in_user"],
            "POST_TX", f"student_id={sid}",
            f"{action} | {new_tx.reference_no} | dr={dr} cr={cr}",
        )
        
        # 🛠️ التعديل الثاني: حماية الاعتماد (Commit) من انهيار النظام
        try:
            db.commit()
            suffix = f" + {len(extra_txs)} auto-discount(s)" if extra_txs else ""
            st.session_state["flash_msg"] = f"Posted {new_tx.reference_no} for {student.name}{suffix}!"
            st.rerun()
        except IntegrityError:
            db.rollback()
            st.error("🛑 Database Integrity Error: The generated Reference Number already exists. The system has automatically synced the counter. Please click 'Process Transaction' again.")
