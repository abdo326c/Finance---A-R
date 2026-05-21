# app.py
# ─────────────────────────────────────────────
# Entry point: page config, CSS, sidebar,
# and routing to page modules.
# ─────────────────────────────────────────────
import streamlit as st

from config import VALID_TERMS, DEFAULT_YEAR
from models import seed_default_users, get_static_lookups, get_db, engine
from auth import init_session, check_timeout, login_form, logout

# ── Must be first Streamlit call ──────────────
st.set_page_config(
    page_title="Finance A/R System",
    layout="wide",
    page_icon="🏦",
    initial_sidebar_state="expanded",
)

# ── Seed DB on first run ───────────────────────
seed_default_users()

# ── Custom CSS ────────────────────────────────
# ── Custom CSS ────────────────────────────────
st.markdown(
    """
<style>
#MainMenu, footer, .stDeployButton { display: none !important; }
header[data-testid="stHeader"] { background: transparent !important; }
.block-container { padding-top: 2rem !important; padding-bottom: 1rem !important; }

/* إخفاء قائمة ستريمليت الافتراضية لمنع التعارض مع فولدر pages */
[data-testid="stSidebarNav"] { display: none !important; }

/* تنسيق القائمة المخصصة */
[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child { display: none !important; }
[data-testid="stSidebar"] div[role="radiogroup"] > label {
    padding: 8px 12px; border-radius: 8px; margin-bottom: 4px;
    background-color: transparent; transition: all 0.2s ease; cursor: pointer; font-weight: 500;
}
[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
    background-color: #f0f2f6; transform: translateX(4px);
}

/* 🟢 التعديل هنا: تلوين الصفحة النشطة (Active Page) */
[data-testid="stSidebar"] div[role="radiogroup"] > label[data-baseweb="radio"] input:checked + div {
    background-color: #eaf1fa !important; color: #004a99 !important; font-weight: 700 !important; 
    border-left: 4px solid #004a99 !important; border-radius: 0px 8px 8px 0px !important; 
    padding: 8px 10px !important; width: 100% !important; 
}

[data-testid="stMetricValue"] { font-size: 32px !important; color: #004a99 !important; }
[data-testid="stMetric"] {
    background-color: #ffffff; padding: 25px; border-radius: 15px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05); border-left: 6px solid #004a99;
}
.stButton > button { border-radius: 8px; border: none; transition: all 0.3s; }
.stButton > button:hover { transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
</style>
""",
    unsafe_allow_html=True,
)

# ── Session init + auth guard ─────────────────
init_session()

if not st.session_state["authenticated"]:
    login_form()
    st.stop()

if not check_timeout():
    st.stop()

# ── Flash toast ───────────────────────────────
if st.session_state.get("flash_msg"):
    st.toast(st.session_state.pop("flash_msg"), icon="✅")

# ── Header ────────────────────────────────────
st.markdown(
    "<h3 style='text-align:center;color:#1f2937;margin-bottom:-30px;'>"
    "🏦 Nile University - Finance A/R System</h3>",
    unsafe_allow_html=True,
)
st.markdown("---")

# ── Sidebar ───────────────────────────────────
NAV_OPTIONS = [
    "📊 Dashboard",
    "📜 Student Statement",
    "📈 Reports",
    "📚 Policies & Docs",
    "🔍 Student Lookup",
    "📊 Operations",
    "📤 Bulk Financials",
    "🎓 Scholarships",
    "🔄 D365 FTI Export",  # <--- السطر الجديد اللي ضفناه
    "👤 Registration",
    "🗑️ Batch Management",
    "⚙️ System Admin",
]

with st.sidebar:
    selected_tab = st.radio("Navigation", NAV_OPTIONS, label_visibility="collapsed")
    st.markdown("---")
    st.caption(f"👤 Logged in as: **{st.session_state.get('logged_in_user', '?')}**")
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚪 Log out", use_container_width=True):
        logout()
        st.rerun()

# ── Cached lookups (shared across pages) ──────
try:
    sch_map, all_colleges, available_years = get_static_lookups()
except Exception:
    sch_map, all_colleges, available_years = {}, [], [DEFAULT_YEAR]

# Expose to pages via session state (avoids re-import of heavy cache)
st.session_state["_sch_map"]   = sch_map
st.session_state["_avail_yrs"] = available_years

# ── Page routing ──────────────────────────────
if selected_tab == "📊 Dashboard":
    from pages.dashboard import render
    render(engine, available_years)

elif selected_tab == "📜 Student Statement":
    from pages.statement import render
    render(engine, available_years)

elif selected_tab == "📈 Reports":
    from pages.reports import render
    render(engine, available_years)

elif selected_tab == "📚 Policies & Docs":
    from pages.policies import render
    render()

elif selected_tab == "🔍 Student Lookup":
    from pages.lookup import render
    render()

elif selected_tab == "📊 Operations":
    from pages.operations import render
    render()

elif selected_tab == "📤 Bulk Financials":
    from pages.bulk import render
    render(engine)

elif selected_tab == "🎓 Scholarships":
    from pages.scholarships import render
    render(engine)
    
 # ── السطور الجديدة اللي هتضيفها ──
elif selected_tab == "🔄 D365 FTI Export":
    from pages.d365_export import render
    render(engine, available_years)
# ─────────────────────────────────   

elif selected_tab == "👤 Registration":
    from pages.registration import render
    render(engine)

elif selected_tab == "🗑️ Batch Management":
    from pages.batches import render
    render(engine)

elif selected_tab == "⚙️ System Admin":
    from pages.admin import render
    render()
