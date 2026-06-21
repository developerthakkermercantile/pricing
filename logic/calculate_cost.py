import pandas as pd
import numpy as np
import re  # Needed to extract the GST number from the text template
from config import INCLUDED

def map_item_charges(
    items_df: pd.DataFrame, 
    slabs_df: pd.DataFrame,
    gst_status: str  # NEW: Pass "Included" or "Excluded" here
) -> pd.DataFrame:
    """
    Maps your item master query records to dynamic cost slab elements.
    
    Parameters:
    - items_df: The output DataFrame from your complex SQL query.
    - slabs_df: The raw active fee slabs retrieved from load_slabs().
    - gst_status: String determining which formula to use ("Included" or "Excluded").
    
    Returns:
    - DataFrame with newly mapped columns including calculated percentage amounts, totals, and M_ceiling.
    """
    if items_df.empty or slabs_df.empty:
        # Return fallback zeros if either dataframe arrives empty
        fallback_cols = [
            "Bucket A (₹)", "Bucket B (%)", "Bucket B Amount (₹)", 
            "Bucket C (₹)", "Total Cost (A+B+C)", "M_ceiling (₹)", "Mapped Category"
        ]
        for col in fallback_cols:
            items_df[col] = 0.0 if "Category" not in col else "None"
        return items_df

    # Lists to append calculated outcomes row by row
    bucket_a_list = []
    bucket_b_rate_list = []
    bucket_b_amount_list = []  
    bucket_c_list = []
    m_ceiling_list = [] # To store the calculated Margin Ceiling (S)

    # Iterate over each row in your main item query output
    for _, item_row in items_df.iterrows():
        weight = float(item_row.get("chargeable_weight", 0.0))
        price = float(item_row.get("reseller_rate", 0.0)) # This is M

        # --- STEP 2: MAP BUCKET A (Courier Fees) VIA WEIGHT ---
        slab_a_matches = slabs_df[
            (slabs_df["cost_lower_slab"] <= weight) & 
            (slabs_df["cost_higher_slab"] >= weight)
        ]
        a_cost = float(slab_a_matches["a"].sum()) if not slab_a_matches.empty else 0.0
        bucket_a_list.append(a_cost)

        # --- STEP 3: MAP BUCKET B (Referral %) VIA PRICE & RESOLVED CATEGORY ---
        slab_b_matches = slabs_df[
            (slabs_df["cost_lower_slab"] <= price) & 
            (slabs_df["cost_higher_slab"] >= price)
        ]
        b_rate = float(slab_b_matches["b"].sum()) if not slab_b_matches.empty else 0.0
        bucket_b_rate_list.append(b_rate)
        
        # Calculate the actual monetary amount for Bucket B (based on base price M)
        b_amount = price * b_rate
        bucket_b_amount_list.append(b_amount)

        # --- STEP 4: MAP BUCKET C (Closing / Handling Fees) VIA PRICE ---
        slab_c_matches = slabs_df[
            (slabs_df["cost_lower_slab"] <= price) & 
            (slabs_df["cost_higher_slab"] >= price)
        ]
        c_cost = float(slab_c_matches["c"].sum()) if not slab_c_matches.empty else 0.0
        bucket_c_list.append(c_cost)

        # --- STEP 5: CALCULATE M_ceiling (The New Math for 'S') ---
        # 1. Extract Gp from the item_df's tax template (e.g., "18 GST" -> 18)
        tax_str = str(item_row.get("item_tax_template", "0"))
        gst_match = re.search(r'\d+', tax_str)
        gp_val = float(gst_match.group()) if gst_match else 0.0
        gp_decimal = gp_val / 100.0  # Convert to decimal (e.g., 0.18)
        print("GST decimal")
        print(gp_decimal)
        
        # 2. Map variables to the formula terms for clarity
        M = price
        A = a_cost
        C = c_cost
        B_rate = b_rate
        
        # 3. Apply the correct formula based on gst_status
        if gst_status == INCLUDED:
            # Version 1: With Service GST (Defensive Cash-Flow Guard)
            print("GST INcluded")
            numerator = M + ((A + C) * 1.18)
            denominator = (1 / (1 + gp_decimal)) - (B_rate * 1.18)
        else:
            # Version 2: Without Service GST (Pure Input Credit Pass-Through)
            print('GST exculded')
            numerator = M + A + C
            denominator = (1 / (1 + gp_decimal)) - B_rate
            
        # 4. Safe calculation (prevent division by zero just in case)
        print("Numerator : " + str(numerator))
        print("Denominator : ", str(denominator))
        if denominator != 0:
            s_value = numerator / denominator
        else:
            s_value = 0.0
            
        m_ceiling_list.append(round(s_value, 2))

    # --- STEP 6: ATTACH NEW COLUMNS BACK TO THE DATAFRAME ---
    output_df = items_df.copy()
    output_df["Bucket A (₹)"] = bucket_a_list
    output_df["Bucket B (%)"] = [f"{rate * 100:.2f}%" for rate in bucket_b_rate_list]
    output_df["Bucket B Amount (₹)"] = bucket_b_amount_list 
    output_df["Bucket C (₹)"] = bucket_c_list
    output_df["Total Cost (A+B+C)"] = output_df["Bucket A (₹)"] + output_df["Bucket B Amount (₹)"] + output_df["Bucket C (₹)"]
    
    # Attach the final calculated margin
    output_df["M_ceiling (₹)"] = m_ceiling_list
    
    print(output_df[["item_code", "Bucket A (₹)", "Bucket C (₹)", "Total Cost (A+B+C)", "M_ceiling (₹)"]].head())
    print("Completed mapping of item charges and calculated target selling price (S).")

    return output_df