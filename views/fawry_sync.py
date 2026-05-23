# views/fawry_sync.py
# ─────────────────────────────────────────────────────────────
# Fawry Payments Supabase to local SQLite Finance Bridge
# ─────────────────────────────────────────────────────────────
import streamlit as st
import requests
import datetime
from models import get_db, Student, Transaction, write_audit
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
    url = f"{SUPABASE_URL}/rest/v1/transactions?id_status=eq.Valid"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Supabase connection error: HTTP {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Failed to connect to Supabase: {e}")
        return None

def render(engine, available_years):
    st.subheader("🔌 Fawry Payments Synchronization Bridge")
    st.markdown("Bridge payment transactions processed in `fawry-query-app` directly into local student finance accounts.")
    require_role("Admin", "Editor")

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
        # Get all local transactions with FAWRY- prefix
        local_fawry_refs = {
            tx.reference_no.replace("FAWRY-", ""): tx 
            for tx in db.query(Transaction).filter(Transaction.reference_no.like("FAWRY-%")).all()
        }

        # Check local student IDs
        local_students = {s.id: s for s in db.query(Student).all()}

        for stx in supabase_txs:
            ref = str(stx.get("reference_number"))
            
            # Skip if already synced
            if ref in local_fawry_refs:
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
    unique_items = sorted(list(set(t.get("item_name") for t in unsynced_txs if t.get("item_name"))))
    unique_banks = sorted(list(set(t.get("bank") for t in unsynced_txs if t.get("bank"))))
    
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    with col_f1:
        filter_dates = st.multiselect("Date of Payment", unique_dates, default=[])
    with col_f2:
        filter_mapping = st.selectbox("Mapping Status", ["All", "Mapped (Found)", "Unmapped (Not Found)"])
    with col_f3:
        filter_items = st.multiselect("Item Name", unique_items, default=[])
    with col_f4:
        filter_banks = st.multiselect("Bank", unique_banks, default=[])
        
    filtered_txs = []
    for tx in unsynced_txs:
        if filter_dates and tx.get("payment_date") not in filter_dates:
            continue
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
        st.metric("Pending Transactions", f"{len(filtered_txs)} payments")
    with c2:
        total_vol = sum(t["item_price"] for t in filtered_txs)
        st.metric("Total Outstanding Volume", f"{total_vol:,.2f} EGP")

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
    included_refs = edited_df[edited_df["Include"] == True]["Fawry Ref"].tolist() if not edited_df.empty else []

    # ── 4. Synchronization & Export Actions ──
    st.markdown("<br>", unsafe_allow_html=True)
    c_btn1, c_btn2 = st.columns([1, 1])

    with c_btn1:
        if st.button("📥 Synchronize Selected Valid Payments", type="primary", use_container_width=True):
            valid_to_sync = [t for t in filtered_txs if t["student_found"] and t["reference_number"] in included_refs]
            if not valid_to_sync:
                st.error("🛑 No selected pending transactions have valid registered students in local ERP.")
                return
    
    with c_btn2:
        csv_data = edited_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📊 Export to CSV",
            data=csv_data,
            file_name=f"fawry_payments_export_{datetime.date.today()}.csv",
            mime="text/csv",
            use_container_width=True
        )

            sync_count = 0
            with get_db() as db_session:
                try:
                    for tx in valid_to_sync:
                        # Convert date string to python date object
                        p_date = datetime.date.today()
                        if tx["payment_date"]:
                            try:
                                p_date = datetime.datetime.strptime(tx["payment_date"], "%Y-%m-%d").date()
                            except Exception:
                                pass

                        new_tx = Transaction(
                            reference_no = f"FAWRY-{tx['reference_number']}",
                            student_id = tx["student_id_int"],
                            transaction_type = "Payment",
                            description = f"Fawry Sync via {tx['bank']} for {tx['item_name']}",
                            internal_note = f"Supabase sync | Fawry Fees: {tx['fawry_fees']} EGP | Net Amount: {tx['net_amount']} EGP",
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
                            f"Synced Fawry Ref={tx['reference_number']} | cr={tx['item_price']}"
                        )
                        sync_count += 1
                        st.toast(f"✅ Synced Ref {tx['reference_number']} for {tx['student_name']}", icon="✅")

                    db_session.commit()
                    st.session_state["flash_msg"] = f"Successfully synchronized {sync_count} Fawry payments into Student Accounts!"
                    st.rerun()

                except Exception as ex:
                    db_session.rollback()
                    st.error(f"Reconciliation sync failed: {ex}")
