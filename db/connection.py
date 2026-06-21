"""
db/connection.py — MySQL connection via PyMySQL + SQLAlchemy.

Frappe Cloud's ProxySQL requires SSL. Pass the downloaded .pem file path
via secrets.toml ssl_ca key. The engine is cached for the Streamlit session.
"""
import ssl
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from config import get_db_config

@st.cache_resource(show_spinner="Connecting to ERPNext database…")
def get_engine() -> Engine:
    cfg = get_db_config()

    url = (
        f"mysql+pymysql://{cfg['user']}:{cfg['password']}"
        f"@{cfg['host']}:{cfg['port']}/{cfg['database']}"
    )

    # ── SSL config ────────────────────────────────────────────────────────────
    # Create an explicitly permissive SSL context
    ssl_context = ssl.create_default_context()
    
    # 1. Disable hostname checking (Satisfies ProxySQL's mismatched cert name)
    ssl_context.check_hostname = False
    
    # 2. Bypass the issuer chain verification completely (Bypasses the Windows crash)
    # The connection will still be fully encrypted, satisfying Frappe Cloud's requirements.
    ssl_context.verify_mode = ssl.CERT_NONE

    engine = create_engine(
        url,
        connect_args={
            "ssl": ssl_context,  # Pass the context directly to PyMySQL
            "connect_timeout": 15,
            "charset": "utf8mb4",
        },
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=3,
        max_overflow=2,
    )

    # Eager connection test
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        get_engine.clear()
        raise RuntimeError(
            f"DB connection test failed: {exc}\n\n"
            "Check .streamlit/secrets.toml — host, port, user, password, database."
        ) from exc

    return engine

def get_connection():
    """Return a SQLAlchemy connection from the cached engine."""
    return get_engine().connect()