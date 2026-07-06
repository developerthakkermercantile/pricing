import pandas as pd
import numpy as np
import re  # Needed to extract the GST number from the text template
from config import INCLUDED

def map_item_charges(
    item_df: pd.DataFrame, 
    slabs_df: pd.DataFrame,
    gst_status: str,  # Determines which formula to use ("Included" or "Excluded")
    product_gst_status
) -> pd.DataFrame:
    """
    Maps your item master query records to dynamic cost slab elements.
    
    Parameters:
    - items_df: The output DataFrame from your complex SQL query.
    - slabs_df: The raw active fee slabs retrieved from load_slabs().
    - gst_status: String determining which formula to use ("Included" or "Excluded").
    - product_gst_status: Determines if GST should be added to the base reseller rate.
    
    Returns:
    - DataFrame with newly mapped columns including calculated percentage amounts, totals, GST added, and M_ceiling.
    """
    # 1. Fallback if either dataframe is empty
    if item_df.empty or slabs_df.empty:
        fallback_cols = [
            "GST Amount Added (₹)", "Adjusted Price (₹)", "Bucket A (₹)", "Bucket B (%)", 
            "Bucket B Amount (₹)", "Bucket C (₹)", "Total Cost (A+B+C)", 
            "M_ceiling (₹)", "Mapped Category"
        ]
        for col in fallback_cols:
            item_df[col] = 0.0 if "Category" not in col else "None"
        return item_df

    # 2. Extract the single row as a Series
    item_row = item_df.iloc[0]

    # --- EXTRACT BASE VALUES ---
    weight = float(item_row.get("chargeable_weight", 0.0))
    base_price = float(item_row.get("reseller_rate", 0.0)) 
    
    tax_str = str(item_row.get("item_tax_template", "0"))
    gst_match = re.search(r'\d+', tax_str)
    gp_val = float(gst_match.group()) if gst_match else 0.0
    gp_decimal = gp_val / 100.0  

    # --- CALCULATE ADJUSTED PRICE ---
    if product_gst_status == INCLUDED:
        gst_added_amount = base_price * gp_decimal
        price = base_price - gst_added_amount  # Fixed: changed - to +
    else:
        gst_added_amount = 0.0
        price = base_price
        
    print(f"GST decimal: {gp_decimal} | GST Added: {round(gst_added_amount, 2)} | Adjusted Price: {round(price, 2)}")

    # --- MAP BUCKET A (Courier) ---
    slab_a_matches = slabs_df[
        (slabs_df["cost_lower_slab"] <= weight) & 
        (slabs_df["cost_higher_slab"] >= weight)
    ]
    a_cost = float(slab_a_matches["a"].sum()) if not slab_a_matches.empty else 0.0

    # --- MAP BUCKET B (Referral) ---
    slab_b_matches = slabs_df[
        (slabs_df["cost_lower_slab"] <= price) & 
        (slabs_df["cost_higher_slab"] >= price)
    ]
    b_rate = float(slab_b_matches["b"].sum()) if not slab_b_matches.empty else 0.0
    b_amount = price * b_rate

    # --- MAP BUCKET C (Closing/Fixed) ---
    slab_c_matches = slabs_df[
        (slabs_df["cost_lower_slab"] <= price) & 
        (slabs_df["cost_higher_slab"] >= price)
    ]
    c_cost = float(slab_c_matches["c"].sum()) if not slab_c_matches.empty else 0.0

    # --- CALCULATE CEILING (S) ---
    M = price
    A = a_cost
    C = c_cost
    B_rate = b_rate
    
    if gst_status == INCLUDED:
        print("GST Included")
        numerator = M + ((A + C) * 1.18)
        denominator = (1 / (1 + gp_decimal)) - (B_rate * 1.18)
    else:
        print('GST excluded')
        numerator = M + A + C
        denominator = (1 / (1 + gp_decimal)) - B_rate
        
    print(f"Numerator : {numerator} | Denominator : {denominator}")
    
    s_value = (numerator / denominator) if denominator != 0 else 0.0

    # --- ASSIGN DIRECTLY TO DATAFRAME ---
    output_df = item_df.copy()
    output_df["GST Amount Added (₹)"] = round(gst_added_amount, 2)
    output_df["Adjusted Price (₹)"] = round(price, 2)
    output_df["Bucket A (₹)"] = a_cost
    output_df["Bucket B (%)"] = f"{b_rate * 100:.2f}%"
    output_df["Bucket B Amount (₹)"] = b_amount
    output_df["Bucket C (₹)"] = c_cost
    output_df["Total Cost (A+B+C)"] = a_cost + b_amount + c_cost
    output_df["M_ceiling (₹)"] = round(s_value, 2)

    return output_df