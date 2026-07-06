"""
app.py — Amazon Cost Slab Calculator
Entry point for the Streamlit app.

Run:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd

from logic.db_data_loaders import (
    load_slabs, 
    load_items, 
    load_item_descendants, 
    load_items_merged_with_ecom_charges
)
from logic.slab_merger import build_merged_grid
from ui.sidebar import render_sidebar
from logic.calculate_cost import map_item_charges
from config import NONE_SELECTION, NONE_CATEGORY

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Cost Slab Calculator",
    page_icon="📦",
    layout="wide",
)

st.title("📦 Bulk Cost Slab Calculator")

# ── Sidebar ───────────────────────────────────────────────────────────────────
params = render_sidebar()

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
    st.success(f"✅ Loaded {len(ecom_charges)} slab rows for {params['marketplace']}")
    with st.expander("👀 View Raw E-Commerce Slabs"):
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

# ── Bulk CSV Upload & Processing ──────────────────────────────────────────────
st.subheader("📁 Bulk Upload Items (CSV)")
st.write("Upload a CSV containing multiple items to calculate costs in bulk.")

uploaded_file = st.file_uploader("Upload CSV (must contain 'item_code' column)", type=["csv"])

if uploaded_file is not None:
    # 1. Read CSV and validate
    bulk_df = pd.read_csv(uploaded_file)
    
    if "item_code" not in bulk_df.columns:
        st.error("❌ The uploaded CSV must contain a column named exactly 'item_code'.")
        st.stop()
        
    # Extract unique item codes from the upload
    item_codes_list = bulk_df["item_code"].dropna().unique().tolist()
    st.info(f"✅ Extracted {len(item_codes_list)} unique item codes from CSV.")

    # 2. Load all merged e-com items from DB 
    with st.spinner("Fetching item details from database..."):
        full_item_df = load_items_merged_with_ecom_charges(
            market_place=params["marketplace"],
            shipping=params["shipping"],
            shipping_level=params["shipping_level"],
            area=params["area"]
        )
    
    # 3. Filter DB results to match ONLY what was in the uploaded CSV
    filtered_item_df = full_item_df[full_item_df["item_code"].isin(item_codes_list)]
    
    if filtered_item_df.empty:
        st.warning("⚠️ None of the uploaded item codes matched the database records. Check for typos or leading/trailing spaces in your CSV.")
        st.stop()
        
    st.success(f"🔍 Successfully matched {len(filtered_item_df)} items from the database.")
    
    with st.expander("👀 View Fetched Item Base Data"):
        st.dataframe(filtered_item_df, hide_index=True)

    # ── 4. Batch Process Items Individually (The Loop) ────────────────────────
    st.subheader("⚙️ Processing Batch...")
    
    # Initialize a list to hold the calculated dataframes for each item
    processed_items_list = []
    
    # Setup a progress bar to show the user it's working
    progress_bar = st.progress(0)
    total_items = len(filtered_item_df)
    status_text = st.empty()

    for i in range(total_items):
        # Isolate the single row as its own dataframe to preserve column structure
        single_item_df = filtered_item_df.iloc[[i]].copy()
        item_code = single_item_df["item_code"].iloc[0]
        
        status_text.text(f"({i + 1}/{total_items}) | Calculating costs for: {item_code} \n ")
        
        # 4a. Resolve specific categories for THIS item only
        target_categories = load_item_descendants(item_code)
        
        # 4b. Build a custom merged grid strictly for THIS item's categories
        try:
            item_cost_slab = build_merged_grid(
                ecom_charges, 
                target_categories=target_categories, 
                item_tax_template="0", # Handled dynamically inside map_item_charges now
                gst_status=params["gst_status"], 
                product_gst_status=params["product_gst_status"]
            )
        except Exception as e:
            st.error(f"❌ Failed to build merged grid for {item_code}: {e}")
            continue # Skip this item and move to the next one if it fails

        # 4c. Map the charges for THIS specific item against its custom grid
        try:
            mapped_single_item = map_item_charges(
                single_item_df, 
                item_cost_slab, 
                params["gst_status"], 
                params["product_gst_status"]
            )
            processed_items_list.append(mapped_single_item)
        except Exception as e:
            st.error(f"❌ Failed to map charges for {item_code}: {e}")
            continue
            
        # Update progress bar
        progress_bar.progress((i + 1) / total_items)
        
    status_text.text("✅ Batch processing complete!")

    # ── 5. Combine and Display Results ────────────────────────────────────────────
    if processed_items_list:
        # Merge all the individually processed 1-row dataframes back into a single table
        final_mapped_df = pd.concat(processed_items_list, ignore_index=True)
        
        st.subheader("📋 Final Calculation: Mapped Charges & Ceiling Margins")
        st.dataframe(final_mapped_df, hide_index=True)
        
        # ── Export Results ────────────────────────────────────────────────────────
        st.markdown("---")
        csv_data = final_mapped_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="⬇️ Download Calculated Costs as CSV",
            data=csv_data,
            file_name='bulk_item_costs_calculated.csv',
            mime='text/csv',
            use_container_width=True
        )
    else:
        st.error("⚠️ No items were successfully processed.")