# views/reconciliation.py
import io
import datetime
import pandas as pd
import streamlit as st
from sqlalchemy import text
from models import (
    get_db, Student, Transaction, write_audit, next_ref_block
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

        st.success(f"📂 Loaded external file: `{uploaded_file.name}` containing **{len(df_ext)}** records.")

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

        # ── 5. Run Compare Core Engine ──
        with st.spinner("Analyzing ledger discrepancies..."):
            # Ensure proper types
            df_ext[id_col] = df_ext[id_col].astype(str).str.replace(".0", "", regex=False).str.strip()
            df_ext[amount_col] = pd.to_numeric(df_ext[amount_col], errors='coerce').fillna(0.0)
            df_ext[date_col] = pd.to_datetime(df_ext[date_col], errors='coerce')
            
            # Map selected term to PowerCampus standard term string
            target_pc_term = map_term_name(selected_term)

            # Filter external records matching target business logic
            # Charges (C) and Discounts (D) matching selected Term & Year
            charges_discounts_mask = (
                (df_ext[type_col].astype(str).str.upper().str.strip().isin(['C', 'D'])) &
                (df_ext[term_col].astype(str).apply(map_term_name) == target_pc_term) &
                (df_ext[year_col].astype(str).str.contains(str(selected_year), na=False))
            )
            if enable_charge_date and charge_cutoff:
                charges_discounts_mask &= (df_ext[date_col].dt.date >= charge_cutoff)

            # Payments (R) strictly matching cut-off date picker
            payments_mask = (
                (df_ext[type_col].astype(str).str.upper().str.strip() == 'R') &
                (df_ext[date_col].dt.date >= pay_cutoff)
            )

            df_charges_discounts = df_ext[charges_discounts_mask]
            df_payments = df_ext[payments_mask]

            # Combine matches
            df_filtered = pd.concat([df_charges_discounts, df_payments], ignore_index=True)

            if df_filtered.empty:
                st.warning("⚠️ No records matched the selected Term, Year, and Date Filter criteria in the uploaded file.")
                return

            # Compute external totals per student
            ext_students = {}
            for _, row in df_filtered.iterrows():
                sid = row[id_col]
                tx_type = str(row[type_col]).upper().strip()
                amt = float(row[amount_col])
                
                # Retrieve names
                f_name = str(row.get(fname_col, "")) if fname_col in row else ""
                m_name = str(row.get(mname_col, "")) if mname_col in row else ""
                l_name = str(row.get(lname_col, "")) if lname_col in row else ""
                full_name = f"{f_name} {m_name} {l_name}".replace("  ", " ").strip()
                
                # Fetch code/descriptions for discrepancy audit views
                code_val = str(row[code_col]) if code_col in row else ""
                desc_val = str(row[desc_col]) if desc_col in row else ""
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
            met_col1, met_col2, met_col3, met_col4 = st.columns(4)
            met_col1.metric("🟢 Matched Accounts", len(matched_list))
            met_col2.metric("🟡 Mismatched Balances", len(mismatch_list))
            met_col3.metric("🔴 Missing in Local A/R", len(missing_local_list))
            met_col4.metric("🔵 Missing in PowerCampus", len(missing_ext_list))

            # ── 7. Detailed Visual Tab Panels ──
            st.markdown("---")
            st.markdown("### 🔍 Discrepancy Breakdown & Resolving Actions")
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

                    # Expandable detailed audit list with correction buttons
                    st.markdown("#### 🛠️ Direct Discrepancy Auditing & Adjustment Options")
                    
                    for row in mismatch_list:
                        sid = row["Student ID"]
                        diff_val = row["Discrepancy (EGP)"]
                        
                        with st.expander(f"⚠️ Audit Student **{sid}** — **{row['Name']}** (Discrepancy: {diff_val:+,.2f} EGP)"):
                            # Side by side ledgers
                            col_l, col_r = st.columns(2)
                            with col_l:
                                st.write("**PowerCampus Transactions (Filtered)**")
                                ext_txs = ext_students[sid]["transactions"]
                                df_etxs = pd.DataFrame(ext_txs)
                                df_etxs["date"] = df_etxs["date"].dt.strftime("%Y-%m-%d")
                                st.dataframe(df_etxs[["type", "amount", "code", "desc", "date"]], hide_index=True, use_container_width=True)
                            
                            with col_r:
                                st.write("**Local A/R Transactions**")
                                with get_db() as db:
                                    loc_txs = db.query(Transaction).filter_by(student_id=int(sid), term=selected_term, academic_year=int(selected_year)).all()
                                    if loc_txs:
                                        df_ltxs = pd.DataFrame([{
                                            "type": t.transaction_type,
                                            "debit": t.debit,
                                            "credit": t.credit,
                                            "desc": t.description,
                                            "date": t.entry_date.strftime("%Y-%m-%d") if t.entry_date else ""
                                        } for t in loc_txs])
                                        st.dataframe(df_ltxs, hide_index=True, use_container_width=True)
                                    else:
                                        st.caption("No transactions found locally.")

                            # Correction Buttons
                            action_c1, action_c2 = st.columns(2)
                            
                            # Correction Option: Post balancing adjustment locally
                            adj_type = "Adjustment Debit" if diff_val > 0 else "Adjustment Credit"
                            adj_amt = abs(diff_val)
                            
                            btn_label = f"⚖️ Post Balancing { 'Debit' if diff_val > 0 else 'Credit' } of {adj_amt:,.2f} EGP"
                            if action_c1.button(btn_label, key=f"post_adj_{sid}_{selected_term}"):
                                with get_db() as db:
                                    # Ensure student is active in DB
                                    student_exists = db.get(Student, int(sid))
                                    if not student_exists:
                                        st.toast("🛑 Cannot post adjustment: Student profile does not exist in local database. Register them first.", icon="❌")
                                    else:
                                        start = next_ref_block(db, 1)
                                        dr = adj_amt if diff_val > 0 else 0.0
                                        cr = 0.0 if diff_val > 0 else adj_amt
                                        
                                        new_tx = Transaction(
                                            reference_no = f"RECON-{start:06d}",
                                            student_id = int(sid),
                                            transaction_type = "Adjustment",
                                            description = f"Recon Correction: PowerCampus Balance Sync",
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
                                            f"Posted {adj_type} of {adj_amt:,.2f} EGP to reconcile with PowerCampus"
                                        )
                                        db.commit()
                                        st.toast(f"⚖️ Balancing adjustment of {adj_amt:,.2f} EGP posted successfully!", icon="✅")
                                        st.rerun()

                else:
                    st.success("🎉 All common students have matching ledger balances! There are no mismatches.")

            # ── TAB 2: MISSING LOCALLY ──
            with res_tab2:
                if missing_local_list:
                    st.warning("⚠️ The following students/transactions exist in PowerCampus but are completely missing in our Local A/R database:")
                    
                    df_miss_loc = pd.DataFrame(missing_local_list)
                    st.dataframe(df_miss_loc, use_container_width=True, hide_index=True)

                    st.markdown("#### ⚡ Quick-Resolve Auto Import Options")
                    for row in missing_local_list:
                        sid = row["Student ID"]
                        name = row["Name"]
                        pc_bal = row["PowerCampus Balance"]
                        
                        col_lbl, col_btn1, col_btn2 = st.columns([4, 2, 2])
                        col_lbl.write(f"**{sid}** — {name} (PC Balance: **{pc_bal:,.2f} EGP**)")
                        
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
                                        price_per_hr = 4000.0, # Default standard tuition rate
                                        is_sponsored = False
                                    )
                                    db.add(new_student)
                                    write_audit(
                                        db, st.session_state["logged_in_user"],
                                        "RECON_ADD_STUDENT", f"student_id={sid}",
                                        f"Auto-registered student profile from PowerCampus reconciliation"
                                    )
                                    db.commit()
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
                                        
                                        # Convert date securely
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
                                    st.toast(f"✅ Imported {imported_count} transactions to {name}'s profile!", icon="✅")
                                    st.rerun()
                else:
                    st.success("🎉 No missing student records identified in your local database!")

            # ── TAB 3: MATCHED RECORDS ──
            with res_tab3:
                if matched_list:
                    df_matched = pd.DataFrame(matched_list)
                    st.dataframe(df_matched[[
                        "Student ID", "Name", "PowerCampus Balance", "Local Balance", "Discrepancy (EGP)"
                    ]], use_container_width=True, hide_index=True)
                else:
                    st.caption("No perfectly matched records in this run.")

            # ── 8. Export Discrepancy report ──
            st.markdown("<br>", unsafe_allow_html=True)
            export_data = []
            if mismatch_list:
                export_data.extend(mismatch_list)
            if missing_local_list:
                for item in missing_local_list:
                    export_data.append({
                        **item, "Local Balance": 0.0, "Discrepancy (EGP)": item["PowerCampus Balance"], "Status": "Missing Locally"
                    })
            
            if export_data:
                df_export = pd.DataFrame(export_data)
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    df_export.to_excel(writer, index=False, sheet_name='Discrepancies')
                
                st.download_button(
                    label="📥 Download Discrepancies Excel Report",
                    data=excel_buffer.getvalue(),
                    file_name=f"Reconciliation_Report_{selected_term}_{selected_year}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="secondary",
                    use_container_width=True
                )

        st.balloons()
