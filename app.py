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
</style>
""",
    unsafe_allow_html=True,
)

# ── Dynamic Theme & Toast Styling ─────────────
dark_theme_enabled = st.session_state.get("dark_mode", False)
theme_css = ""
if dark_theme_enabled:
    theme_css = """
    <style>
    /* Dark Mode variables & overrides */
    .stApp {
        background-color: #0b0f19 !important;
        color: #f8fafc !important;
    }
    div[data-testid="stAppViewContainer"] {
        background-color: #0b0f19 !important;
        color: #f8fafc !important;
    }
    div[data-testid="stHeader"] {
        background-color: #0b0f19 !important;
    }
    
    /* Clean, selective typography overrides */
    h1, h2, h3, h4, h5, h6 {
        color: #f8fafc !important;
    }
    div[data-testid="stMarkdownContainer"] p {
        color: #e2e8f0 !important;
    }
    div[data-testid="stMarkdownContainer"] span {
        color: #e2e8f0 !important;
    }
    
    /* Sidebar styling in Dark Mode */
    section[data-testid="stSidebar"] {
        background-color: #0d111d !important;
        border-right: 1px solid #1f2937 !important;
    }
    section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] h4, section[data-testid="stSidebar"] h5, section[data-testid="stSidebar"] h6, section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] span, section[data-testid="stSidebar"] small {
        color: #e2e8f0 !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label {
        color: #94a3b8 !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
        background-color: #1f2937 !important;
        color: #f1f5f9 !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label[data-baseweb="radio"] input:checked + div {
        background-color: #1e3a8a !important; 
        color: #60a5fa !important; 
        border-left: 4px solid #3b82f6 !important; 
    }
    
    /* Widget Labels & Text inputs */
    div[data-testid="stWidgetLabel"] p {
        color: #f1f5f9 !important;
        font-weight: 500 !important;
    }
    div[data-testid="stCheckbox"] p, div[data-testid="stCheckbox"] span {
        color: #f1f5f9 !important;
    }
    
    /* Metrics */
    [data-testid="stMetricValue"] { color: #60a5fa !important; }
    [data-testid="stMetricLabel"] { color: #94a3b8 !important; }
    [data-testid="stMetric"] {
        background-color: #1e293b !important;
        border-left: 6px solid #3b82f6 !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3) !important;
    }
    
    /* Expander fixes (expander headers background color and text color) */
    div[data-testid="stExpander"] {
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 10px !important;
    }
    div[data-testid="stExpander"] summary {
        background-color: #1e293b !important;
        color: #f8fafc !important;
        border-radius: 10px 10px 0 0 !important;
        border-bottom: 1px solid #334155 !important;
    }
    div[data-testid="stExpander"] summary:hover {
        background-color: #243147 !important;
    }
    div[data-testid="stExpander"] summary span {
        color: #f8fafc !important;
    }
    div[data-testid="stExpander"] summary svg {
        fill: #f8fafc !important;
    }
    
    /* Forms */
    div[data-testid="stForm"] {
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 12px !important;
        padding: 20px !important;
    }
    
    /* Input fields (select, inputs, text areas) */
    div[data-baseweb="select"] > div {
        background-color: #0f172a !important;
        color: #f8fafc !important;
        border: 1px solid #334155 !important;
    }
    div[data-baseweb="select"] svg {
        fill: #f8fafc !important;
    }
    input[data-testid="stTextInputBase"] {
        background-color: #0f172a !important;
        color: #f8fafc !important;
        border: 1px solid #334155 !important;
    }
    input[type="number"] {
        background-color: #0f172a !important;
        color: #f8fafc !important;
        border: 1px solid #334155 !important;
    }
    
    /* Buttons in Dark Mode */
    .stButton > button {
        background-color: #3b82f6 !important;
        color: #ffffff !important;
    }
    .stButton > button:hover {
        background-color: #2563eb !important;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4) !important;
    }
    
    /* Tabs */
    button[data-baseweb="tab"] {
        color: #94a3b8 !important;
    }
    button[data-baseweb="tab"]:hover {
        color: #60a5fa !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #60a5fa !important;
        border-bottom-color: #3b82f6 !important;
    }
    
    /* Dataframes and Tables */
    div[data-testid="stDataFrame"] table {
        background-color: #1e293b !important;
        color: #f8fafc !important;
    }
    div[data-testid="stDataFrame"] th {
        background-color: #0f172a !important;
        color: #f8fafc !important;
    }
    div[data-testid="stDataFrame"] td {
        background-color: #1e293b !important;
        color: #f8fafc !important;
    }
    
    .glass-card {
        background: rgba(30, 41, 59, 0.7) !important;
        backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 12px !important;
        padding: 16px !important;
    }
    </style>
    """
else:
    theme_css = """
    <style>
    [data-testid="stMetricValue"] { font-size: 32px !important; color: #0d47a1 !important; }
    [data-testid="stMetric"] { background-color: #ffffff; padding: 25px; border-radius: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border-left: 6px solid #0d47a1; }
    .glass-card { background: rgba(255, 255, 255, 0.8) !important; backdrop-filter: blur(12px) !important; border: 1px solid rgba(0, 0, 0, 0.08) !important; border-radius: 12px !important; padding: 16px !important; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03) !important; }
    </style>
    """

# Append the modern, styled toast overlays
theme_css += """
<style>
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
"""

st.markdown(theme_css, unsafe_allow_html=True)

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
    # 🌓 Corporate Theme Switcher
    dark_mode = st.toggle("🌙 Dark Mode", value=st.session_state.get("dark_mode", False))
    st.session_state["dark_mode"] = dark_mode
    st.markdown("---")

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
