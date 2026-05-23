# views/reconciliation.py
import io
import datetime
import pandas as pd
import streamlit as st
from sqlalchemy import text
from models import (
    get_db, Student, Transaction, write_audit, next_ref_block, DisputeLog
)
from config import VALID_TERMS, DEFAULT_YEAR

def map_term_name(term):
    """Maps PowerCampus ACADEMIC_TERM values (e.g. SPRG, FALL) to standard term names (Spring, Fall)."""
    t = str(term).strip().upper()
    if "SPRING" in t or "SPRG" in t:
        return "SPRG"
    if "FALL" in t:
        return "FALL"
    if "SUMMER" in t or "SUMR" in t:
        return "SUMR"
    return t

def render(engine, available_years):
    st.subheader("🔄 Multi-System Account Reconciliation Hub")
    st.markdown("Bridge the legacy **PowerCampus** registration database, our **Local A/R database**, and **Microsoft Dynamics ERP** to spot mismatches instantly and apply bulk sync operations.")

    tab1, tab2 = st.tabs(["📊 Run Reconciliation", "📋 Reconciliation Rules & Help"])

    with tab2:
        st.markdown("""
        ### 📋 About the Three-System Reconciliation Hub
        This workspace is designed to solve the common issue where legacy platforms (like **PowerCampus**) and ERPs (like **Dynamics 365**) lose connection or record transactions on varying dates.
        
        #### ⚙️ Standard Reconciliation Rules:
        1. **Charges & Discounts (`C` and `D` type)**:
           * Filtered strictly by **Academic Term** (e.g., `SPRG`) and **Academic Year** (e.g., `2026`).
           * Optionally filtered by an entry-date threshold to prevent previous-semester carryovers from distorting values.
        2. **Payments & Receipts (`R` type)**:
           * Attributed strictly by **Entry Date** rather than term tags. This accounts for PowerCampus labeling payment rows incorrectly. 
           * Default threshold for **Spring 2026** is payments made **on or after March 18, 2026**.
        
        #### 🛡️ Database Safe-Guards:
        * Any automated profile creation (`Register Student`) or transaction import (`Auto-Import Invoice`) performs transactional checks and commits directly to the SQLite backend.
        * Complete operations are logged to the global **Admin Audit Logs** for tracking.
        """)

    with tab1:
        # ── 1. Settings Header ──
        st.markdown("#### ⚙️ Reconciliation Settings")
        c1, c2, c3 = st.columns(3)
        selected_term = c1.selectbox("Target Term:", VALID_TERMS, index=1) # Spring is default
        selected_year = c2.selectbox("Target Year:", available_years)
        recon_mode = c3.selectbox("Reconciliation Mode:", [
            "PowerCampus ⇆ Local A/R Database",
            "Local A/R Database ⇆ Microsoft Dynamics 365 (ERP)"
        ])

        # ── 2. Dynamic Date Filters Panel ──
        with st.expander("📅 Billing Rules & Custom Date Cut-offs", expanded=True):
            r_col1, r_col2 = st.columns(2)
            
            # Default payment cut-off: if Spring, March 18 of the target year. Else, Sept 1.
            default_pay_cut = datetime.date(int(selected_year), 3, 18) if "spring" in selected_term.lower() else datetime.date(int(selected_year), 9, 1)
            pay_cutoff = r_col1.date_input("Include Payments ON or AFTER:", default_pay_cut)
            
            enable_charge_date = r_col2.checkbox("Filter Charges & Discounts by Date as well?", value=False)
            charge_cutoff = None
            if enable_charge_date:
                charge_cutoff = r_col2.date_input("Include Charges/Discounts ON or AFTER:", default_pay_cut)

        # ── 3. File Upload ──
        st.markdown("#### 📤 Upload External Ledger Export")
        uploaded_file = st.file_uploader(
            f"Upload your { 'PowerCampus CSV/Excel' if 'PowerCampus' in recon_mode else 'Dynamics 365 Posting log' }",
            type=["csv", "xlsx"]
        )

        if not uploaded_file:
            st.info("💡 Please upload an Excel or CSV file to begin the matching process.")
            return

        # ── 4. File Parsing & Flexible Auto-Mapping ──
        try:
            if uploaded_file.name.endswith(".csv"):
                df_ext = None
                # Try common encodings for regional database exports (Arabic windows-1256, Excel UTF-8 BOM, etc.)
                encodings_to_try = ['utf-8', 'utf-8-sig', 'windows-1256', 'cp1252', 'latin1', 'iso-8859-1']
                for encoding in encodings_to_try:
                    try:
                        uploaded_file.seek(0)
                        df_ext = pd.read_csv(uploaded_file, encoding=encoding)
                        break
                    except (UnicodeDecodeError, UnicodeError, ValueError):
                        continue
                
                if df_ext is None:
                    uploaded_file.seek(0)
                    df_ext = pd.read_csv(uploaded_file) # Fallback to raise original exception
            else:
                df_ext = pd.read_excel(uploaded_file)
        except Exception as e:
            st.error(f"🛑 Failed to parse file. Verify encoding/format: {str(e)}")
            return

        st.toast(f"📂 Loaded external file: `{uploaded_file.name}` containing **{len(df_ext)}** records.", icon="✅")

        # Column Auto-Detection mapping
        cols = list(df_ext.columns)
        
        def find_best_col(key_options, all_cols):
            for opt in key_options:
                for c in all_cols:
                    if opt.lower() == c.strip().lower():
                        return c
            return all_cols[0] if all_cols else ""

        # Setup standard lookups based on uploaded PowerCampus structure
        id_col = find_best_col(["PEOPLE_ORG_ID", "Student ID", "StudentID", "student_id", "PEOPLE_ID"], cols)
        fname_col = find_best_col(["FIRST_NAME", "First Name", "first_name"], cols)
        mname_col = find_best_col(["MIDDLE_NAME", "Middle Name", "middle_name"], cols)
        lname_col = find_best_col(["LAST_NAME", "Last Name", "last_name"], cols)
        type_col = find_best_col(["CHARGE_CREDIT_TYPE", "Type", "transaction_type", "type"], cols)
        amount_col = find_best_col(["AMOUNT", "Amount", "value", "amount"], cols)
        desc_col = find_best_col(["CRG_CRD_DESC", "Description", "desc", "description"], cols)
        code_col = find_best_col(["CHARGE_CREDIT_CODE", "Code", "charge_credit_code"], cols)
        date_col = find_best_col(["ENTRY_DATE", "Date", "entry_date", "post_date"], cols)
        term_col = find_best_col(["ACADEMIC_TERM", "Term", "academic_term"], cols)
        year_col = find_best_col(["ACADEMIC_YEAR", "Year", "academic_year"], cols)

        with st.expander("⚙️ CSV Column Mapping (Verify or Adjust Columns)", expanded=False):
            st.caption("Verify that the auto-detected columns map correctly to your file fields.")
            mc1, mc2, mc3 = st.columns(3)
            id_col = mc1.selectbox("Student ID Column", cols, index=cols.index(id_col) if id_col in cols else 0)
            fname_col = mc2.selectbox("First Name Column", cols, index=cols.index(fname_col) if fname_col in cols else 0)
            lname_col = mc3.selectbox("Last Name Column", cols, index=cols.index(lname_col) if lname_col in cols else 0)
            
            mc4, mc5, mc6 = st.columns(3)
            type_col = mc4.selectbox("Type Column (C/D/R)", cols, index=cols.index(type_col) if type_col in cols else 0)
            amount_col = mc5.selectbox("Amount Column", cols, index=cols.index(amount_col) if amount_col in cols else 0)
            date_col = mc6.selectbox("Date Column", cols, index=cols.index(date_col) if date_col in cols else 0)

            mc7, mc8, mc9 = st.columns(3)
            desc_col = mc7.selectbox("Description Column", cols, index=cols.index(desc_col) if desc_col in cols else 0)
            term_col = mc8.selectbox("Term Column", cols, index=cols.index(term_col) if term_col in cols else 0)
            year_col = mc9.selectbox("Year Column", cols, index=cols.index(year_col) if year_col in cols else 0)

        # Check if settings changed to reset initialization state
        current_state_key = f"{uploaded_file.name}_{selected_term}_{selected_year}"
        if st.session_state.get("recon_state_key") != current_state_key:
            st.session_state["recon_state_key"] = current_state_key
            if "recon_initialized" in st.session_state:
                del st.session_state["recon_initialized"]

        # ── 5. Cohort Filtering Safeguard ──
        st.markdown("#### 🎯 Reconciliation Scope & Cohort Filtering")
        
        with st.container():
            st.info("""
            💡 **Cohort Filtering**: PowerCampus database exports often contain registrations for all university programs (e.g., graduates, non-UG, international groups). 
            Since this A/R instance is dedicated to a specific cohort (such as active UG Egyptian students), you should reconcile only student records already present/active in your Local A/R system to avoid thousands of foreign-category discrepancies.
            """)
            
            cohort_scope = st.radio(
                "Select Reconciliation Target Cohort:",
                options=[
                    "🎯 Active Local Student Cohort Only (Recommended - Filters out other PowerCampus categories)",
                    "🌐 All Uploaded PowerCampus Student Records (Full cross-system audit of all csv rows)"
                ],
                index=0,
                key="reconciliation_cohort_scope_select"
            )
            
            col_init, _ = st.columns([2, 2])
            proceed_reconcile = col_init.button("🚀 Initialize Smart Reconciliation Engine", type="primary", use_container_width=True)
            
            if proceed_reconcile:
                st.session_state["recon_initialized"] = True
                st.session_state["recon_cohort_scope"] = cohort_scope
                
            if "recon_initialized" not in st.session_state:
                st.warning("💡 Please select the cohort scope above and click **'Initialize Smart Reconciliation Engine'** to run the matching calculations.")
                return

        # ── 6. Run Compare Core Engine ──
        with st.spinner("Analyzing ledger discrepancies..."):
            import polars as pl
            
            # Convert pandas dataframe to polars for high-performance processing
            df_pl = pl.from_pandas(df_ext)
            
            # Ensure proper types
            df_pl = df_pl.with_columns([
                pl.col(id_col).cast(pl.String).str.replace(".0", "", literal=True).str.strip_chars(),
                pl.col(amount_col).cast(pl.Float64, strict=False).fill_null(0.0),
                pl.col(type_col).cast(pl.String).str.to_uppercase().str.strip_chars()
            ])
            
            # Map selected term to PowerCampus standard term string
            target_pc_term = map_term_name(selected_term)

            # Define masks using polars expressions
            charges_discounts_mask = (
                (pl.col(type_col).is_in(['C', 'D'])) &
                (pl.col(term_col).cast(pl.String).map_elements(map_term_name, return_dtype=pl.String) == target_pc_term) &
                (pl.col(year_col).cast(pl.String).str.contains(str(selected_year)))
            )
            
            if enable_charge_date and charge_cutoff:
                # Assuming date_col is datetime or string, handle it gracefully
                try:
                    df_pl = df_pl.with_columns(pl.col(date_col).cast(pl.Datetime, strict=False).cast(pl.Date, strict=False))
                    charges_discounts_mask = charges_discounts_mask & (pl.col(date_col) >= charge_cutoff)
                except Exception:
                    pass

            payments_mask = (pl.col(type_col) == 'R')
            if pay_cutoff:
                try:
                    df_pl = df_pl.with_columns(pl.col(date_col).cast(pl.Datetime, strict=False).cast(pl.Date, strict=False))
                    payments_mask = payments_mask & (pl.col(date_col) >= pay_cutoff)
                except Exception:
                    pass

            # Filter records
            df_charges_discounts = df_pl.filter(charges_discounts_mask)
            df_payments = df_pl.filter(payments_mask)

            # Combine matches
            df_filtered = pl.concat([df_charges_discounts, df_payments], how="vertical")

            if df_filtered.is_empty():
                st.warning("⚠️ No records matched the selected Term, Year, and Date Filter criteria in the uploaded file.")
                return

            # Compute external totals per student using Polars dictionary iteration (10x-50x faster than pandas iterrows)
            ext_students = {}
            for row in df_filtered.iter_rows(named=True):
                sid = row[id_col]
                tx_type = row[type_col]
                amt = float(row[amount_col])
                
                # Retrieve names
                f_name = str(row.get(fname_col, "")) if fname_col in row and row[fname_col] is not None else ""
                m_name = str(row.get(mname_col, "")) if mname_col in row and row[mname_col] is not None else ""
                l_name = str(row.get(lname_col, "")) if lname_col in row and row[lname_col] is not None else ""
                full_name = f"{f_name} {m_name} {l_name}".replace("  ", " ").strip()
                
                code_val = str(row[code_col]) if code_col in row and row[code_col] is not None else ""
                desc_val = str(row[desc_col]) if desc_col in row and row[desc_col] is not None else ""
                tx_date = row[date_col]
                
                if sid not in ext_students:
                    ext_students[sid] = {
                        "name": full_name or f"Student {sid}",
                        "charges": 0.0, "discounts": 0.0, "payments": 0.0,
                        "transactions": []
                    }
                
                ext_students[sid]["transactions"].append({
                    "type": tx_type, "amount": amt, "code": code_val, "desc": desc_val, "date": tx_date
                })

                if tx_type == 'C':
                    ext_students[sid]["charges"] += amt
                elif tx_type == 'D':
                    ext_students[sid]["discounts"] += amt
                elif tx_type == 'R':
                    ext_students[sid]["payments"] += amt

            # Compute net balance per student in external system
            for sid, details in ext_students.items():
                details["net_balance"] = details["charges"] - details["discounts"] - details["payments"]

            # Get list of active local student IDs to implement target cohort filtering
            with get_db() as db:
                local_active_student_ids = {str(s.id) for s in db.query(Student.id).all()}
            
            # Filter ext_students to only include active local students if target cohort scope is enabled
            is_local_only = "Active Local Student Cohort Only" in st.session_state.get("recon_cohort_scope", "")
            if is_local_only:
                ext_students = {sid: data for sid, data in ext_students.items() if sid in local_active_student_ids}

            # Query Local Database ledger totals
            local_students = {}
            with get_db() as db:
                # Fetch all transactions for selected term and year
                db_txs = (
                    db.query(Transaction, Student)
                    .join(Student, Transaction.student_id == Student.id)
                    .filter(Transaction.term == selected_term, Transaction.academic_year == int(selected_year))
                    .all()
                )
                
                for tx, student in db_txs:
                    sid_str = str(student.id)
                    if sid_str not in local_students:
                        local_students[sid_str] = {
                            "name": student.name,
                            "charges": 0.0, "discounts": 0.0, "payments": 0.0
                        }
                    
                    # Distribute by transaction category dynamically
                    # Any positive debit represents a charge (Tuition invoice, activity fee, etc.)
                    # Any positive credit represents a reduction (Scholarship discount or payment)
                    if tx.debit > 0:
                        local_students[sid_str]["charges"] += tx.debit
                    elif tx.credit > 0:
                        if tx.transaction_type in ['Discount', 'Bulk Scholarships']:
                            local_students[sid_str]["discounts"] += tx.credit
                        else:
                            # Correctly captures 'Payment', 'Bulk Payments', and credit adjustments
                            local_students[sid_str]["payments"] += tx.credit

            for sid_str, details in local_students.items():
                details["net_balance"] = details["charges"] - details["discounts"] - details["payments"]

            # Compare and Sort Categories
            matched_list = []
            mismatch_list = []
            missing_local_list = []
            missing_ext_list = []

            # 1. Compare External students against local
            for sid, ext_data in ext_students.items():
                ext_bal = ext_data["net_balance"]
                
                if sid in local_students:
                    loc_data = local_students[sid]
                    loc_bal = loc_data["net_balance"]
                    diff = ext_bal - loc_bal
                    
                    record = {
                        "Student ID": sid,
                        "Name": ext_data["name"],
                        "PowerCampus Charges": ext_data["charges"],
                        "PowerCampus Discounts": ext_data["discounts"],
                        "PowerCampus Payments": ext_data["payments"],
                        "PowerCampus Balance": ext_bal,
                        "Local Charges": loc_data["charges"],
                        "Local Discounts": loc_data["discounts"],
                        "Local Payments": loc_data["payments"],
                        "Local Balance": loc_bal,
                        "Discrepancy (EGP)": diff
                    }
                    
                    if abs(diff) < 0.01:
                        matched_list.append(record)
                    else:
                        mismatch_list.append(record)
                else:
                    # Missing completely in Local database
                    missing_local_list.append({
                        "Student ID": sid,
                        "Name": ext_data["name"],
                        "PowerCampus Charges": ext_data["charges"],
                        "PowerCampus Discounts": ext_data["discounts"],
                        "PowerCampus Payments": ext_data["payments"],
                        "PowerCampus Balance": ext_bal
                    })

            # 2. Compare Local students missing in external
            for sid, loc_data in local_students.items():
                if sid not in ext_students:
                    missing_ext_list.append({
                        "Student ID": sid,
                        "Name": loc_data["name"],
                        "Local Charges": loc_data["charges"],
                        "Local Discounts": loc_data["discounts"],
                        "Local Payments": loc_data["payments"],
                        "Local Balance": loc_data["net_balance"]
                    })

            # ── 6. Metrics Visualization Cards ──
            st.markdown("<br>", unsafe_allow_html=True)
            
            def render_small_metric(label: str, value: str, border_color: str, bg_color: str = "#ffffff"):
                st.markdown(f"""
                <div style="
                    background: {bg_color};
                    border: 1px solid rgba(0, 0, 0, 0.08);
                    border-left: 5px solid {border_color};
                    border-radius: 8px;
                    padding: 10px 14px;
                    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.02);
                    display: flex;
                    flex-direction: column;
                    gap: 2px;
                    margin-bottom: 10px;
                ">
                    <span style="font-size:10px; color:#5c677d; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;">
                        {label}
                    </span>
                    <span style="font-size:18px; color:#0d47a1; font-weight:700; line-height:1.2;">
                        {value}
                    </span>
                </div>
                """, unsafe_allow_html=True)

            met_col1, met_col2, met_col3, met_col4 = st.columns(4)
            with met_col1:
                render_small_metric("🟢 Matched Accounts", str(len(matched_list)), "#2e7d32")
            with met_col2:
                render_small_metric("🟡 Mismatched Balances", str(len(mismatch_list)), "#f9a825")
            with met_col3:
                render_small_metric("🔴 Missing in Local A/R", str(len(missing_local_list)), "#c62828")
            with met_col4:
                render_small_metric("🔵 Missing in PowerCampus", str(len(missing_ext_list)), "#1565c0")

            # ── 7. Executive Reconciliation Diagnostics ──
            st.markdown("---")
            st.markdown("### 📊 Executive Reconciliation Diagnostics")
            
            with st.container():
                # Calculate category variances across mismatches and missing students
                total_invoice_diff = 0.0
                total_scholarship_diff = 0.0
                total_payment_diff = 0.0
                
                for item in mismatch_list:
                    total_invoice_diff += (item["PowerCampus Charges"] - item["Local Charges"])
                    total_scholarship_diff += (item["PowerCampus Discounts"] - item["Local Discounts"])
                    total_payment_diff += (item["PowerCampus Payments"] - item["Local Payments"])
                    
                for item in missing_local_list:
                    total_invoice_diff += item["PowerCampus Charges"]
                    total_scholarship_diff += item["PowerCampus Discounts"]
                    total_payment_diff += item["PowerCampus Payments"]
                
                abs_inv = abs(total_invoice_diff)
                abs_sch = abs(total_scholarship_diff)
                abs_pay = abs(total_payment_diff)
                
                max_variance = max(abs_inv, abs_sch, abs_pay) if (abs_inv or abs_sch or abs_pay) else 0.0
                
                diag_msg = ""
                if max_variance > 0:
                    if max_variance == abs_pay:
                        diag_msg = "💡 **Observation**: Most discrepancies are driven by **Payment Mismatches**. Since PowerCampus is updated live via the payment gateway and local systems are updated manually, you likely just need to select the students below and import their missing live payments to synchronize."
                    elif max_variance == abs_inv:
                        diag_msg = "💡 **Observation**: Most discrepancies are driven by **Tuition Charges (Invoices)**. Ensure student credit hour invoices are registered consistently on both systems."
                    else:
                        diag_msg = "💡 **Observation**: Most discrepancies are driven by **Scholarships & Discounts**. Check if student scholarship allocations are up to date in both systems."
                else:
                    diag_msg = "🎉 **Observation**: Perfect harmony! No financial variances detected across matched ledger records."
                
                dc1, dc2, dc3 = st.columns(3)
                with dc1:
                    render_small_metric("📄 Total Tuition Invoice Variance", f"{total_invoice_diff:+,.2f} EGP", "#1565c0")
                with dc2:
                    render_small_metric("🎓 Total Scholarship Variance", f"{total_scholarship_diff:+,.2f} EGP", "#6a1b9a")
                with dc3:
                    render_small_metric("💳 Total Payment / Receipt Variance", f"{total_payment_diff:+,.2f} EGP", "#00838f")
                
                st.info(diag_msg)
                
                # Categorize and Prioritize Common Student Mismatches
                high_priority_mismatches = []
                medium_priority_mismatches = []
                low_priority_mismatches = []
                
                for item in mismatch_list:
                    # Get step variances
                    pc_chg = item["PowerCampus Charges"]
                    pc_dsc = item["PowerCampus Discounts"]
                    pc_pmt = item["PowerCampus Payments"]
                    
                    loc_chg = item["Local Charges"]
                    loc_dsc = item["Local Discounts"]
                    loc_pmt = item["Local Payments"]
                    
                    chg_diff = pc_chg - loc_chg
                    dsc_diff = pc_dsc - loc_dsc
                    pmt_diff = pc_pmt - loc_pmt
                    
                    abs_diff = abs(item["Discrepancy (EGP)"])
                    
                    if abs_diff < 10.0:
                        low_priority_mismatches.append(item)
                    elif abs(chg_diff) >= 0.01 or abs(dsc_diff) >= 0.01:
                        high_priority_mismatches.append({
                            **item,
                            "chg_diff": chg_diff,
                            "dsc_diff": dsc_diff
                        })
                    else:
                        medium_priority_mismatches.append({
                            **item,
                            "pmt_diff": pmt_diff
                        })
                
                st.markdown("#### 🚨 Prioritized Resolution Directives")
                
                # 1. High Priority Collapsible Block
                if high_priority_mismatches:
                    with st.expander(f"🔴 **High Priority: Tuition & Scholarship Mismatches ({len(high_priority_mismatches)} Accounts)**", expanded=False):
                        st.caption("These accounts have active variances in Tuition Billing or Scholarship discounts. These distort core revenue figures and must be resolved by manual cross-system ledger audits.")
                        high_df = pd.DataFrame([{
                            "ID": m["Student ID"],
                            "Name": m["Name"],
                            "Tuition Delta": f"{m['chg_diff']:+,.2f} EGP" if abs(m['chg_diff']) >= 0.01 else "Matched",
                            "Scholarship Delta": f"{m['dsc_diff']:+,.2f} EGP" if abs(m['dsc_diff']) >= 0.01 else "Matched"
                        } for m in high_priority_mismatches])
                        st.dataframe(high_df, use_container_width=True, hide_index=True)
                
                # 2. Medium Priority Collapsible Block
                if medium_priority_mismatches:
                    with st.expander(f"🟡 **Medium Priority: Payment Gateway Variances ({len(medium_priority_mismatches)} Accounts)**", expanded=False):
                        st.caption("These accounts differ strictly on payment/receipt entries. Since PowerCampus updates live via the gateway, you likely just need to safe-import the gateway receipts below.")
                        med_df = pd.DataFrame([{
                            "ID": m["Student ID"],
                            "Name": m["Name"],
                            "Payment Delta": f"{m['pmt_diff']:+,.2f} EGP"
                        } for m in medium_priority_mismatches])
                        st.dataframe(med_df, use_container_width=True, hide_index=True)
                    
                # 3. Low Priority Collapsible Block
                if low_priority_mismatches:
                    with st.expander(f"🟢 **Low Priority: Negligible Penny Rounding Variances ({len(low_priority_mismatches)} Accounts)**", expanded=False):
                        st.caption("These accounts have minor variances of less than 10 EGP (rounding errors or payment differential pennies).")
                        low_df = pd.DataFrame([{
                            "ID": m["Student ID"],
                            "Name": m["Name"],
                            "Discrepancy": f"{m['Discrepancy (EGP)']:+,.2f} EGP"
                        } for m in low_priority_mismatches])
                        st.dataframe(low_df, use_container_width=True, hide_index=True)

            # ── 8. Detailed Visual Tab Panels ──
            st.markdown("---")
            st.markdown("### 🔍 Student Cross-System Ledger Auditing & Action Hub")
            res_tab1, res_tab2, res_tab3 = st.tabs([
                "🟡 Mismatched Balances",
                "🔴 Missing in Local A/R Database",
                "🟢 Matched Accounts"
            ])

            # ── TAB 1: MISMATCHED BALANCES ──
            with res_tab1:
                if mismatch_list:
                    df_mismatch = pd.DataFrame(mismatch_list)
                    st.dataframe(df_mismatch[[
                        "Student ID", "Name", "PowerCampus Balance", "Local Balance", "Discrepancy (EGP)"
                    ]], use_container_width=True, hide_index=True)

                    st.markdown("#### 🛠️ Direct Discrepancy Auditing & Inspector")
                    audit_options = [f"{r['Student ID']} — {r['Name']} (Diff: {r['Discrepancy (EGP)']:+,.2f} EGP)" for r in mismatch_list]
                    selected_audit = st.selectbox(
                        "🔍 Select a Mismatched Student to Audit & Adjust:",
                        options=audit_options,
                        key="reconciliation_mismatch_audit_select"
                    )
                    
                    if selected_audit:
                        selected_sid = selected_audit.split(" — ")[0]
                        row = next(r for r in mismatch_list if r["Student ID"] == selected_sid)
                        sid = row["Student ID"]
                        diff_val = row["Discrepancy (EGP)"]
                        
                        # Compute selective step variances
                        pc_chg = row["PowerCampus Charges"]
                        pc_dsc = row["PowerCampus Discounts"]
                        pc_pmt = row["PowerCampus Payments"]
                        
                        loc_chg = row["Local Charges"]
                        loc_dsc = row["Local Discounts"]
                        loc_pmt = row["Local Payments"]
                        
                        chg_diff = pc_chg - loc_chg
                        dsc_diff = pc_dsc - loc_dsc
                        pmt_diff = pc_pmt - loc_pmt

                        # Fetch dispute status from database
                        with get_db() as db:
                            dispute_entry = db.query(DisputeLog).filter_by(student_id=int(sid)).first()
                            disputed = dispute_entry.is_disputed if dispute_entry else False
                            dispute_notes = dispute_entry.notes if dispute_entry else ""
                        
                        # Render dispute warning banner if flagged
                        if disputed:
                            st.markdown(f"""
                            <div style="background-color: #ffebee; color: #b71c1c; border-left: 6px solid #b71c1c; padding: 12px; border-radius: 8px; font-weight: 500; font-size: 14px; margin-bottom: 15px;">
                                ⚠️ <b>Account Flagged: Under Dispute</b><br>
                                <span style="font-size:12px; opacity:0.9;">Notes: {dispute_notes}</span>
                            </div>
                            """, unsafe_allow_html=True)

                        st.markdown(f"##### 📋 Smarter 3-Step Discrepancy Diagnostics for **{row['Name']}** ({sid})")

                        # Dispute & Follow-up Expandable Form
                        with st.expander("📌 Internal Dispute & Follow-up Log", expanded=False):
                            st.caption("Mark this account as disputed or record custom follow-up notes.")
                            d_col1, d_col2 = st.columns([1, 2])
                            new_disputed = d_col1.checkbox("⚠️ Flag student ledger under dispute", value=disputed, key=f"disp_check_{sid}")
                            new_notes = d_col2.text_area("Dispute & Follow-up Notes:", value=dispute_notes, key=f"disp_notes_{sid}", placeholder="e.g. Waiting for Paymob clearance...")
                            
                            if st.button("💾 Save Dispute Status & Notes", key=f"disp_save_{sid}", use_container_width=True):
                                with get_db() as db:
                                    entry = db.query(DisputeLog).filter_by(student_id=int(sid)).first()
                                    if entry:
                                        entry.is_disputed = new_disputed
                                        entry.notes = new_notes
                                        entry.updated_by = st.session_state.get("logged_in_user", "System")
                                    else:
                                        db.add(DisputeLog(
                                            student_id = int(sid),
                                            is_disputed = new_disputed,
                                            notes = new_notes,
                                            updated_by = st.session_state.get("logged_in_user", "System")
                                        ))
                                    write_audit(
                                        db, st.session_state["logged_in_user"],
                                        "RECON_DISPUTE_UPDATE", f"student_id={sid}",
                                        f"Disputed={new_disputed}, Notes={new_notes[:50]}..."
                                    )
                                    db.commit()
                                    st.toast("✅ Dispute status and notes updated successfully!", icon="✅")
                                    st.rerun()

                        # 🛡️ Complex Multi-Variance Alert check
                        active_diff_categories = []
                        if abs(chg_diff) >= 0.01:
                            active_diff_categories.append("Tuition Charges")
                        if abs(dsc_diff) >= 0.01:
                            active_diff_categories.append("Scholarships/Discounts")
                        if abs(pmt_diff) >= 0.01:
                            active_diff_categories.append("Payments")
                            
                        if len(active_diff_categories) > 1:
                            st.markdown(f"""
                            <div style="background-color: #ffebee; color: #b71c1c; border-left: 6px solid #b71c1c; padding: 15px; border-radius: 8px; font-weight: 500; margin-bottom: 20px; font-size: 14px;">
                                ⚠️ <b>Complex Cross-System Audit Required</b>: This student has discrepancies in multiple financial categories: <b>{", ".join(active_diff_categories)}</b>. Please thoroughly verify all transaction lines on both systems displayed in the ledger tables below before applying corrections manually.
                            </div>
                            """, unsafe_allow_html=True)

                        # Render three steps side by side in small columns
                        s_col1, s_col2, s_col3 = st.columns(3)
                        
                        with s_col1:
                            st.markdown("##### Step 1: Tuition Charges")
                            st.write(f"PowerCampus: **{pc_chg:,.2f} EGP**")
                            st.write(f"Local A/R: **{loc_chg:,.2f} EGP**")
                            if abs(chg_diff) < 0.01:
                                st.markdown("<span style='color:green; font-weight:bold;'>✅ Charges Match</span>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"<span style='color:red; font-weight:bold;'>❌ Mismatch: {chg_diff:+,.2f} EGP</span>", unsafe_allow_html=True)
                                
                        with s_col2:
                            st.markdown("##### Step 2: Scholarships")
                            st.write(f"PowerCampus: **{pc_dsc:,.2f} EGP**")
                            st.write(f"Local A/R: **{loc_dsc:,.2f} EGP**")
                            if abs(dsc_diff) < 0.01:
                                st.markdown("<span style='color:green; font-weight:bold;'>✅ Discounts Match</span>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"<span style='color:red; font-weight:bold;'>❌ Mismatch: {dsc_diff:+,.2f} EGP</span>", unsafe_allow_html=True)
                                
                        with s_col3:
                            st.markdown("##### Step 3: Payments & Receipts")
                            st.write(f"PowerCampus: **{pc_pmt:,.2f} EGP**")
                            st.write(f"Local A/R: **{loc_pmt:,.2f} EGP**")
                            if abs(pmt_diff) < 0.01:
                                st.markdown("<span style='color:green; font-weight:bold;'>✅ Payments Match</span>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"<span style='color:red; font-weight:bold;'>❌ Mismatch: {pmt_diff:+,.2f} EGP</span>", unsafe_allow_html=True)

                        # Highlight live payment gateway missing locally alert
                        if pmt_diff > 0:
                            st.markdown(f"""
                            <div style="background-color: #e3f2fd; color: #0d47a1; border-left: 6px solid #0d47a1; padding: 12px; border-radius: 8px; font-size: 14px; margin-top: 15px; margin-bottom: 15px;">
                                💡 <b>Live Transaction Detected</b>: A live payment of <b>{pmt_diff:,.2f} EGP</b> was processed via the PowerCampus live payment gateway, but is missing in the local database. You can safely import this payment using the selective tool below.
                            </div>
                            """, unsafe_allow_html=True)

                        st.markdown("<br>", unsafe_allow_html=True)
                        ext_txs = ext_students[sid]["transactions"]
                        df_etxs = pd.DataFrame(ext_txs)
                        if not df_etxs.empty:
                            df_etxs["date"] = df_etxs["date"].dt.strftime("%Y-%m-%d")
                            
                        with get_db() as db:
                            loc_txs = db.query(Transaction).filter_by(student_id=int(sid), term=selected_term, academic_year=int(selected_year)).all()
                            
                        df_ltxs = pd.DataFrame()
                        if loc_txs:
                            df_ltxs = pd.DataFrame([{
                                "type": t.transaction_type,
                                "debit": t.debit,
                                "credit": t.credit,
                                "desc": t.description,
                                "date": t.entry_date.strftime("%Y-%m-%d") if t.entry_date else ""
                            } for t in loc_txs])

                        # Build dynamic row styling functions for visual audits
                        def style_ext(row):
                            amt = abs(row["amount"])
                            matched = False
                            for t in loc_txs:
                                local_amt = t.debit if t.debit > 0 else t.credit
                                if abs(local_amt - amt) < 0.01:
                                    matched = True
                                    break
                            if matched:
                                return ["background-color: rgba(212, 239, 223, 0.45); color: #155724;"] * len(row) # Soft green
                            else:
                                return ["background-color: rgba(248, 215, 218, 0.45); color: #721c24; font-weight: bold; border-left: 4px solid #d32f2f;"] * len(row) # Soft crimson

                        def style_loc(row):
                            amt = row["debit"] if row["debit"] > 0 else row["credit"]
                            matched = False
                            for _, ext_row in df_etxs.iterrows():
                                ext_amt = abs(ext_row["amount"])
                                if abs(ext_amt - amt) < 0.01:
                                    matched = True
                                    break
                            if matched:
                                return ["background-color: rgba(212, 239, 223, 0.45); color: #155724;"] * len(row) # Soft green
                            else:
                                return ["background-color: rgba(248, 215, 218, 0.45); color: #721c24; font-weight: bold; border-left: 4px solid #d32f2f;"] * len(row) # Soft crimson

                        col_l, col_r = st.columns(2)
                        with col_l:
                            st.write("**PowerCampus Transactions (Filtered)**")
                            if not df_etxs.empty:
                                styled_etxs = df_etxs[["type", "amount", "code", "desc", "date"]].style.apply(style_ext, axis=1)
                                st.dataframe(styled_etxs, hide_index=True, use_container_width=True)
                            else:
                                st.caption("No transactions found on PowerCampus.")
                        
                        with col_r:
                            st.write("**Local A/R Transactions**")
                            if not df_ltxs.empty:
                                styled_ltxs = df_ltxs.style.apply(style_loc, axis=1)
                                st.dataframe(styled_ltxs, hide_index=True, use_container_width=True)
                            else:
                                st.caption("No transactions found locally.")

                            # Direct Audit remedies
                            st.markdown("##### 🛠️ Selective Audit Remedies")

                            # 🧪 "Before vs. After" Ledger Simulation Sandbox
                            sim_active = st.checkbox("🧪 Open 'Before vs. After' Ledger Simulation Sandbox", value=False, key=f"sim_check_{sid}")
                            if sim_active:
                                st.markdown("##### 🧪 Real-time Ledger Balance Projection Sandbox")
                                st.caption("Here is the simulated transition preview showing exactly what your Local A/R database ledgers will look like after executing the imports/adjustments.")
                                
                                # Compile simulation rows
                                sim_rows = [
                                    {
                                        "Financial Dimension": "📄 Tuition Charges (Debits)",
                                        "Current Local (EGP)": loc_chg,
                                        "Remedy Effect (EGP)": chg_diff if abs(chg_diff) >= 0.01 else 0.0,
                                        "Projected Local (After Commit)": loc_chg + (chg_diff if abs(chg_diff) >= 0.01 else 0.0),
                                        "PowerCampus Target": pc_chg,
                                        "Post-Commit Status": "✅ Will Match" if abs((loc_chg + chg_diff) - pc_chg) < 0.01 else "🟡 Residual variance"
                                    },
                                    {
                                        "Financial Dimension": "🎓 Scholarships (Credits)",
                                        "Current Local (EGP)": loc_dsc,
                                        "Remedy Effect (EGP)": dsc_diff if abs(dsc_diff) >= 0.01 else 0.0,
                                        "Projected Local (After Commit)": loc_dsc + (dsc_diff if abs(dsc_diff) >= 0.01 else 0.0),
                                        "PowerCampus Target": pc_dsc,
                                        "Post-Commit Status": "✅ Will Match" if abs((loc_dsc + dsc_diff) - pc_dsc) < 0.01 else "🟡 Residual variance"
                                    },
                                    {
                                        "Financial Dimension": "💳 Payments & Receipts (Credits)",
                                        "Current Local (EGP)": loc_pmt,
                                        "Remedy Effect (EGP)": pmt_diff if abs(pmt_diff) >= 0.01 else 0.0,
                                        "Projected Local (After Commit)": loc_pmt + (pmt_diff if abs(pmt_diff) >= 0.01 else 0.0),
                                        "PowerCampus Target": pc_pmt,
                                        "Post-Commit Status": "✅ Will Match" if abs((loc_pmt + pmt_diff) - pc_pmt) < 0.01 else "🟡 Residual variance"
                                    },
                                    {
                                        "Financial Dimension": "⚖️ Net Balance Outstanding",
                                        "Current Local (EGP)": loc_chg - loc_dsc - loc_pmt,
                                        "Remedy Effect (EGP)": chg_diff - dsc_diff - pmt_diff,
                                        "Projected Local (After Commit)": pc_chg - pc_dsc - pc_pmt,
                                        "PowerCampus Target": pc_chg - pc_dsc - pc_pmt,
                                        "Post-Commit Status": "✅ Will Balance"
                                    }
                                ]
                                
                                df_sim = pd.DataFrame(sim_rows)
                                st.dataframe(
                                    df_sim,
                                    use_container_width=True,
                                    hide_index=True,
                                    column_config={
                                        "Current Local (EGP)": st.column_config.NumberColumn(format="%,.2f"),
                                        "Remedy Effect (EGP)": st.column_config.NumberColumn(format="%+,.2f"),
                                        "Projected Local (After Commit)": st.column_config.NumberColumn(format="%,.2f"),
                                        "PowerCampus Target": st.column_config.NumberColumn(format="%,.2f"),
                                    }
                                )
                                st.markdown("<br>", unsafe_allow_html=True)
                            act_col1, act_col2 = st.columns(2)
                            
                            # Remedy 1: Import missing payment
                            if pmt_diff > 0:
                                if act_col1.button(f"📥 Import Missing Payment ({pmt_diff:,.2f} EGP)", key=f"imp_pmt_{sid}", use_container_width=True):
                                    with get_db() as db:
                                        student_exists = db.get(Student, int(sid))
                                        if not student_exists:
                                            st.toast("🛑 Cannot import: Register student profile first.", icon="❌")
                                        else:
                                            start = next_ref_block(db, 1)
                                            new_tx = Transaction(
                                                reference_no = f"PAY-{start:06d}",
                                                student_id = int(sid),
                                                transaction_type = "Payment",
                                                description = f"[RECON-GATEWAY] Imported live gateway receipt",
                                                debit = 0.0, credit = abs(pmt_diff),
                                                hours_change = 0,
                                                entry_date = datetime.date.today(),
                                                term = selected_term,
                                                academic_year = int(selected_year)
                                            )
                                            db.add(new_tx)
                                            write_audit(
                                                db, st.session_state["logged_in_user"],
                                                "RECON_IMPORT_PMT", f"student_id={sid}",
                                                f"Imported live gateway payment of {pmt_diff:,.2f} EGP"
                                            )
                                            db.commit()
                                            st.cache_data.clear()
                                            st.toast(f"✅ Safe-imported gateway payment of {pmt_diff:,.2f} EGP successfully!", icon="✅")
                                            st.balloons()
                                            st.rerun()
                                            
                            # Remedy 2: Import missing charge
                            if chg_diff > 0:
                                if act_col2.button(f"📥 Import Missing Invoice ({chg_diff:,.2f} EGP)", key=f"imp_chg_{sid}", use_container_width=True):
                                    with get_db() as db:
                                        student_exists = db.get(Student, int(sid))
                                        if not student_exists:
                                            st.toast("🛑 Cannot import: Register student profile first.", icon="❌")
                                        else:
                                            start = next_ref_block(db, 1)
                                            new_tx = Transaction(
                                                reference_no = f"INV-{start:06d}",
                                                student_id = int(sid),
                                                transaction_type = "Invoice",
                                                description = f"[RECON] Imported tuition charge invoice",
                                                debit = abs(chg_diff), credit = 0.0,
                                                hours_change = 0,
                                                entry_date = datetime.date.today(),
                                                term = selected_term,
                                                academic_year = int(selected_year)
                                            )
                                            db.add(new_tx)
                                            write_audit(
                                                db, st.session_state["logged_in_user"],
                                                "RECON_IMPORT_INV", f"student_id={sid}",
                                                f"Imported missing tuition invoice of {chg_diff:,.2f} EGP"
                                            )
                                            db.commit()
                                            st.cache_data.clear()
                                            st.toast(f"✅ Safe-imported tuition charge of {chg_diff:,.2f} EGP successfully!", icon="✅")
                                            st.balloons()
                                            st.rerun()

                            # Remedy 3: Import missing scholarship discount
                            if dsc_diff > 0:
                                if act_col1.button(f"📥 Import Missing Scholarship ({dsc_diff:,.2f} EGP)", key=f"imp_dsc_{sid}", use_container_width=True):
                                    with get_db() as db:
                                        student_exists = db.get(Student, int(sid))
                                        if not student_exists:
                                            st.toast("🛑 Cannot import: Register student profile first.", icon="❌")
                                        else:
                                            start = next_ref_block(db, 1)
                                            new_tx = Transaction(
                                                reference_no = f"SCH-{start:06d}",
                                                student_id = int(sid),
                                                transaction_type = "Discount",
                                                description = f"[RECON] Imported scholarship discount",
                                                debit = 0.0, credit = abs(dsc_diff),
                                                hours_change = 0,
                                                entry_date = datetime.date.today(),
                                                term = selected_term,
                                                academic_year = int(selected_year)
                                            )
                                            db.add(new_tx)
                                            write_audit(
                                                db, st.session_state["logged_in_user"],
                                                "RECON_IMPORT_SCH", f"student_id={sid}",
                                                f"Imported missing scholarship discount of {dsc_diff:,.2f} EGP"
                                            )
                                            db.commit()
                                            st.cache_data.clear()
                                            st.toast(f"✅ Safe-imported scholarship discount of {dsc_diff:,.2f} EGP successfully!", icon="✅")
                                            st.balloons()
                                            st.rerun()

                            # Remedy 4: Compensating adjustment
                            adj_amt = abs(diff_val)
                            adj_type = "Debit" if diff_val > 0 else "Credit"
                            if act_col2.button(f"⚖️ Post Custom Reconciling {adj_type} ({adj_amt:,.2f} EGP)", key=f"post_adj_{sid}", use_container_width=True):
                                with get_db() as db:
                                    student_exists = db.get(Student, int(sid))
                                    if not student_exists:
                                        st.toast("🛑 Register student profile first.", icon="❌")
                                    else:
                                        start = next_ref_block(db, 1)
                                        dr = adj_amt if diff_val > 0 else 0.0
                                        cr = 0.0 if diff_val > 0 else adj_amt
                                        new_tx = Transaction(
                                            reference_no = f"RECON-{start:06d}",
                                            student_id = int(sid),
                                            transaction_type = "Adjustment",
                                            description = f"Recon Custom balancing adjustment",
                                            debit = dr, credit = cr,
                                            hours_change = 0,
                                            entry_date = datetime.date.today(),
                                            term = selected_term,
                                            academic_year = int(selected_year)
                                        )
                                        db.add(new_tx)
                                        write_audit(
                                            db, st.session_state["logged_in_user"],
                                            "RECON_ADJUST", f"student_id={sid}",
                                            f"Posted custom reconciling {adj_type} of {adj_amt:,.2f} EGP"
                                        )
                                        db.commit()
                                        st.cache_data.clear()
                                        st.toast(f"⚖️ Compensating adjustment of {adj_amt:,.2f} EGP posted successfully!", icon="✅")
                                        st.balloons()
                                        st.rerun()
                else:
                    st.toast("🎉 All common students have matching ledger balances! There are no mismatches.", icon="✅")

            # ── TAB 2: MISSING LOCALLY ──
            with res_tab2:
                if missing_local_list:
                    st.warning("⚠️ The following students/transactions exist in PowerCampus but are completely missing in our Local A/R database:")
                    
                    df_miss_loc = pd.DataFrame(missing_local_list)
                    st.dataframe(df_miss_loc, use_container_width=True, hide_index=True)

                    st.markdown("#### ⚡ Quick-Resolve Student Inspector")
                    missing_options = ["— Select Student —"] + [f"{r['Student ID']} — {r['Name']} (PC Bal: {r['PowerCampus Balance']:,.2f} EGP)" for r in missing_local_list]
                    selected_missing = st.selectbox(
                        "🔍 Select a Missing Student to Register / Import:",
                        options=missing_options,
                        key="reconciliation_missing_import_select"
                    )

                    if selected_missing != "— Select Student —":
                        selected_sid = selected_missing.split(" — ")[0]
                        row = next(r for r in missing_local_list if r["Student ID"] == selected_sid)
                        sid = row["Student ID"]
                        name = row["Name"]
                        pc_bal = row["PowerCampus Balance"]
                        
                        col_lbl, col_btn1, col_btn2 = st.columns([4, 2, 2])
                        col_lbl.write(f"📂 **{sid}** — {name} (PC Balance: **{pc_bal:,.2f} EGP**)")
                        
                        # 1. Register student action
                        btn_reg_key = f"reg_stu_{sid}"
                        with get_db() as db:
                            local_stu = db.get(Student, int(sid))
                        
                        if not local_stu:
                            if col_btn1.button("➕ Register Profile", key=btn_reg_key, use_container_width=True):
                                with get_db() as db:
                                    new_student = Student(
                                        id = int(sid),
                                        name = name,
                                        college = "Engineering" if "eng" in name.lower() or "eng" in str(ext_students[sid]["transactions"][0]["desc"]).lower() else "Business",
                                        price_per_hr = 4000.0,
                                        is_sponsored = False
                                    )
                                    db.add(new_student)
                                    write_audit(
                                        db, st.session_state["logged_in_user"],
                                        "RECON_ADD_STUDENT", f"student_id={sid}",
                                        f"Auto-registered student profile from PowerCampus reconciliation"
                                    )
                                    db.commit()
                                    st.cache_data.clear()
                                    st.toast(f"👤 Registered student {name} ({sid}) successfully!", icon="✅")
                                    st.rerun()
                        else:
                            col_btn1.write("✅ Profile Registered")

                        # 2. Auto-import transactions action
                        btn_imp_key = f"imp_txs_{sid}"
                        if col_btn2.button("⚡ Import Invoices", key=btn_imp_key, use_container_width=True):
                            with get_db() as db:
                                local_stu = db.get(Student, int(sid))
                                if not local_stu:
                                    st.toast("🛑 Please register the student profile first!", icon="❌")
                                else:
                                    ext_txs = ext_students[sid]["transactions"]
                                    imported_count = 0
                                    
                                    for t in ext_txs:
                                        start = next_ref_block(db, 1)
                                        tx_type = "Invoice" if t["type"] == 'C' else ("Discount" if t["type"] == 'D' else "Payment")
                                        dr = t["amount"] if t["type"] == 'C' else 0.0
                                        cr = t["amount"] if t["type"] in ['D', 'R'] else 0.0
                                        pfx = "INV" if t["type"] == 'C' else ("SCH" if t["type"] == 'D' else "PAY")
                                        ent_date = t["date"].date() if isinstance(t["date"], pd.Timestamp) else datetime.date.today()
                                        
                                        new_tx = Transaction(
                                            reference_no = f"{pfx}-{start:06d}",
                                            student_id = int(sid),
                                            transaction_type = tx_type,
                                            description = f"[RECON-PC] {t['desc'] or t['code']}",
                                            debit = dr, credit = cr,
                                            hours_change = 0,
                                            entry_date = ent_date,
                                            term = selected_term,
                                            academic_year = int(selected_year)
                                        )
                                        db.add(new_tx)
                                        imported_count += 1

                                    write_audit(
                                        db, st.session_state["logged_in_user"],
                                        "RECON_IMPORT_TXS", f"student_id={sid}",
                                        f"Imported {imported_count} transaction lines from PowerCampus"
                                    )
                                    db.commit()
                                    st.cache_data.clear()
                                    st.toast(f"✅ Imported {imported_count} transactions to {name}'s profile!", icon="✅")
                                    st.rerun()
                else:
                    st.toast("🎉 No missing student records identified in your local database!", icon="✅")

            # ── TAB 3: MATCHED RECORDS ──
            with res_tab3:
                if matched_list:
                    df_matched = pd.DataFrame(matched_list)
                    st.dataframe(df_matched[[
                        "Student ID", "Name", "PowerCampus Balance", "Local Balance", "Discrepancy (EGP)"
                    ]], use_container_width=True, hide_index=True)
                else:
                    st.caption("No perfectly matched records in this run.")

            # ── 9. Export Premium Multi-Sheet Reconciliation Excel Workbook ──
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Construct workbook dataframes
            export_data = []
            if mismatch_list:
                export_data.extend(mismatch_list)
            if missing_local_list:
                for item in missing_local_list:
                    export_data.append({
                        **item, "Local Balance": 0.0, "Discrepancy (EGP)": item["PowerCampus Balance"], "Status": "Missing Locally"
                    })
            
            if matched_list or mismatch_list or missing_local_list or missing_ext_list:
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    # Sheet 1: Summary Dashboard
                    summary_data = [
                        {"Key Indicator": "Academic Term", "Value": selected_term},
                        {"Key Indicator": "Academic Year", "Value": str(selected_year)},
                        {"Key Indicator": "Reconciliation Date", "Value": datetime.date.today().strftime("%Y-%m-%d")},
                        {"Key Indicator": "Reconciled By", "Value": st.session_state.get("logged_in_user", "System")},
                        {"Key Indicator": "-------------------------", "Value": "-------------------------"},
                        {"Key Indicator": "🟢 perfectly Matched Students", "Value": len(matched_list)},
                        {"Key Indicator": "🟡 Mismatched Balances", "Value": len(mismatch_list)},
                        {"Key Indicator": "🔴 Students Missing Locally", "Value": len(missing_local_list)},
                        {"Key Indicator": "🔵 Students Missing in PowerCampus", "Value": len(missing_ext_list)},
                    ]
                    pd.DataFrame(summary_data).to_excel(writer, sheet_name='📊 Summary Dashboard', index=False)
                    
                    # Sheet 2: Mismatched Balances
                    if mismatch_list:
                        pd.DataFrame(mismatch_list).to_excel(writer, sheet_name='🟡 Mismatched Balances', index=False)
                    else:
                        pd.DataFrame([{"Message": "No mismatched records in this run."}]).to_excel(writer, sheet_name='🟡 Mismatched Balances', index=False)
                    
                    # Sheet 3: Missing Locally
                    if missing_local_list:
                        pd.DataFrame(missing_local_list).to_excel(writer, sheet_name='🔴 Missing in Local DB', index=False)
                    else:
                        pd.DataFrame([{"Message": "No missing local records."}]).to_excel(writer, sheet_name='🔴 Missing in Local DB', index=False)
                        
                    # Sheet 4: Missing in PowerCampus
                    if missing_ext_list:
                        pd.DataFrame(missing_ext_list).to_excel(writer, sheet_name='🔵 Missing in PowerCampus', index=False)
                    else:
                        pd.DataFrame([{"Message": "No missing external records."}]).to_excel(writer, sheet_name='🔵 Missing in PowerCampus', index=False)
                    
                    # Sheet 5: Matched Ledger
                    if matched_list:
                        pd.DataFrame(matched_list).to_excel(writer, sheet_name='🟢 Matched Ledger', index=False)
                    else:
                        pd.DataFrame([{"Message": "No perfectly matched accounts."}]).to_excel(writer, sheet_name='🟢 Matched Ledger', index=False)

                st.download_button(
                    label="📥 Download Premium Reconciliation Excel Workbook (.xlsx)",
                    data=excel_buffer.getvalue(),
                    file_name=f"Comprehensive_Reconciliation_Report_{selected_term}_{selected_year}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )
