import pandas as pd
import streamlit as st
from sqlalchemy import text

from db.connection import get_engine
from db.queries import (
    ITEM_DESCENDANTS_QUERY,
    SLAB_QUERY,
    DISTINCT_SHIPPING_LEVELS_QUERY,
    DISTINCT_AREAS_QUERY,
    ITEMS_MERGED_WITH_ECOM_CHARGES_QUERY,
    ITEM_QUERY
)

# ── Global Cache ──────────────────────────────────────────────────────────────
# We initialize it as None to manage clean assignments safely
_items_cache = None  

@st.cache_data(ttl=3600, show_spinner="Loading fee slabs from ERPNext…")
def load_slabs(
    market_place: str,
    shipping: str,
    shipping_level: str,
    area: str,
) -> pd.DataFrame:
    params = {
        "market_place":   market_place,
        "shipping":       shipping,
        "shipping_level": shipping_level,
        "area":           area,
    }

    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(text(SLAB_QUERY), conn, params=params)

    if df.empty:
        return df

    df["lower_slab"]  = pd.to_numeric(df["lower_slab"],  errors="coerce").fillna(0)
    df["higher_slab"] = pd.to_numeric(df["higher_slab"], errors="coerce").fillna(0)

    return df

@st.cache_data(ttl=3600)
def load_items() -> pd.DataFrame:
    global _items_cache
    
    # If cache is already populated, return it directly
    if _items_cache is not None and not _items_cache.empty:
        return _items_cache
    
    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(text(ITEM_QUERY), conn)
        
    # FIX: Use a simple assignment to store the complete dataframe copy
    _items_cache = df.copy()  
    return df

def load_item_descendants(item_code: str) -> list[str]:
    """Fetches all native child group category names below an item's parent group."""
    # Ensure items cache is populated before querying it
    items_df = load_items()
    
    # Filter out matching row
    matching_row = items_df[items_df["item_code"] == item_code]
    if matching_row.empty:
        return ["All"]
        
    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(text(ITEM_DESCENDANTS_QUERY), conn, params={"item_code": item_code})
    
    # Return list of descendants, always ensuring 'All' is paired in
    categories = ["All"]
    if not df.empty:
        categories.extend(df["descendant_group"].dropna().tolist())
    return list(set(categories))

def load_items_merged_with_ecom_charges(
    market_place: str,
    shipping: str,
    shipping_level: str,
    area: str
) -> pd.DataFrame:
    
    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(text(ITEMS_MERGED_WITH_ECOM_CHARGES_QUERY), conn, params={
            "market_place": market_place,
            "shipping": shipping,
            "shipping_level": shipping_level,
            "area": area
        })

    return df

@st.cache_data(ttl=3600)
def load_areas() -> list[str]:
    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(text(DISTINCT_AREAS_QUERY), conn)
    return df["area"].dropna().tolist()

@st.cache_data(ttl=3600)
def load_shipping_levels() -> list[str]:
    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(text(DISTINCT_SHIPPING_LEVELS_QUERY), conn)
    return df["shipping_level"].dropna().tolist()