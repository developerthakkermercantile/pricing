"""
ui/sidebar.py — Sidebar: marketplace filters, SKU multi-select, global params.
"""

import streamlit as st
import pandas as pd
from config import (
    DEFAULT_MARKETPLACE, DEFAULT_SHIPPING, DEFAULT_SHIPPING_LEVEL,
    DEFAULT_AREA, INCLUDED, EXCLUDED
)
from logic.db_data_loaders import load_shipping_levels, load_areas


def render_sidebar() -> dict:
    st.sidebar.title("⚙️ Filters")

    # ── Marketplace filters ───────────────────────────────────────────────────
    st.sidebar.subheader("Marketplace")

    marketplace = st.sidebar.text_input(
        "Marketplace",
        value=DEFAULT_MARKETPLACE,
        help="Matches the 1st segment of the ERPNext item code.",
    )
    shipping = st.sidebar.text_input(
        "Shipping type",
        value=DEFAULT_SHIPPING,
        help="FBA / FBF / Self-ship etc.",
    )

    try:
        shipping_levels = load_shipping_levels()
    except Exception:
        shipping_levels = [DEFAULT_SHIPPING_LEVEL]

    try:
        areas = load_areas()
    except Exception:
        areas = [DEFAULT_AREA]

    shipping_level = st.sidebar.selectbox(
        "Shipping level",
        options=shipping_levels,
        index=shipping_levels.index(DEFAULT_SHIPPING_LEVEL)
              if DEFAULT_SHIPPING_LEVEL in shipping_levels else 0,
    )
    area = st.sidebar.selectbox(
        "Area",
        options=areas,
        index=areas.index(DEFAULT_AREA) if DEFAULT_AREA in areas else 0,
    )

    # ── Tax filters ───────────────────────────────────────────────────────────
    gst_status = st.sidebar.selectbox(
        "GST",
        options=[INCLUDED, EXCLUDED],
        index=0,  # Sets "Included" as the default. Change to 1 for "Excluded"
        help="Specify whether GST is included or excluded in the pricing."
    )

    # ── Product Tax filters ───────────────────────────────────────────────────────────
    product_gst_status = st.sidebar.selectbox(
        "Product Tax GST",
        options=[INCLUDED, EXCLUDED],
        index=0,  # Sets "Included" as the default. Change to 1 for "Excluded"
        help="Specify whether Product GST is included or excluded in the pricing."
    )

    return {
        "marketplace":    marketplace,
        "shipping":       shipping,
        "shipping_level": shipping_level,
        "area":           area,
        "gst_status":     gst_status,
        "product_gst_status": product_gst_status
    }