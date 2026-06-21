"""
config.py — App-wide constants and Streamlit secrets accessor.

"""

import streamlit as st

# ── Default filter values ─────────────────────────────────────────────────────
DEFAULT_MARKETPLACE     = "Amazon India FBA"
DEFAULT_SHIPPING        = "FBA"
DEFAULT_SHIPPING_LEVEL  = "Premium"
DEFAULT_AREA            = "National"
NONE_SELECTION         = "None Selection"  # For item_code dropdown
NONE_CATEGORY        = "None"           # For category extraction fallback

# -- GST--------------------------
INCLUDED = "Included"
EXCLUDED = "Exculded"

# ── DB secrets accessor ───────────────────────────────────────────────────────
def get_db_config() -> dict:
    """Return DB connection kwargs from Streamlit secrets."""
    db = st.secrets["db"]
    return {
        "host":     db["HOST"],
        "port":     int(db.get("PORT", 3306)),
        "database": db["DATABASE"],
        "user":     db["USER"],
        "password": db["PASSWORD"],
    }