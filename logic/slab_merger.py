import pandas as pd
from config import NONE_CATEGORY, NONE_SELECTION, INCLUDED
import re

def build_merged_grid(
    slabs_df: pd.DataFrame,
    target_categories: list[str],
    item_tax_template: str,
    gst_status: str,
    product_gst_status: str
) -> pd.DataFrame:

    if slabs_df.empty:
        return pd.DataFrame()
        
    # 1. Clean and normalize the list of categories to filter against
    # Always ensure 'All' is in the list for flat fees
    allowed_categories = ["All"]
    
    if isinstance(target_categories, list):
        for cat in target_categories:
            if cat not in ["All", NONE_SELECTION, NONE_CATEGORY] and pd.notna(cat):
                allowed_categories.append(cat)
                
    # 2. Filter slabs_df upfront to contain ONLY the relevant categories
    filtered_df = slabs_df[slabs_df["category"].isin(allowed_categories)]
    
    if filtered_df.empty:
        return pd.DataFrame()

    # 3. COMPACT TIMELINE: Extract distinct boundary numbers across ALL allowed categories combined
    all_numbers = (
        pd.concat([filtered_df["lower_slab"], filtered_df["higher_slab"]])
        .drop_duplicates()
        .sort_values()
    )
    sorted_values = all_numbers.tolist()

    slabs = []
    
    # 4. Iterate through consecutive pairs of the unified timeline
    cost_lower_slab  = 0 
    for i in range(1, len(sorted_values)):
        low = sorted_values[i-1]
        high = sorted_values[i]
        
        # 5. Fetch rules covering this precise interval across any of our allowed categories
        matches = filtered_df[
            (filtered_df["lower_slab"] <= low) & 
            (filtered_df["higher_slab"] >= high)
        ]
        
        if matches.empty:
            continue
            
        # 6. Group by bucket across categories to sum rates matching this interval
        bucket_sums = matches.groupby("bucket")["price_list_rate"].sum()
        
        a_price = bucket_sums.get("A", 0.0)
        b_rate  = bucket_sums.get("B", 0.0)  # Safe isolated percentage rate (e.g., 0.09)
        c_price = bucket_sums.get("C", 0.0)
        
        # 7. Calculate row total as addition of flat fees A and C only
        total_flat_price = a_price + c_price

        # Calculate the variable amount by applying the percentage (b_rate) to 'high'
        b_amount = high * b_rate

        # Add the calculated percentage amount to the total fixed cost
        total_flat_price = total_flat_price + b_amount

        # --- GST EXTRACTION AND CALCULATION ---
        # Grab the first non-null tax template in this interval (default to "0" if missing)
        valid_taxes = matches["item_tax_template"].dropna()
        tax_string = str(valid_taxes.iloc[0]) if not valid_taxes.empty else "0"
        
        # Use regex to find the first sequence of digits in the string (e.g., "18" from "18 GST")
        gst_match = re.search(r'\d+', tax_string)
        gst_percentage = float(gst_match.group()) if gst_match else 0.0
        
        gst_amount = 0.0
        
        # Apply the GST logic based on the sidebar filter selection
        if gst_status == INCLUDED:
            gst_amount = total_flat_price * (gst_percentage / 100.0)
            total_flat_price = total_flat_price + gst_amount
        
        # 8. Apply the cost deduction logic
        cost_higher_slab = high - total_flat_price
        

        slabs.append({
            "lower_slab": low,
            "higher_slab": high,
            "cost_lower_slab": cost_lower_slab,
            "cost_higher_slab": cost_higher_slab,
            "a": a_price,
            "b": b_rate,
            "b_amount": b_amount,
            "c": c_price,
            "gst_percentage": gst_percentage,
            "gst_amount": gst_amount,
            "total": total_flat_price
        })

        cost_lower_slab  = cost_higher_slab



    print(f"Constructed unified merged grid with {len(slabs)} structured rows.")
    return pd.DataFrame(slabs)