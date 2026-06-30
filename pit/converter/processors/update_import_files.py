import pandas as pd



def normalize_exposures_by_group(df, value_col, flag = 'factors'):
    """
    Normalize values within each group to sum to 1.0.
    
    Args:
        df (pd.DataFrame): DataFrame containing the data
        group_col (str): Column name to group by (e.g., 'Name', 'Issuer')
        value_col (str): Column name containing values to normalize
    
    Returns:
        pd.DataFrame: DataFrame with normalized values
    """
    df = df.copy()

    # To check whether a row's value in a column is negative (for example, in column 'value_col'):
    # You can use a boolean condition like: row[value_col] < 0
    # For use with DataFrames, example for a whole column:
    negative_mask = df[value_col] < 0
    # Which gives a Boolean Series that's True for negative values.
    if negative_mask.any():
        raise ValueError(f"Error: Negative values found in {value_col} (flag: {flag} cannot be negative). Stopping execution.")

    
    # Group by the specified column and normalize values
    if flag == 'factors': # sum must be 1.0
        def _normalize_factors(group):
            total = group[value_col].sum()
            if total <= 0:
                raise ValueError(
                    f"Error: Non-positive total for {value_col} in Name={group['Name'].iloc[0]} "
                    f"(flag: {flag}). Stopping execution."
                )

            normalized = group[value_col] / total
            if len(normalized) > 0:
                normalized.iloc[-1] = 1.0 - normalized.iloc[:-1].sum()

            out = group.copy()
            out[value_col] = normalized
            return out

        df = (
            df.groupby('Name', group_keys=False)
            .apply(_normalize_factors)
            .reset_index(drop=True)
        )
    elif flag == 'principal' or flag == 'coupon': # sum must be less than or equal to 1.0
        df[value_col] = (
            df.groupby('Name')[value_col]
            .transform(lambda x: x / x.sum() if x.sum() > 1 else x)
        )
    
    return df


## validate PD term structure: this function is updated for 2025Q2.
def validate_issuer_pd(df, name_col='Name', years_col='Years', pd_col='PD'):
    """
    Validate and adjust PD values to ensure monotonically increasing cumulative PD by issuer.
    
    Args:
        df (pd.DataFrame): DataFrame with PD term structure data
        name_col (str): Column name for instrument/issuer identifier (default: 'Name')
        years_col (str): Column name for years/term (default: 'Years')
        pd_col (str): Column name for PD values (default: 'PD')
    
    Returns:
        pd.DataFrame: DataFrame with validated PD values
    """
    if df.empty:
        print("Warning: Empty DataFrame passed to validate_issuer_pd")
        return df
    
    # Verify required columns exist
    required_cols = [name_col, years_col, pd_col]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"Warning: Missing columns in validate_issuer_pd: {missing_cols}")
        return df
    
    df_result = df.copy()
    adjustment_count = 0
    
    # Sort the entire dataframe by name and years for processing
    df_result = df_result.sort_values([name_col, years_col]).reset_index(drop=True)
    
    print(f"Validating PD term structure monotonicity for {df_result[name_col].nunique()} instruments...")
    
    # Process each issuer group
    current_name = None
    first_row_of_issuer = True

    adjust_year = False
    
    for idx in range(len(df_result)):
        name = df_result.iloc[idx][name_col]
        years = df_result.iloc[idx][years_col]
        pd_val = df_result.iloc[idx][pd_col]

        if years < 0.25:
            adjust_year = True
        
        # Skip invalid data
        if pd.isna(years) or pd.isna(pd_val) or years <= 0:
            continue
        
        # Check if we're starting a new issuer
        if current_name != name:
            current_name = name
            first_row_of_issuer = True
        
        # 1) Implied CPD: 1 - (1 - pd)^years
        implied_cpd = 1 - (1 - pd_val) ** years
        
        # 2) Min CPD calculation
        if first_row_of_issuer:
            implied_cpd = min(1-1e-7, implied_cpd)
            prev_implied_cpd = implied_cpd
            prev_min_cpd = implied_cpd
            
            min_cpd = implied_cpd
            max_cpd = implied_cpd

            first_row_of_issuer = False
        else:
            epsilon = min(1e-7, (1.0 - prev_implied_cpd) / 2)
            min_cpd = max(prev_implied_cpd + epsilon, prev_min_cpd)
            max_cpd = max(min_cpd, 1-1e-9)
        
        # 3) Flag: check if adjustment needed
        if min_cpd > implied_cpd:
            flag = 0
        elif max_cpd < implied_cpd:
            flag = 1
        else:
            flag = 2
        
        # 4) New CPD
        if flag == 2:
            new_cpd = implied_cpd
        elif flag == 0:
            new_cpd = min_cpd
        else:
            new_cpd = max_cpd
        
        # 5) Final PD: convert back to annualized PD
        ## this is for RICS, if acculumated PD > 1 ((acculumated PD - 1) >10^(-6) , then RICS will not accept the data.
        final_pd = 1 - (1 - new_cpd) ** (1 / years)

        # 6) Update the dataframe if adjustment was made
        original_pd = pd_val
        if abs(final_pd - original_pd) > 1e-8:
            adjustment_count += 1
            if adjustment_count <= 10:  # Log first 10 adjustments
                print(f"  PD adjusted for {name} at {years:.2f} years: "
                      f"{original_pd:.6f} -> {final_pd:.6f}")
            elif adjustment_count == 11:
                print("  ... (additional adjustments not shown)")
        
        df_result.iloc[idx, df_result.columns.get_loc(pd_col)] = final_pd
        
        if adjust_year:
            df_result.iloc[idx, df_result.columns.get_loc(years_col)] = 0.25
            adjust_year = False
        
        # Update previous values for next iteration
        prev_implied_cpd = implied_cpd
        prev_min_cpd = min_cpd
    
    if adjustment_count > 0:
        print(f"Total PD adjustments made: {adjustment_count}")
    else:
        print("No PD adjustments needed - all term structures are monotonic")
    
    return df_result





