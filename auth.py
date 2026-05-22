# auth.py
# ─────────────────────────────────────────────
# Authentication: bcrypt hashing + login form
# + session-timeout check + Cookie persistence
# ─────────────────────────────────────────────
import time
import bcrypt
import streamlit as st
from sqlalchemy.sql import func
from streamlit_cookies_controller import CookieController

from config import TIMEOUT_MIN
from models import get_db, SystemUser

# تعريف الكنترولر المسؤول عن قراءة وحفظ الكوكيز
controller = CookieController()

# ── Password hashing (bcrypt, salted) ─────────
def hash_pw(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_pw(plain: str, hashed: str) -> bool:
    """
    Supports both bcrypt hashes (new) and legacy SHA-256 hashes (old).
    Automatically upgrades SHA-256 passwords to bcrypt on first login.
    """
    try:
        # bcrypt hashes always start with $2b$ or $2a$
        if hashed.startswith("$2b$") or hashed.startswith("$2a$"):
            return bcrypt.checkpw(plain.encode(), hashed.encode())
        else:
            # Legacy SHA-256 path
            import hashlib
            return hashlib.sha256(plain.encode()).hexdigest() == hashed
    except Exception:
        return False

# ── Session helpers ───────────────────────────
def init_session():
    # 🟢 1. قراءة الكوكيز من المتصفح أولاً
    cookie_user = controller.get('logged_in_user')
    cookie_role = controller.get('user_role')

    # لو الكوكيز موجودة واليوزر مش مسجل دخول في الجلسة الحالية، دخله أوتوماتيك
    if cookie_user and cookie_role and not st.session_state.get("authenticated"):
        st.session_state["authenticated"] = True
        st.session_state["logged_in_user"] = cookie_user
        st.session_state["user_role"] = cookie_role
        st.session_state["last_activity"] = time.time()
        st.session_state["lookup_id"] = 0
        return # خلاص دخل، مفيش داعي نكمل

    # 🟢 2. لو مفيش كوكيز، حط القيم الافتراضية (تسجيل خروج)
    defaults = {
        "authenticated": False,
        "logged_in_user": None,
        "user_role": None,
        "lookup_id": 0,
        "last_activity": time.time(),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def check_timeout():
    """Call once per page load. Returns True if session is still alive."""
    if not st.session_state.get("authenticated"):
        return False
        
    elapsed = time.time() - st.session_state.get("last_activity", 0)
    
    if elapsed > TIMEOUT_MIN * 60:
        logout()
        st.warning(f"⚠️ Session expired after {TIMEOUT_MIN} minutes of inactivity. Please log in again.")
        
        if st.button("🔄 العودة لشاشة تسجيل الدخول", type="primary"):
            st.session_state["last_activity"] = time.time()
            st.rerun()
            
        return False
        
    st.session_state["last_activity"] = time.time()
    return True


def logout():
    st.session_state["authenticated"] = False
    st.session_state["logged_in_user"] = None
    st.session_state["user_role"] = None
    
    # 🟢 مسح الكوكيز من المتصفح عند تسجيل الخروج
    controller.remove('logged_in_user')
    controller.remove('user_role')


def require_role(*roles: str):
    """
    Render an access-denied message and stop execution
    if the current user's role is not in `roles`.
    """
    role = st.session_state.get("user_role", "")
    if role not in roles:
        st.error(
            f"🔒 **Access denied.** This section requires one of: "
            f"{', '.join(roles)}. Your role is **{role or 'unknown'}**."
        )
        st.stop()


# ── Login form ────────────────────────────────
def login_form():
    st.markdown("<br><br><br><br>", unsafe_allow_html=True)
    _, col, _ = st.columns([1.5, 2, 1.5])
    with col:
        st.markdown(
            "<h2 style='text-align:center;color:#004a99;'>🔒 Finance Login</h2>",
            unsafe_allow_html=True,
        )
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            st.markdown("<br>", unsafe_allow_html=True)
            submitted = st.form_submit_button("🚀 Login", use_container_width=True)

        if submitted:
            with get_db() as db:
                user = (
                    db.query(SystemUser)
                    .filter(
                        func.lower(SystemUser.username) == username.lower().strip(),
                        SystemUser.is_active == True,
                    )
                    .first()
                )
                if user and verify_pw(password, user.password_hash):

                    if not user.password_hash.startswith(("$2b$", "$2a$")):
                        user.password_hash = hash_pw(password)
                        db.commit()
                        
                    st.session_state["authenticated"]  = True
                    st.session_state["logged_in_user"] = user.username
                    st.session_state["user_role"]      = user.role
                    st.session_state["last_activity"]  = time.time()
                    
                    # 🟢 حفظ البيانات في المتصفح لمدة 30 يوم (2592000 ثانية)
                    controller.set('logged_in_user', user.username, max_age=2592000)
                    controller.set('user_role', user.role, max_age=2592000)
                    
                    st.rerun()
                else:
                    st.error("❌ Invalid username / password, or account disabled.")
