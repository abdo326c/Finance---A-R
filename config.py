# config.py
# ─────────────────────────────────────────────
# Centralized constants & environment config
# ─────────────────────────────────────────────
import streamlit as st

VALID_TERMS    = ["Fall", "Spring", "Summer"]
# 🟢 تم إضافة "Test" في نهاية القائمة
VALID_STATUSES = ["Active", "Inactive", "Graduated", "Program Withdraw", "Semester Withdraw", "Test"]
VALID_COLLEGES = ["ENG", "BBA", "IT_CS", "BIO_TECH"]
VALID_ROLES    = ["Admin", "Editor", "Viewer"]
DEFAULT_YEAR   = 2026

MAX_BULK_ROWS  = 5_000          # guard against huge uploads freezing the app
TIMEOUT_MIN    = 30             # session idle timeout in minutes

DB_URL = st.secrets.get("DB_URL", "sqlite:///finance.db")
