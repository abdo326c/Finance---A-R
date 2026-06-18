# helpers.py
# ─────────────────────────────────────────────
# Business-logic helpers shared across pages:
#   • scholarship discount builders
#   • retroactive adjustment
#   • cap enforcement
# ─────────────────────────────────────────────
import re
from sqlalchemy.sql import func
from models import (
    Student, StudentScholarship, ScholarshipType,
    Transaction, next_ref_block,
)


# ── Normalize percentage to 0–100 ─────────────
def _pct(raw: float) -> float:
    """
    All DB values are stored as 0–100 (e.g. 60.0 for 60%).
    This function is kept for backward compatibility but now simply returns
    the raw value since the migration already standardized everything.
    """
    return raw


# ── Semester Chronology ───────────────────────
def get_semester_rank(term: str, year: int) -> int:
    """
    Ranks a semester chronologically to block future registration if on hold.
    Order: Fall < Spring < Summer.
    Example: Fall 2025 (20251) < Spring 2026 (20262) < Summer 2026 (20263)
    """
    term = term.strip().title()
    term_val = 0
    if term == "Fall":
        term_val = 1
    elif term == "Spring":
        term_val = 2
    elif term == "Summer":
        term_val = 3
    else:
        term_val = 0
    return year * 10 + term_val


# ── Active scholarships for a student/term ────
def get_student_scholarships(db, student_id, term, academic_year):
    rows = (
        db.query(StudentScholarship, ScholarshipType)
        .join(ScholarshipType)
        .filter(
            StudentScholarship.student_id   == student_id,
            StudentScholarship.term         == term,
            StudentScholarship.academic_year== academic_year,
            StudentScholarship.is_active    == True,
        )
        .all()
    )
    return [
        {"scholarship_type_id": ss.scholarship_type_id,
         "name": st_type.name,
         "percentage": _pct(ss.percentage)}
        for ss, st_type in rows
    ]


# ── Build discount transactions for a new invoice ──
def build_auto_discount_transactions(
    db, student_id, gross_amount, term, academic_year,
    entry_date, ref_start: int, batch_id=None
):
    scholarships = get_student_scholarships(db, student_id, term, academic_year)
    if not scholarships:
        return []

    discount_txs, accumulated_pct = [], 0.0
    counter = ref_start

    for sch in scholarships:
        requested_pct = sch["percentage"]
        if requested_pct <= 0:
            continue
        actual_pct = min(requested_pct, max(0.0, 100.0 - accumulated_pct))
        accumulated_pct += actual_pct
        credit_val = gross_amount * (actual_pct / 100.0)
        capped = actual_pct < requested_pct
        desc = (
            f"{sch['name']} ({actual_pct:.1f}%)"
            + (f" (Capped from {requested_pct:.1f}%)" if capped else "")
        )
        discount_txs.append(
            Transaction(
                reference_no        = f"SCH-{counter:06d}",
                batch_id            = batch_id,
                student_id          = student_id,
                scholarship_type_id = sch["scholarship_type_id"],
                transaction_type    = "Discount",
                description         = desc,
                hours_change        = 0.0,
                debit               = 0.0,
                credit              = credit_val,
                entry_date          = entry_date,
                term                = term,
                academic_year       = academic_year,
            )
        )
        counter += 1
        if accumulated_pct >= 100.0:
            break
    return discount_txs


# ── Retroactive scholarship adjustment ────────
def get_retroactive_scholarship_tx(
    db, student_id, term, academic_year,
    sch_type_id, sch_name, requested_pct: float,
    ref_num: int, batch_id=None, internal_note=None
):
    """
    Computes the delta between what was already discounted for this
    scholarship type and what *should* have been discounted, then
    returns a corrective Transaction (or None if balanced).
    `requested_pct` is always 0–100.
    """
    net_billed = (
        db.query(func.sum(Transaction.debit - Transaction.credit))
        .filter(
            Transaction.student_id    == student_id,
            Transaction.term          == term,
            Transaction.academic_year == academic_year,
            Transaction.transaction_type.in_([
                "Invoice", "Bulk Invoices (Tuition)",
                "Credit Hours Adjustment", "Credit Hours Adjustments",
            ]),
        )
        .scalar() or 0.0
    )
    if net_billed <= 0:
        return None

    other_pct = 0.0
    other_active = (
        db.query(StudentScholarship.percentage)
        .filter(
            StudentScholarship.student_id == student_id,
            StudentScholarship.term == term,
            StudentScholarship.academic_year == academic_year,
            StudentScholarship.is_active == True,
            StudentScholarship.scholarship_type_id != sch_type_id,
        )
        .all()
    )
    for (pct,) in other_active:
        other_pct += pct

    actual_pct = min(requested_pct, max(0.0, 100.0 - other_pct))
    target     = net_billed * (actual_pct / 100.0)

    existing = (
        db.query(func.sum(Transaction.credit - Transaction.debit))
        .filter(
            Transaction.student_id       == student_id,
            Transaction.term             == term,
            Transaction.academic_year    == academic_year,
            Transaction.scholarship_type_id == sch_type_id,
            Transaction.reference_no.like("SCH-%"),
        )
        .scalar() or 0.0
    )

    diff = target - existing
    if abs(diff) <= 0.01:
        return None

    capped = actual_pct < requested_pct
    desc = (
        f"Retroactive: {sch_name} ({actual_pct:.1f}%)"
        + (f" (Capped from {requested_pct:.1f}%)" if capped else "")
    )
    return Transaction(
        reference_no        = f"SCH-{ref_num:06d}",
        batch_id            = batch_id,
        student_id          = student_id,
        scholarship_type_id = sch_type_id,
        transaction_type    = "Discount",
        description         = desc,
        internal_note       = internal_note,
        hours_change        = 0.0,
        debit               = abs(diff) if diff < 0 else 0.0,
        credit              = diff      if diff > 0 else 0.0,
        entry_date          = __import__("datetime").date.today(),
        term                = term,
        academic_year       = academic_year,
    )


# ── Cap enforcement (max 100 % per student/term) ──
def enforce_scholarship_cap(db, student_id, term, academic_year):
    active = (
        db.query(StudentScholarship, ScholarshipType)
        .join(ScholarshipType)
        .filter(
            StudentScholarship.student_id    == student_id,
            StudentScholarship.term          == term,
            StudentScholarship.academic_year == academic_year,
            StudentScholarship.is_active     == True,
        )
        .order_by(StudentScholarship.id.asc())
        .all()
    )
    if not active:
        return []

    deactivated, running = [], 0.0
    for ss, st_type in active:
        pct = _pct(ss.percentage)
        if running + pct > 100.0:
            remaining = round(100.0 - running, 4)
            if remaining > 0:
                # Cap the percentage instead of fully deactivating
                ss.percentage = remaining
                running = 100.0
            else:
                ss.is_active = False
                deactivated.append(st_type.name)
        else:
            running += pct
    return deactivated
