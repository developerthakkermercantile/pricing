"""
app.py — Amazon Cost Slab Calculator
Entry point for the Streamlit app.

Run:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd

from logic.db_data_loaders import load_slabs, load_items, load_item_descendants, load_items_merged_with_ecom_charges
from logic.slab_merger import build_merged_grid
from ui.sidebar import render_sidebar
from logic.calculate_cost import map_item_charges
from config import (
    NONE_SELECTION, NONE_CATEGORY
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=" Cost Slab Calculator",
    page_icon="📦",
    layout="wide",
)

st.title("📦 Cost Slab Calculator")

# ── Sidebar ───────────────────────────────────────────────────────────────────
params = render_sidebar()

# ── Item & Category Selection UI Element ──────────────────────────────────────
st.subheader("🔍 Select Product Item")
unique_items = load_items()

selected_item = st.selectbox(
    "Select an Item Code:",
    options=[NONE_SELECTION] + unique_items["item_code"].dropna().tolist(),
    help="Select a specific item code to auto-extract its category and referral fee percent rate."
)

st.dataframe(
    unique_items,
    column_config={
        "item_code": st.column_config.TextColumn("Item Code"),
        "item_name": st.column_config.TextColumn("Item Name"),
        "placeholder_cost": st.column_config.NumberColumn("Placeholder Cost", format="%.2f"),
        "weight_per_unit": st.column_config.NumberColumn("Weight per Unit (kg)", format="%.3f"),
        "amazon_category": st.column_config.TextColumn("Amazon Category"),
        "referral_fee_percent": st.column_config.NumberColumn("Referral Fee %", format="%.2f"),
        "item_tax_template": st.column_config.TextColumn("Item Tax template"),
    },
    hide_index=True,
)

# ── Load slabs ────────────────────────────────────────────────────────────────
with st.spinner("Fetching fee slabs…"):
    try:
        ecom_charges = load_slabs(
            market_place   = params["marketplace"],
            shipping       = params["shipping"],
            shipping_level = params["shipping_level"],
            area           = params["area"],
        )
    except Exception as e:
        st.error(f"❌ Failed to load slabs from DB: {e}")
        st.stop()

if ecom_charges.empty:
    st.warning("No slabs returned for the selected filter combination. Adjust sidebar filters.")
    st.stop()
else:
    st.success(f"✅ Loaded {len(ecom_charges)} slab rows")
    st.dataframe(
        ecom_charges,
        column_config={
            "item_code": st.column_config.TextColumn("Item Code"),
            "item_tax_template": st.column_config.TextColumn("Item Tax Template"),
            "price_list_rate": st.column_config.NumberColumn("Price List Rate", format="%.2f"),
            "market_place": st.column_config.TextColumn("Marketplace"),
            "shipping": st.column_config.TextColumn("Shipping Type"),
            "shipping_level": st.column_config.TextColumn("Shipping Level"),
            "category": st.column_config.TextColumn("Product Category"),
            "area": st.column_config.TextColumn("Area"),
            "charger_type": st.column_config.TextColumn("Charge Type (A/B/C)"),
            "bucket": st.column_config.TextColumn("Bucket (A/B/C)"),
            "lower_slab": st.column_config.NumberColumn("Lower Slab", format="%d"),
            "higher_slab": st.column_config.NumberColumn("Higher Slab", format="%d"),
        },
        hide_index=True,
    )


# ── Step: Resolve Selected Item down to its Product Category ──────────────────
target_category = NONE_CATEGORY

if selected_item != NONE_SELECTION:
    # Search inside loaded slabs to extract what category matches the item code
    target_categories = load_item_descendants(selected_item)
    print(f"Resolved target categories for item '{selected_item}' are: {target_categories}")

    # ── EXTRACT SPECIFIC ITEM'S TAX TEMPLATE ──────────────────────────────────────
    # 1. Filter the unique_items dataframe for the selected item code
    matched_row = unique_items[unique_items["item_code"] == selected_item]
    
    # 2. Safely extract the tax template value (if the row exists)
    if not matched_row.empty:
        item_tax = matched_row["item_tax_template"].iloc[0]
    else:
        item_tax = "0" # Fallback if missing

    # ── Build merged grid ─────────────────────────────────────────────────────────────
    with st.spinner("Building merged grid…"):
        try:
            # CRITICAL: We pass the dynamically resolved target category value here
            cost_slab = build_merged_grid(ecom_charges, target_categories=target_categories, item_tax_template=item_tax, gst_status=params["gst_status"], product_gst_status=params["product_gst_status"])
        except Exception as e:
            st.error(f"❌ Failed to build merged grid: {e}")
            st.stop()


    # ── Display the Merged Grid ───────────────────────────────────────────────────
    st.subheader("📊 Merged Cost Slabs")

    if not cost_slab.empty:
        st.success(f"✅ Merged grid has {len(cost_slab)} slabs")
        
        # Optional formatting wrapper layout for a cleaner look
        st.dataframe(
            cost_slab,
            column_config={
                "lower_slab": st.column_config.NumberColumn("Lower Slab", format="%d"),
                "higher_slab": st.column_config.NumberColumn("Higher Slab", format="%d"),
                "cost_lower_slab": st.column_config.NumberColumn("Cost Lower Slab", format="%.2f"),
                "cost_higher_slab": st.column_config.NumberColumn("Cost Higher Slab", format="%.2f"),
                "a": st.column_config.NumberColumn("A (Courier)", format="%.2f"),
                "b": st.column_config.NumberColumn("B (Referral %)"),
                "b_amount": st.column_config.NumberColumn("B (Referral amount)", format="%.2f"),
                "c": st.column_config.NumberColumn("C (Closing/Pick)", format="%.2f"),
                "gst_percentage": st.column_config.NumberColumn("GST Percentage"),
                "gst_amount": st.column_config.NumberColumn("GST amount", format="%.2f"),
                "product_gst_percentage": st.column_config.NumberColumn("Product GST Percentage"),
                "product_gst_amount": st.column_config.NumberColumn("Product GST amount", format="%.2f"),
                "total": st.column_config.NumberColumn("Total Fixed Costs", format="%.2f"),
            },
        )

    else:
        st.info("The merged grid generated an empty DataFrame.")

    item_df = load_items_merged_with_ecom_charges(
        market_place=params["marketplace"],
        shipping=params["shipping"],
        shipping_level=params["shipping_level"],
        area=params["area"]
    )

    st.subheader("📋 Items Mapped with E-commerce Charges")
    mapped_df = map_item_charges(item_df, cost_slab, params["gst_status"], params["product_gst_status"])
    st.dataframe(mapped_df, hide_index=True)
    
