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

# 🟢 التعديل الأهم: قراءة الكوكيز وتحضير الجلسة قبل رسم أي حاجة على الشاشة
init_session()

# ── Seed DB on first run ───────────────────────
seed_default_users()

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

/* تلوين الصفحة النشطة (Active Page) */
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

/* Glass-card styling */
.glass-card {
    background: rgba(255, 255, 255, 0.8) !important;
    backdrop-filter: blur(12px) !important;
    border: 1px solid rgba(0, 0, 0, 0.08) !important;
    border-radius: 12px !important;
    padding: 16px !important;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03) !important;
}

/* Skeleton Loaders */
.skeleton {
    animation: skeleton-loading 1s linear infinite alternate;
    border-radius: 4px;
}
@keyframes skeleton-loading {
    0% { background-color: hsl(200, 20%, 80%); }
    100% { background-color: hsl(200, 20%, 95%); }
}

/* Sticky Headers for Tables */
[data-testid="stDataFrame"] th {
    position: sticky !important;
    top: 0 !important;
    z-index: 10 !important;
    background-color: #f8f9fa !important;
}

/* Glassmorphic Slide-in Toasts */
div[data-testid="stToast"] {
    background: rgba(13, 71, 161, 0.9) !important;
    backdrop-filter: blur(12px) !important;
    border-left: 6px solid #00897b !important;
    border-radius: 8px !important;
    color: #ffffff !important;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2) !important;
    font-weight: 500 !important;
    transition: all 0.3s ease !important;
}
div[data-testid="stToast"] h2 { color: #ffffff !important; }
div[data-testid="stToast"] button { color: #ffffff !important; }
</style>
""",
    unsafe_allow_html=True,
)

# ── Auth guard ────────────────────────────────
if not st.session_state.get("authenticated"):
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

NAV_OPTIONS = [
    "📊 Dashboard",
    "📜 Student Statement",
    "📈 Reports",
    "📚 Policies & Docs",
    "🔍 Student Lookup",
    "📊 Operations",
    "📤 Bulk Financials",
    "🎓 Scholarships",
    "🔄 D365 FTI Export",
    "🔄 Reconciliation",
    "📩 Email Follow-up",
    "👤 Registration",
    "🗑️ Batch Management",
    "⚙️ System Admin",
]

with st.sidebar:
    selected_tab = st.radio(
        "Navigation", 
        NAV_OPTIONS, 
        label_visibility="collapsed"
    )

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

st.session_state["_sch_map"]   = sch_map
st.session_state["_avail_yrs"] = available_years

# ── Page routing ──────────────────────────────
if selected_tab == "📊 Dashboard":
    from views.dashboard import render
    render(engine, available_years)

elif selected_tab == "📜 Student Statement":
    from views.statement import render
    render(engine, available_years)

elif selected_tab == "📈 Reports":
    from views.reports import render
    render(engine, available_years)

elif selected_tab == "📚 Policies & Docs":
    from views.policies import render
    render()

elif selected_tab == "🔍 Student Lookup":
    from views.lookup import render
    render()

elif selected_tab == "📊 Operations":
    from views.operations import render
    render()

elif selected_tab == "📤 Bulk Financials":
    from views.bulk import render
    render(engine)

elif selected_tab == "🎓 Scholarships":
    from views.scholarships import render
    render(engine)
    
elif selected_tab == "🔄 D365 FTI Export":
    from views.d365_export import render
    render(engine, available_years)

elif selected_tab == "🔄 Reconciliation":
    from views.reconciliation import render
    render(engine, available_years)
    
elif selected_tab == "📩 Email Follow-up":
    from views.email_followup import render
    render(engine, available_years)   

elif selected_tab == "👤 Registration":
    from views.registration import render
    render(engine)

elif selected_tab == "🗑️ Batch Management":
    from views.batches import render
    render(engine)

elif selected_tab == "⚙️ System Admin":
    from views.admin import render
    render()
