# views/fawry_sync.py
# ─────────────────────────────────────────────────────────────
# Fawry Payments Supabase to local SQLite Finance Bridge
# ─────────────────────────────────────────────────────────────
import streamlit as st
import requests
import datetime
from models import get_db, Student, Transaction, write_audit, next_ref_block
from auth import require_role
from config import VALID_TERMS

SUPABASE_URL = "https://hjtxdyuevxcezxzbiiqk.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhqdHhkeXVldnhjZXp4emJpaXFrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk1MjU5MDEsImV4cCI6MjA5NTEwMTkwMX0.ZiKUw1db5pDRYto-hLGut3rdrzxVfRN36ouX4AjB5AQ"

def fetch_supabase_transactions():
    """Retrieve validated transaction entries directly from Supabase REST endpoint"""
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
                
                # If we received fewer records than the limit, we've reached the end
                if len(data) < limit:
                    break
                
                offset += limit
            else:
                st.error(f"Supabase connection error: HTTP {response.status_code}")
                return None
                
        return all_transactions
    except Exception as e:
        st.error(f"Failed to connect to Supabase: {e}")
        return None

def render(engine, available_years):
    st.subheader("🔌 Fawry Payments Synchronization Bridge")
    st.markdown("Bridge payment transactions processed in `fawry-query-app` directly into local student finance accounts.")
    require_role("Admin", "Editor")

    if "fawry_sync_summary" in st.session_state:
        summary = st.session_state.pop("fawry_sync_summary")
        st.markdown("### 📊 Last Import Summary")
        s_c1, s_c2, s_c3 = st.columns(3)
        with s_c1:
            st.markdown(f'''
                <div style="padding:15px; border-radius:8px; background-color:#d4edda; border-left:5px solid #28a745; margin-bottom:15px;">
                    <div style="font-size: 13px; color: #155724; font-weight: 600;">Successfully Uploaded</div>
                    <div style="font-size: 20px; font-weight: bold; color: #155724;">{summary["uploaded_count"]} <span style="font-size:14px;font-weight:normal;">payments</span></div>
                </div>
            ''', unsafe_allow_html=True)
        with s_c2:
            st.markdown(f'''
                <div style="padding:15px; border-radius:8px; background-color:#d4edda; border-left:5px solid #28a745; margin-bottom:15px;">
                    <div style="font-size: 13px; color: #155724; font-weight: 600;">Total Amount Uploaded</div>
                    <div style="font-size: 20px; font-weight: bold; color: #155724;">{summary["uploaded_amount"]:,.2f} <span style="font-size:14px;font-weight:normal;">EGP</span></div>
                </div>
            ''', unsafe_allow_html=True)
        with s_c3:
            bg_color = "#f8d7da" if summary["failed_count"] > 0 else "#e2e3e5"
            text_color = "#721c24" if summary["failed_count"] > 0 else "#383d41"
            border_color = "#dc3545" if summary["failed_count"] > 0 else "#6c757d"
            st.markdown(f'''
                <div style="padding:15px; border-radius:8px; background-color:{bg_color}; border-left:5px solid {border_color}; margin-bottom:15px;">
                    <div style="font-size: 13px; color: {text_color}; font-weight: 600;">Failed Payments</div>
                    <div style="font-size: 20px; font-weight: bold; color: {text_color};">{summary["failed_count"]} <span style="font-size:14px;font-weight:normal;">payments</span></div>
                </div>
            ''', unsafe_allow_html=True)
        if summary.get("failed_details"):
            with st.expander("View Failed Payments Details", expanded=True):
                for detail in summary["failed_details"]:
                    st.error(detail)
        st.markdown("---")

    # ── 1. Connection Status Card ──
    st.markdown("### 🌐 Supabase Integration Status")
    
    is_connected = False
    supabase_txs = None
    with st.spinner("Establishing secure handshake with Supabase..."):
        supabase_txs = fetch_supabase_transactions()
        if supabase_txs is not None:
            is_connected = True

    if is_connected:
        st.markdown(
            f"""
            <div style="background-color: rgba(212, 239, 223, 0.15); border-left: 6px solid #27c93f; padding: 15px; border-radius: 8px; margin-bottom: 20px; font-family: 'Inter', sans-serif;">
                <span style="color: #27c93f; font-weight: bold; font-size: 16px;">🟢 Connection Established Successfully</span><br/>
                <span style="font-size: 13.5px; opacity: 0.95;">
                    <b>Endpoint URL:</b> {SUPABASE_URL}<br/>
                    <b>Remote Table Name:</b> transactions<br/>
                    <b>Active Records:</b> {len(supabase_txs)} validated payment logs fetched from Supabase.
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"""
            <div style="background-color: rgba(248, 215, 218, 0.15); border-left: 6px solid #ff5f56; padding: 15px; border-radius: 8px; margin-bottom: 20px; font-family: 'Inter', sans-serif;">
                <span style="color: #ff5f56; font-weight: bold; font-size: 16px;">🔴 Connection Failed</span><br/>
                <span style="font-size: 13.5px; opacity: 0.95;">
                    Unable to contact Supabase database at {SUPABASE_URL}. Check your server internet connection or API availability.
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )
        return

    # ── 2. Sync Configuration ──
    st.markdown("### ⚙️ Sync Posting Defaults")
    col_t, col_y, col_info = st.columns([1, 1, 2])
    
    with col_t:
        sync_term = st.selectbox("Target Posting Term:", VALID_TERMS, index=0)
    with col_y:
        sync_year = st.selectbox("Target Posting Year:", available_years, index=0)
    with col_info:
        st.info("💡 Synced transactions will be registered under this Term and Year in student accounts.")

    # ── 3. Cross-reference Sync Report ──
    if not supabase_txs:
        st.warning("⚠️ No validated payment records found in Supabase.")
        return

    st.markdown("### 📋 Reconciliation Sync Table")

    # Filter out already synced payments in local SQLite db
    unsynced_txs = []
    
    with get_db() as db:
        # Get all local transactions with FAWRY- logic
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

        # Check local student IDs
        local_students = {s.id: s for s in db.query(Student).all()}

        for stx in supabase_txs:
            ref = str(stx.get("reference_number"))
            item_name = stx.get("item_name", "TUI")
            
            expected_ref = f"FAWRY-{ref}-{item_name}"
            legacy_ref = f"FAWRY-{ref}"
            
            # Skip if already synced
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
                "item_name": stx.get("item_name", "TUI"),
                "item_price": float(stx.get("item_price", 0.0)),
                "bank": stx.get("bank", "NUADCB136"),
                "fawry_fees": float(stx.get("fawry_fees", 0.0)),
                "net_amount": float(stx.get("net_amount", 0.0))
            })

    if not unsynced_txs:
        st.success("✅ All payments from Supabase are fully synchronized with local student accounts!")
        return

    st.markdown("### 🔍 Filter Payments")
    
    unique_dates = sorted(list(set(t.get("payment_date") for t in unsynced_txs if t.get("payment_date"))))
    
    min_date = datetime.date.today()
    max_date = datetime.date.today()
    if unique_dates:
        try:
            min_date = datetime.datetime.strptime(unique_dates[0], "%Y-%m-%d").date()
            max_date = datetime.datetime.strptime(unique_dates[-1], "%Y-%m-%d").date()
        except Exception:
            pass
            
    st.info(f"💡 **Sync Recommendation:** Missing payments detected. The system recommends pulling from **{min_date.strftime('%Y-%m-%d')}** onwards.")

    unique_items = sorted(list(set(t.get("item_name") for t in unsynced_txs if t.get("item_name"))))
    unique_banks = sorted(list(set(t.get("bank") for t in unsynced_txs if t.get("bank"))))
    
    default_items = [i for i in unique_items if i.upper() in ["TUI", "SU", "LATE FEE", "LATE_FEE"]]
    
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    with col_f1:
        filter_date_range = st.date_input("Date Range", value=(min_date, max_date))
    with col_f2:
        filter_mapping = st.selectbox("Mapping Status", ["All", "Mapped (Found)", "Unmapped (Not Found)"])
    with col_f3:
        filter_items = st.multiselect("Item Name", unique_items, default=default_items)
    with col_f4:
        filter_banks = st.multiselect("Bank", unique_banks, default=[])
        
    filtered_txs = []
    
    range_start, range_end = None, None
    if isinstance(filter_date_range, tuple):
        if len(filter_date_range) == 2:
            range_start, range_end = filter_date_range
        elif len(filter_date_range) == 1:
            range_start = range_end = filter_date_range[0]
    elif filter_date_range:
        range_start = range_end = filter_date_range
        
    for tx in unsynced_txs:
        if range_start and range_end and tx.get("payment_date"):
            try:
                tx_date = datetime.datetime.strptime(tx["payment_date"], "%Y-%m-%d").date()
                if not (range_start <= tx_date <= range_end):
                    continue
            except Exception:
                pass
                
        if filter_mapping == "Mapped (Found)" and not tx["student_found"]:
            continue
        if filter_mapping == "Unmapped (Not Found)" and tx["student_found"]:
            continue
        if filter_items and tx.get("item_name") not in filter_items:
            continue
        if filter_banks and tx.get("bank") not in filter_banks:
            continue
        filtered_txs.append(tx)

    # Statistics Cards
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f'''
            <div style="padding:12px; border-radius:6px; background-color:rgba(31,119,180,0.1); border-left:4px solid #1f77b4; margin-bottom:15px;">
                <div style="font-size: 13px; color: #555; font-weight: 600;">Pending Transactions</div>
                <div style="font-size: 18px; font-weight: bold; color: #1f77b4;">{len(filtered_txs):,} <span style="font-size:14px;font-weight:normal;">payments</span></div>
            </div>
        ''', unsafe_allow_html=True)
    with c2:
        total_vol = sum(t["item_price"] for t in filtered_txs)
        st.markdown(f'''
            <div style="padding:12px; border-radius:6px; background-color:rgba(39,201,63,0.1); border-left:4px solid #27c93f; margin-bottom:15px;">
                <div style="font-size: 13px; color: #555; font-weight: 600;">Total Outstanding Volume</div>
                <div style="font-size: 18px; font-weight: bold; color: #27c93f;">{total_vol:,.2f} <span style="font-size:14px;font-weight:normal;">EGP</span></div>
            </div>
        ''', unsafe_allow_html=True)

    # Render Styled Table
    display_rows = []
    for tx in filtered_txs:
        status_text = f"✅ {tx['student_name']}" if tx["student_found"] else "❌ Student Not Found"
        display_rows.append({
            "Include": True,
            "Fawry Ref": tx["reference_number"],
            "Payment Date": tx["payment_date"],
            "Student ID": tx["student_id"],
            "ERP Status": status_text,
            "Item": tx["item_name"],
            "Bank": tx["bank"],
            "Amount (EGP)": f"{tx['item_price']:,.2f}"
        })

    import pandas as pd
    df_display = pd.DataFrame(display_rows)
    
    edited_df = st.data_editor(
        df_display, 
        use_container_width=True,
        hide_index=True,
        column_config={
            "Include": st.column_config.CheckboxColumn(
                "Include in Sync",
                help="Uncheck to exclude this payment from being synchronized.",
                default=True,
            )
        },
        disabled=["Fawry Ref", "Payment Date", "Student ID", "ERP Status", "Item", "Bank", "Amount (EGP)"]
    )
    
    # Filter for checked rows
    included_refs = [str(x) for x in edited_df[edited_df["Include"] == True]["Fawry Ref"].tolist()] if not edited_df.empty else []

    # ── 4. Synchronization & Export Actions ──
    st.markdown("<br>", unsafe_allow_html=True)
    c_btn1, c_btn2 = st.columns([1, 1])

    with c_btn2:
        csv_data = edited_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📊 Export to CSV",
            data=csv_data,
            file_name=f"fawry_payments_export_{datetime.date.today()}.csv",
            mime="text/csv",
            use_container_width=True
        )

    with c_btn1:
        if st.button("📥 Synchronize Selected Valid Payments", type="primary", use_container_width=True):
            valid_to_sync = [t for t in filtered_txs if t["student_found"] and t["reference_number"] in included_refs]
            if not valid_to_sync:
                st.error("🛑 No selected pending transactions have valid registered students in local ERP.")
                return

            sync_count = 0
            sync_amount = 0.0
            failed_count = 0
            failed_amount = 0.0
            failed_details = []

            batch_id = f"FAWRY-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"

            with get_db() as db_session:
                try:
                    start_ref_num = next_ref_block(db_session, len(valid_to_sync))
                    current_ref_idx = start_ref_num

                    for tx in valid_to_sync:
                        try:
                            # Use nested transaction (savepoint) so a single failure doesn't rollback the entire batch
                            with db_session.begin_nested():
                                p_date = datetime.date.today()
                                if tx["payment_date"]:
                                    try:
                                        p_date = datetime.datetime.strptime(tx["payment_date"], "%Y-%m-%d").date()
                                    except Exception:
                                        pass
        
                                new_ref_no = f"PAY-{current_ref_idx:06d}"

                                new_tx = Transaction(
                                    reference_no = new_ref_no,
                                    batch_id = batch_id,
                                    student_id = tx["student_id_int"],
                                    transaction_type = "Bulk Payments",
                                    description = f"Bank: {tx['bank']} | Ref: {tx['reference_number']}",
                                    internal_note = f"FAWRY_SYNC:{tx['reference_number']}:{tx['item_name']} | Fawry Fees: {tx['fawry_fees']} EGP | Net Amount: {tx['net_amount']} EGP",
                                    debit = 0.0,
                                    credit = tx["item_price"],
                                    hours_change = 0.0,
                                    entry_date = p_date,
                                    term = sync_term,
                                    academic_year = int(sync_year)
                                )
                                db_session.add(new_tx)
                                
                                # Write audit entry
                                write_audit(
                                    db_session, 
                                    st.session_state["logged_in_user"],
                                    "FAWRY_SYNC", 
                                    f"student_id={tx['student_id_int']}",
                                    f"Synced Fawry Ref={tx['reference_number']} as {new_ref_no} | batch={batch_id}"
                                )
                            # If no exception, it was successful
                            sync_count += 1
                            sync_amount += tx["item_price"]
                            current_ref_idx += 1
                        except Exception as inner_ex:
                            failed_count += 1
                            failed_amount += tx["item_price"]
                            failed_details.append(f"Ref {tx['reference_number']} ({tx['item_name']}): {inner_ex}")

                    db_session.commit()
                    
                    st.session_state["fawry_sync_summary"] = {
                        "uploaded_count": sync_count,
                        "uploaded_amount": sync_amount,
                        "failed_count": failed_count,
                        "failed_amount": failed_amount,
                        "failed_details": failed_details
                    }
                    st.session_state["flash_msg"] = f"Sync complete! Processed {sync_count + failed_count} payments in batch {batch_id}."
                    st.rerun()

                except Exception as ex:
                    db_session.rollback()
                    st.error(f"Reconciliation sync failed entirely: {ex}")
