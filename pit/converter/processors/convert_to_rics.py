import pandas as pd
import numpy as np
import os




def read_mapping_files(data_path): 
    """
    Reads the following mapping files from the specified folder:
    - GCorr_Factor_Mappings.xlsx
    """
    result = pd.DataFrame()
    Gcorr_Factor_Mappings_csv_path = os.path.join(data_path, f"GCorr_Factors_Mapping.csv")
    if os.path.exists(Gcorr_Factor_Mappings_csv_path):
        try:
            result= pd.read_csv(Gcorr_Factor_Mappings_csv_path)
        except Exception as e:
            print(f"Error reading {Gcorr_Factor_Mappings_csv_path}: {e}")
    else:
        print(f"File not found: {Gcorr_Factor_Mappings_csv_path}")

    return result


def map_country_code(row, column_name, gcorr_mapping):

    factor_code = row.get(column_name, None)
    if pd.isnull(factor_code):
        return np.nan
    match = gcorr_mapping[gcorr_mapping['description'].str.contains(str(factor_code), na=False)]

    return match.iloc[0]['factorcode'] if not match.empty else np.nan

def map_factor_code(row, column_name, gcorr_mapping):

    factor_code = row.get(column_name, None)
    if pd.isnull(factor_code):
        return np.nan
    match = gcorr_mapping[gcorr_mapping['description'] == str(factor_code)]

    return match.iloc[0]['factorcode'] if not match.empty else np.nan


def rics_version_gte(version_str, target):
    """
    Compare RICS version strings (e.g. "10.5", "10.6").
    Returns True if version_str >= target.
    """
    if version_str is None or (isinstance(version_str, str) and not version_str.strip()):
        return False
    try:
        parts = str(version_str).strip().split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        t_parts = str(target).strip().split(".")
        t_major = int(t_parts[0]) if len(t_parts) > 0 else 0
        t_minor = int(t_parts[1]) if len(t_parts) > 1 else 0
        return (major, minor) >= (t_major, t_minor)
    except (ValueError, IndexError):
        return False


def apply_rics_version_format_filter(rics_import_format, rics_version):
    """
    For RICS_version <= 10.5, remove RBCFactors from ChildBond, ChildFRN,
    ChildAmortisingBond, ChildAmortisingFRN column lists. Otherwise return a copy unchanged.
    """
    CHILD_TABLES_WITH_RBC = ("ChildBond", "ChildFRN", "ChildAmortisingBond", "ChildAmortisingFRN")
    out = {k: list(v) for k, v in rics_import_format.items()}
    if not rics_version_gte(rics_version, "10.6"):
        for key in CHILD_TABLES_WITH_RBC:
            if key in out and "RBCFactors" in out[key]:
                out[key] = [c for c in out[key] if c != "RBCFactors"]
    return out


def read_rics_import_format(csv_path):
    """
    Reads the RICS_ImportFiles_Format.csv and returns a dictionary:
    {file_name: [column_names]}
    where column_names is a list of non-NaN column names for that file.
    """
    df = pd.read_csv(csv_path, dtype=str)
    result = {}
    for idx, row in df.iterrows():
        file_name = row.iloc[0]
        # Get all column names from the second column onward, drop NaN and empty strings
        column_names = [str(col).strip() for col in row.iloc[1:] if pd.notnull(col) and str(col).strip() != ""]
        result[file_name] = column_names
    return result

def create_dataframe_from_columns(file_name, import_format, data):
    """
    Create a DataFrame for the given file_name using column names from import_format,
    and populate it with rows if provided.

    Args:
        file_name (str): The name of the file (key in import_format).
        import_format (dict): Dictionary mapping file names to lists of column names.
        rows (list of lists, optional): List of row values (each row is a list).

    Returns:
        pd.DataFrame: The constructed DataFrame.
    """
    columns = import_format[file_name]
    df = pd.DataFrame(columns=columns)
    for col in columns:
        if col in data.columns:
            df[col] = data[col]

    return df

def process_counterparty(df, gcorr_mapping, Model_Assumptions):
    """
    Args:
        df (pd.DataFrame): Counterparty DataFrame.
        gcorr_mapping (pd.DataFrame): Mapping DataFrame for country codes.

    Returns:
        pd.DataFrame: Processed and enriched DataFrame.
    """

    df['Name'] = df['counterpartyName']
    # Map country code
    df['CountryCode'] = df.apply(map_country_code, column_name='counterpartyCountryCode', axis=1, gcorr_mapping=gcorr_mapping)

    df.rename(columns={'rsquared': 'RSQ'}, inplace=True)


    # SAV data does not have CreditClass column; use ImpliedCreditClass=TRUE and CreditClass='';
    df['ImpliedCreditClass'] = True
    df['CreditClass'] = ''

    # Add TransitionMatrix, Z_ScoreModel, and MPRModel columns
    df['TransitionMatrix'] = Model_Assumptions['transition_matrix']
    df['Z-ScoreModel'] = Model_Assumptions['z_score_model']
    df['MPRModel'] = Model_Assumptions['mpr_model']

    return df

def process_agency_counterparty(df, Model_Assumptions):
    """
    Args:
        df (pd.DataFrame): Counterparty DataFrame.
        Model_Assumptions (dict): Model assumptions.
    """

    df['Name'] = df['counterpartyName']
    # Map country code
    df['CountryCode'] = Model_Assumptions['CountryCode']
    df['RSQ'] = Model_Assumptions['RSQ']

    df['CreditClass'] = Model_Assumptions['CreditClass']

    df['TransitionMatrix'] = Model_Assumptions['transition_matrix']
    df['Z-ScoreModel'] = Model_Assumptions['z_score_model']
    df['MPRModel'] = Model_Assumptions['mpr_model']

    return df

def validate_parameter_set_index(df, code_column, data_type):
    """Helper function to validate ParameterSetIndex consistency"""
    for name, group in df.groupby('Name'):
        n_unique_codes = group[code_column].nunique()
        max_param_idx = group['ParameterSetIndex'].max()
        if n_unique_codes != max_param_idx:
            print(f"Warning: For {code_column} '{name}' in {data_type}, max ParameterSetIndex ({max_param_idx}) does not equal number of unique {code_column} ({n_unique_codes})")

def process_factor_subset(df, code_column, data_type):
    """Helper function to process factor subsets"""
    df_subset = df.dropna(subset=[code_column]).copy()
    if df_subset.empty:
        return pd.DataFrame()
    df_subset['ParameterSetIndex'] = df_subset.groupby('Name').cumcount() + 1
    validate_parameter_set_index(df_subset, code_column, data_type)
    return df_subset

def merge_and_dedupe(df1_subset, df2, on_column, how='left'):
    """Helper function for merge and drop_duplicates pattern"""
    merged = pd.merge(df1_subset, df2, on=on_column, how=how)
    merged.drop_duplicates(inplace=True)
    return merged


# average industry factor loadings
def process_agency_factor_loadings(df):
    """Helper function to process agency factor loadings"""
    # For each Name, create a new DataFrame with ParameterSetIndex from 1 to 61, IndustryCode N01 to N61, and Exposure = 1/61
    unique_names = df['Name'].unique()
    industry_codes = [f'N{str(i).zfill(2)}' for i in range(1, 62)]
    exposure_value = 1.0 / 61

    rows = []
    for name in unique_names:
        for idx, code in enumerate(industry_codes, start=1):
            rows.append({
                'Name': name,
                'ParameterSetIndex': idx,
                'IndustryCode': code,
                'Exposure': exposure_value
            })
    df_out = {'IndustryFactorLoadingsParameterSet': pd.DataFrame(rows)}
    validate_parameter_set_index(df_out['IndustryFactorLoadingsParameterSet'], 'IndustryCode', 'AGENCY')
    return df_out




def process_factor_loadings(df, gcorr_mapping, data_type):
    
    df['Factors'] = df.apply(map_factor_code, column_name='factorName', axis=1, gcorr_mapping=gcorr_mapping)
    df = df.rename(columns={'factorCoefficient': 'Exposure'})

    df_factor_loadings = {}
    if 'CLO' in data_type:
        df['IndustryCode'] = np.where(df['Factors'].str.contains('N', case=False, na=False), df['Factors'], np.nan)

        df_factor_loadings[f'IndustryFactorLoadingsParameterSet'] = process_factor_subset(df, 'IndustryCode', data_type)

    elif 'ABS' in data_type or 'RMBS' in data_type:
        df['RegionCode'] = np.where(df['Factors'].str.contains('RETGU', case=False, na=False), df['Factors'], np.nan)
        df['ProductTypeCode'] = np.where(df['Factors'].str.contains('RETPU', case=False, na=False), df['Factors'], np.nan)

        df_factor_loadings[f'RegionLoadingsParameterSet'] = process_factor_subset(df, 'RegionCode', data_type) 
        df_factor_loadings[f'ProductTypeLoadingsParameterSet'] = process_factor_subset(df, 'ProductTypeCode', data_type) 
   
    elif 'CMBS' in data_type:
        df['GeographyCode'] = np.where(df['Factors'].str.contains('CREG', case=False, na=False), df['Factors'], np.nan)
        df['PropertyTypeCode'] = np.where(df['Factors'].str.contains('CREP', case=False, na=False), df['Factors'], np.nan)

        df_factor_loadings[f'GeographyLoadingsParameterSet'] = process_factor_subset(df, 'GeographyCode', data_type)
        df_factor_loadings[f'PropertyTypeLoadingsParameterSet'] = process_factor_subset(df, 'PropertyTypeCode', data_type)  
 
    return df_factor_loadings


## PD term structure validation: check accumulated PD is strictly increasing. The inputs are annulized PD. 
## accumulated PD = 1-(1-annulized PD)^Years
def process_pd_term_structure(df):

    df = df.rename(columns={'term': 'Years', 'pd': 'PD'})
    df['ParameterSetIndex'] = df.groupby('Name').cumcount() + 1 

    return df

def process_date_to_years(df, column_name, start_date):
    """Helper function to process date to years"""
    
    # Check if dates are the same as start_date
    is_same_date = ((df[column_name].dt.year == start_date.year) & 
                    (df[column_name].dt.month == start_date.month) & 
                    (df[column_name].dt.day == start_date.day))
    
    # Calculate end-of-month flag
    is_eom = df[column_name].dt.is_month_end 
    # Calculate month difference
    month_diff = (df[column_name].dt.year - start_date.year) * 12 + (df[column_name].dt.month - start_date.month)
    month_diff = month_diff - (~is_eom)
    
    # Set month_diff to 0 for dates that are the same as start_date
    month_diff = month_diff.where(~is_same_date, 0)
    
    return (month_diff + 1) / 12


def process_TermLoanBond_data(df, start_date, Model_Assumptions, coupon_frequencies, Floating_Reference_Yield_Curves, rics_version="10.6"):

    df_bullet_data = {
        'ChildBond': pd.DataFrame(),
        'LGDMeanTermStructureParameterSet': pd.DataFrame(),
        'LGDKTermStructureParameterSet': pd.DataFrame()
    }
    df_frn_data = {
        'ChildFRN': pd.DataFrame(),
        'LGDMeanTermStructureParameterSet': pd.DataFrame(),
        'LGDKTermStructureParameterSet': pd.DataFrame()
    }


    # Convert maturityDate to datetime if not already, and format to %m/%d/%Y (US format)
    if not pd.api.types.is_datetime64_any_dtype(df['maturityDate']):
        df['maturityDate'] = pd.to_datetime(
            df['maturityDate'], errors='coerce', format='%m/%d/%Y'
        ) 

    df = df.rename(columns={'Name': 'Name_Issuer','instrumentCurrency': 'Economy','maturityDate': 'MaturityDate'})

    df['Name'] = df['Name_Issuer'] + '.' + df['instrumentId']

    bullet_cols = ['Name','Economy','MaturityDate','fixedRate','fixedRateInterestFreq','lgd','lgdVarianceParam']
    frn_cols = ['Name','Economy','MaturityDate','referenceYieldCurve','drawnSpread','drawnSpreadFreq','lgd','lgdVarianceParam']
    if 'RBCFactors' in df.columns:
        bullet_cols = bullet_cols + ['RBCFactors']
        frn_cols = frn_cols + ['RBCFactors']
    df_bullet = df.loc[df['interestTypeName'] == 'FIXED', bullet_cols]
    df_frn = df.loc[df['interestTypeName'] == 'FLOATING', frn_cols]

    if not df_bullet.empty:
        df_bullet['Type'] = 'Bond'
        df_bullet['BondType'] = Model_Assumptions['BondType']
        df_bullet['InflationModel'] = Model_Assumptions['InflationModel']
        df_bullet['ParCoupon'] = Model_Assumptions['ParCoupon']
        df_bullet['DeterministicLGD'] = Model_Assumptions['DeterministicLGD']
        df_bullet['CouponFrequency'] = df_bullet['fixedRateInterestFreq'].map(coupon_frequencies)
        df_bullet['PricingCurve'] = df_bullet['Economy']+'.'+'NominalYieldCurves.NominalYieldCurve'

        df_bullet['Years'] = process_date_to_years(df_bullet, 'MaturityDate', start_date)

        df_bullet.rename(columns={'fixedRate': 'Coupon','lgd': 'LGD','lgdVarianceParam': 'K'}, inplace=True)
        df_bullet['ParameterSetIndex'] = df_bullet.groupby('Name').cumcount() + 1

        child_bond_cols = ['Name','Economy','BondType','PricingCurve','InflationModel','MaturityDate','ParCoupon','Coupon','CouponFrequency','DeterministicLGD','Type']
        if rics_version_gte(rics_version, "10.6"):
            if 'RBCFactors' not in df_bullet.columns:
                df_bullet['RBCFactors'] = ''
            child_bond_cols = child_bond_cols + ['RBCFactors']
        df_bullet_data['ChildBond'] = df_bullet[child_bond_cols].drop_duplicates()
        
        df_bullet_data['LGDMeanTermStructureParameterSet'] = df_bullet[['Name','ParameterSetIndex','Years','LGD']].drop_duplicates()
        df_bullet_data['LGDKTermStructureParameterSet'] = df_bullet[['Name','ParameterSetIndex','Years','K']].drop_duplicates()

    else:
        df_bullet_data['ChildBond'] = pd.DataFrame()
        df_bullet_data['LGDMeanTermStructureParameterSet'] = pd.DataFrame()
        df_bullet_data['LGDKTermStructureParameterSet'] = pd.DataFrame()
        
    
    if not df_frn.empty:
        df_frn['Type'] = 'FRN'
        df_frn['LastResetRate'] = Model_Assumptions['LastResetRate']
        df_frn['ParMargin'] = Model_Assumptions['ParMargin']
        df_frn['DeterministicLGD'] = Model_Assumptions['DeterministicLGD']
        df_frn['CouponFrequency'] = df_frn['drawnSpreadFreq'].map(coupon_frequencies)
        df_frn['PricingCurve'] = df_frn['Economy']+'.'+'NominalYieldCurves.NominalYieldCurve'
        df_frn['CouponCurve'] = df_frn['referenceYieldCurve'].map(Floating_Reference_Yield_Curves)

        df_frn['Years'] = process_date_to_years(df_frn, 'MaturityDate', start_date)
        
        df_frn.rename(columns={'drawnSpread': 'Margin','lgd': 'LGD','lgdVarianceParam': 'K'}, inplace=True)
        df_frn['ParameterSetIndex'] = df_frn.groupby('Name').cumcount() + 1

        child_frn_cols = ['Name','Economy','PricingCurve','CouponCurve','MaturityDate','LastResetRate','ParMargin','Margin','CouponFrequency','DeterministicLGD','Type']
        if rics_version_gte(rics_version, "10.6"):
            if 'RBCFactors' not in df_frn.columns:
                df_frn['RBCFactors'] = ''
            child_frn_cols = child_frn_cols + ['RBCFactors']
        df_frn_data['ChildFRN'] = df_frn[child_frn_cols].drop_duplicates()
        df_frn_data['LGDMeanTermStructureParameterSet'] = df_frn[['Name','ParameterSetIndex','Years','LGD']].drop_duplicates()
        df_frn_data['LGDKTermStructureParameterSet'] = df_frn[['Name','ParameterSetIndex','Years','K']].drop_duplicates()

    else:
        df_frn_data['ChildFRN'] = pd.DataFrame()
        df_frn_data['LGDMeanTermStructureParameterSet'] = pd.DataFrame()
        df_frn_data['LGDKTermStructureParameterSet'] = pd.DataFrame()

    return df_bullet_data, df_frn_data


def interpolate_lgd_lgdk(df_lgd, name_order):
    """
    Interpolates the given column ('LGD' or 'K') monthly over the range of 'Years' for each 'Name' in df_lgd.

    Args:
        df_lgd (pd.DataFrame): DataFrame with columns ['Name', 'Years', 'LGD', 'K'].
        col (str): The column to interpolate, either 'LGD' or 'K'.

    Returns:
        pd.DataFrame: DataFrame with columns ['Name', 'ParameterSetIndex', 'Years', col] interpolated monthly.
    """

    interpolated_rows = {}
    interpolated_rows['LGD'] = []
    interpolated_rows['K'] = []
    for name, group in df_lgd.groupby('Name'):
        # Drop duplicates and sort by Years
        group = group[['Years', 'LGD', 'K']].drop_duplicates().sort_values('Years')

        if group['Years'].count() < 2:
            interpolated_rows['LGD'].append({
                'Name': name,
                'ParameterSetIndex': 1,
                'Years': group['Years'].iloc[0],
                'LGD': group['LGD'].iloc[0]
            })
            interpolated_rows['K'].append({
                'Name': name,
                'ParameterSetIndex': 1,
                'Years': group['Years'].iloc[0],
                'K': group['K'].iloc[0]
            })
        else:
            years_min = group['Years'].min()
            years_max = group['Years'].max()

            monthly_years = np.arange(years_min, years_max + 1/12, 1/12)
            # Remove the values that are larger than years_max in monthly_years
            monthly_years = monthly_years[monthly_years <= years_max]

            interpolated_values = np.interp(monthly_years, group['Years'], group['LGD'])
            for idx, (y, val) in enumerate(zip(monthly_years, interpolated_values), 1):
                interpolated_rows['LGD'].append({
                    'Name': name,
                    'ParameterSetIndex': idx,
                    'Years': y,
                    'LGD': val
                })
            interpolated_values = np.interp(monthly_years, group['Years'], group['K'])
            for idx, (y, val) in enumerate(zip(monthly_years, interpolated_values), 1):
                interpolated_rows['K'].append({
                    'Name': name,
                    'ParameterSetIndex': idx,
                    'Years': y,
                    'K': val
                })

    LGD = pd.DataFrame(interpolated_rows['LGD']).drop_duplicates()
    LGDK = pd.DataFrame(interpolated_rows['K']).drop_duplicates()
    LGD['Name'] = pd.Categorical(LGD['Name'], categories=name_order, ordered=True)
    LGDK['Name'] = pd.Categorical(LGDK['Name'], categories=name_order, ordered=True)
    LGD = LGD.sort_values(['Name', 'ParameterSetIndex']).reset_index(drop=True)
    LGDK = LGDK.sort_values(['Name', 'ParameterSetIndex']).reset_index(drop=True)

    return LGD, LGDK



def process_TermLoanAmortizing_data(df, lgd_schedule_df, cashflow_schedule_df, start_date, Model_Assumptions, coupon_frequencies, Floating_Reference_Yield_Curves, rics_version="10.6"):

    df_bullet_data = {
        'ChildAmortisingBond': pd.DataFrame(),
        'LGDMeanTermStructureParameterSet': pd.DataFrame(),
        'LGDKTermStructureParameterSet': pd.DataFrame()
    }
    df_frn_data = {
        'ChildAmortisingFRN': pd.DataFrame(),
        'LGDMeanTermStructureParameterSet': pd.DataFrame(),
        'LGDKTermStructureParameterSet': pd.DataFrame()
    }

    df = df.rename(columns={'Name': 'Name_Issuer','instrumentCurrency': 'Economy'})
    df['Name'] = df['Name_Issuer'] + '.' + df['instrumentId']    

    amort_bullet_cols = ['Name','Economy','fixedRate','fixedRateInterestFreq','lgdScheduleName','instrumentId']
    amort_frn_cols = ['Name','Economy','referenceYieldCurve','drawnSpread','drawnSpreadFreq','lgdScheduleName','instrumentId']
    if 'RBCFactors' in df.columns:
        amort_bullet_cols = amort_bullet_cols + ['RBCFactors']
        amort_frn_cols = amort_frn_cols + ['RBCFactors']
    df_bullet = df.loc[df['interestTypeName'] == 'FIXED', amort_bullet_cols]
    df_frn = df.loc[df['interestTypeName'] == 'FLOATING', amort_frn_cols]

    if not pd.api.types.is_datetime64_any_dtype(cashflow_schedule_df['cashFlowDate']):
        cashflow_schedule_df['cashFlowDate'] = pd.to_datetime(
            cashflow_schedule_df['cashFlowDate'], errors='coerce', format='%m/%d/%Y'
        ) 

    if not pd.api.types.is_datetime64_any_dtype(lgd_schedule_df['lgdDate']):
        lgd_schedule_df['lgdDate'] = pd.to_datetime(
            lgd_schedule_df['lgdDate'], errors='coerce', format='%m/%d/%Y'
        ) 

    if not df_bullet.empty:
        df_bullet['Type'] = 'AmortisingBond'
        df_bullet['CouponDefinition'] = Model_Assumptions['CouponDefinition']
        df_bullet['ParCoupon'] = Model_Assumptions['ParCoupon']
        df_bullet['DeterministicLGD'] = Model_Assumptions['DeterministicLGD']
        df_bullet['CouponFrequency'] = df_bullet['fixedRateInterestFreq'].map(coupon_frequencies)
        df_bullet['PricingCurve'] = df_bullet['Economy']+'.'+'NominalYieldCurves.NominalYieldCurve'
        df_bullet.rename(columns={'fixedRate': 'Coupon'}, inplace=True)

        child_amort_bond_cols = ['Name','Economy','PricingCurve','CouponDefinition','ParCoupon','Coupon','CouponFrequency','DeterministicLGD','Type']
        if rics_version_gte(rics_version, "10.6"):
            if 'RBCFactors' not in df_bullet.columns:
                df_bullet['RBCFactors'] = ''
            child_amort_bond_cols = child_amort_bond_cols + ['RBCFactors']
        df_bullet_data['ChildAmortisingBond'] = df_bullet[child_amort_bond_cols].drop_duplicates()

        # create LGD/LGDK schedule by monthly, interpolate missing values
        df_lgd_bullet = pd.merge(df_bullet[['Name','lgdScheduleName']], lgd_schedule_df, on='lgdScheduleName', how='left')

        df_lgd_bullet['Years'] = process_date_to_years(df_lgd_bullet, 'lgdDate', start_date)
        df_lgd_bullet.rename(columns={'lgd': 'LGD','lgdVarianceParam': 'K'}, inplace=True)

        name_order = df_bullet_data['ChildAmortisingBond']['Name'].tolist()
        df_bullet_data['LGDMeanTermStructureParameterSet'], df_bullet_data['LGDKTermStructureParameterSet'] = interpolate_lgd_lgdk(df_lgd_bullet, name_order)


        df_cashflow_bullet = pd.merge(df_bullet[['Name','instrumentId']], cashflow_schedule_df, on='instrumentId', how='left')

        df_cashflow_bullet.rename(columns={'cashFlowDate': 'Date','principalReceive': 'PaymentAmount'}, inplace=True)
        df_cashflow_bullet['ParameterSetIndex'] = df_cashflow_bullet.groupby('Name').cumcount() + 1

        df_bullet_data['PrincipalPaymentScheduleParameterSet'] = df_cashflow_bullet[['Name','ParameterSetIndex','Date','PaymentAmount']].drop_duplicates()

        df_bullet_data['CouponPaymentScheduleParameterSet'] = pd.DataFrame(columns=['Name','ParameterSetIndex','Date','PaymentAmount'])

    else:
        df_bullet_data['ChildAmortisingBond'] = pd.DataFrame()
        df_bullet_data['LGDMeanTermStructureParameterSet'] = pd.DataFrame()
        df_bullet_data['LGDKTermStructureParameterSet'] = pd.DataFrame()
        df_bullet_data['PrincipalPaymentScheduleParameterSet'] = pd.DataFrame()
        df_bullet_data['CouponPaymentScheduleParameterSet'] = pd.DataFrame()
        
    
    if not df_frn.empty:
        df_frn['Type'] = 'AmortisingFRN'
        df_frn['LastResetRate'] = Model_Assumptions['LastResetRate']
        df_frn['ParMargin'] = Model_Assumptions['ParMargin']
        df_frn['DeterministicLGD'] = Model_Assumptions['DeterministicLGD']
        df_frn['CouponFrequency'] = df_frn['drawnSpreadFreq'].map(coupon_frequencies)
        df_frn['PricingCurve'] = df_frn['Economy']+'.'+'NominalYieldCurves.NominalYieldCurve'
        df_frn['CouponCurve'] = df_frn['referenceYieldCurve'].map(Floating_Reference_Yield_Curves)
        df_frn.rename(columns={'drawnSpread': 'Margin'}, inplace=True)

        child_amort_frn_cols = ['Name','Economy','PricingCurve','CouponCurve','LastResetRate','ParMargin','Margin','CouponFrequency','DeterministicLGD','Type']
        if rics_version_gte(rics_version, "10.6"):
            if 'RBCFactors' not in df_frn.columns:
                df_frn['RBCFactors'] = ''
            child_amort_frn_cols = child_amort_frn_cols + ['RBCFactors']
        df_frn_data['ChildAmortisingFRN'] = df_frn[child_amort_frn_cols].drop_duplicates()

       # create LGD/LGDK schedule by monthly, interpolate missing values
        df_lgd_frn = pd.merge(df_frn[['Name','lgdScheduleName']], lgd_schedule_df, on='lgdScheduleName', how='left')

        df_lgd_frn['Years'] = process_date_to_years(df_lgd_frn, 'lgdDate', start_date)
        df_lgd_frn.rename(columns={'lgd': 'LGD','lgdVarianceParam': 'K'}, inplace=True)

        name_order = df_frn_data['ChildAmortisingFRN']['Name'].tolist()
        df_frn_data['LGDMeanTermStructureParameterSet'], df_frn_data['LGDKTermStructureParameterSet'] = interpolate_lgd_lgdk(df_lgd_frn, name_order)

        df_cashflow_frn = pd.merge(df_frn[['Name','instrumentId']], cashflow_schedule_df, on='instrumentId', how='left')

        df_cashflow_frn.rename(columns={'cashFlowDate': 'Date','principalReceive': 'PaymentAmount'}, inplace=True)
        df_cashflow_frn['ParameterSetIndex'] = df_cashflow_frn.groupby('Name').cumcount() + 1

        df_frn_data['PrincipalPaymentScheduleParameterSet'] = df_cashflow_frn[['Name','ParameterSetIndex','Date','PaymentAmount']].drop_duplicates()
 
    else:
        df_frn_data['ChildAmortisingFRN'] = pd.DataFrame()
        df_frn_data['LGDMeanTermStructureParameterSet'] = pd.DataFrame()
        df_frn_data['LGDKTermStructureParameterSet'] = pd.DataFrame()
        df_frn_data['PrincipalPaymentScheduleParameterSet'] = pd.DataFrame()


    return df_bullet_data, df_frn_data
    

def process_rics_output_files(pdts_flag, pdts_df, combined_data, gcorr_mapping, data_type, Model_Assumptions, coupon_frequencies, Floating_Reference_Yield_Curves, Start_Date, data_path, RICS_version="10.6"):

    # Convert Start_Date string to datetime for start_date, using format '%m%d%Y'
    start_date = pd.to_datetime(Start_Date, format='%Y%m%d')

    name_order = pdts_df['Name'].unique().tolist()

    rics_import_format = read_rics_import_format(os.path.join(data_path, "RICS_ImportFiles_Format.csv"))
    rics_import_format = apply_rics_version_format_filter(rics_import_format, RICS_version)

    risc_output_dfs = {}
    pdts_flag_str = '_PDTS' if pdts_flag else ''

    # counterparty
    print('----Counterparty----')
    if 'CLO' in data_type or 'AGENCY' in data_type:
        risc_output_dfs[f'GCP{pdts_flag_str}'] = create_dataframe_from_columns(f"GCP{pdts_flag_str}_{'CLO'}", rics_import_format, pdts_df)
    else:
        risc_output_dfs[f'GCP{pdts_flag_str}'] = create_dataframe_from_columns(f"GCP{pdts_flag_str}", rics_import_format, pdts_df)


    # factor loadings
    # agency does not have factor loadings
    if not 'AGENCY' in data_type:
        print('----Factor Loadings----')
        df_factors = merge_and_dedupe(pdts_df[['counterpartyId','Name']], combined_data['covarianceModelFactorCoefficients'], 'counterpartyId')
        df_factor_loadings = process_factor_loadings(df_factors, gcorr_mapping, data_type)
    else:
        print('----Agency Factor Loadings (average industry factor loadings)----')
        df_factor_loadings = process_agency_factor_loadings(pdts_df)

    for factor_loading, factor_loading_data in df_factor_loadings.items():
        factor_loading_data['Name'] = pd.Categorical(factor_loading_data['Name'], categories=name_order, ordered=True)
        factor_loading_data = factor_loading_data.sort_values(['Name', 'ParameterSetIndex']).reset_index(drop=True)
            
        risc_output_dfs[f"GCP{pdts_flag_str}_{factor_loading}"] = create_dataframe_from_columns(f"{factor_loading}", rics_import_format, factor_loading_data)
    
    
    if pdts_flag:
        # pd term structure
        print('----PD Term Structure----')
        df_pds = merge_and_dedupe(pdts_df[['instrumentId','Name']], combined_data['instrumentPdsFlexible'], 'instrumentId')
        df_pd_term_structure = process_pd_term_structure(df_pds)

        df_pd_term_structure ['Name'] = pd.Categorical(df_pd_term_structure ['Name'], categories=name_order, ordered=True)
        df_pd_term_structure  = df_pd_term_structure .sort_values(['Name', 'ParameterSetIndex']).reset_index(drop=True)

        risc_output_dfs[f"GCP{pdts_flag_str}_PDTermStructureParameterSet"] = create_dataframe_from_columns(f"PDTermStructureParameterSet", rics_import_format, df_pd_term_structure)

    # bond data
    df_bondType = pd.DataFrame()
    if not combined_data['termLoanBullet'].empty:
        print('----TermLoanBullet----')
        df_bonds = merge_and_dedupe(pdts_df[['instrumentId','Name']], combined_data['termLoanBullet'], 'instrumentId')
        df_bond_data, df_frn_data = process_TermLoanBond_data(df_bonds, start_date, Model_Assumptions, coupon_frequencies, Floating_Reference_Yield_Curves, RICS_version)
        
        for bond_type, bond_data in df_bond_data.items():
            #if not bond_data.empty:
            if hasattr(bond_data, 'columns') and not bond_data.empty:
                print('----BulletFixed----', bond_type)
                if bond_type == 'ChildBond':
                    df_bondType = pd.concat([df_bondType, bond_data])
                    risc_output_dfs[f"GCP{pdts_flag_str}_{bond_type}"] = create_dataframe_from_columns(f"{bond_type}", rics_import_format, bond_data)
                else:
                    risc_output_dfs[f"GCP{pdts_flag_str}_ChildBond_{bond_type}"] = create_dataframe_from_columns(f"{bond_type}", rics_import_format, bond_data)
        
        for bond_type, bond_data in df_frn_data.items():
            #if not bond_data.empty:
            if hasattr(bond_data, 'columns') and not bond_data.empty:
                print('----BulletFRN----', bond_type)
                if bond_type == 'ChildFRN':
                    df_bondType = pd.concat([df_bondType, bond_data])
                    risc_output_dfs[f"GCP{pdts_flag_str}_{bond_type}"] = create_dataframe_from_columns(f"{bond_type}", rics_import_format, bond_data)
                else:
                    risc_output_dfs[f"GCP{pdts_flag_str}_ChildFRN_{bond_type}"] = create_dataframe_from_columns(f"{bond_type}", rics_import_format, bond_data)

        
    if not combined_data['termLoanAmortizing'].empty:
        print('----TermLoanAmortizing----')
        df_bonds = merge_and_dedupe(pdts_df[['instrumentId','Name']], combined_data['termLoanAmortizing'], 'instrumentId')
        
        df_bond_data, df_frn_data = process_TermLoanAmortizing_data(df_bonds, combined_data['lgdSchedule'], combined_data['cashflow'], start_date, Model_Assumptions, coupon_frequencies, Floating_Reference_Yield_Curves, RICS_version)

        for bond_type, bond_data in df_bond_data.items():
            if hasattr(bond_data, 'columns') and not bond_data.empty:
                print('----AmortisingBond----', bond_type)
                if bond_type == 'ChildAmortisingBond':
                    df_bondType = pd.concat([df_bondType, bond_data])
                    risc_output_dfs[f"GCP{pdts_flag_str}_{bond_type}"] = create_dataframe_from_columns(f"{bond_type}", rics_import_format, bond_data)
                else:
                    risc_output_dfs[f"GCP{pdts_flag_str}_ChildAmortisingBond_{bond_type}"] = create_dataframe_from_columns(f"{bond_type}", rics_import_format, bond_data)
            if "CouponPaymentScheduleParameterSet" in bond_type:
                risc_output_dfs[f"GCP{pdts_flag_str}_ChildAmortisingBond_{bond_type}"] = create_dataframe_from_columns(f"{bond_type}", rics_import_format, bond_data)

        for bond_type, bond_data in df_frn_data.items():
            if hasattr(bond_data, 'columns') and not bond_data.empty:
                print('----AmortisingFRN----', bond_type)
                if bond_type == 'ChildAmortisingFRN':
                    df_bondType = pd.concat([df_bondType, bond_data])
                    risc_output_dfs[f"GCP{pdts_flag_str}_{bond_type}"] = create_dataframe_from_columns(f"{bond_type}", rics_import_format, bond_data)
                else:
                    risc_output_dfs[f"GCP{pdts_flag_str}_ChildAmortisingFRN_{bond_type}"] = create_dataframe_from_columns(f"{bond_type}", rics_import_format, bond_data)
                

    risc_output_dfs[f"GCP{pdts_flag_str}_ChildModelTypes"] = create_dataframe_from_columns(f"ChildModelTypes", rics_import_format, df_bondType)



    # holdings: nominal or market value?
    print('----Holdings----')
    df_holdings = pd.merge(pdts_df[['instrumentId','Name']],combined_data['portfolioDetail'], on='instrumentId', how='right')
    df_holdings = df_holdings.rename(columns={'holdingAmount': 'Weight'})
    df_holdings['Weight'] = df_holdings['Weight'].fillna(0)
    df_holdings['Asset'] = df_holdings['Name'] + '.' + df_holdings['instrumentId']
    df_holdings['CurrencyHedge'] = Model_Assumptions['CurrencyHedge']
    df_holdings.drop_duplicates(inplace=True)
    risc_output_dfs[f"Portfolio_Holdings"] = create_dataframe_from_columns(f"Holdings", rics_import_format, df_holdings)


    # Print a summary of risc_output_dfs
    print("\nSummary of risc_output_dfs:")
    for key, df in risc_output_dfs.items():
        print(f"{key}: {df.shape[0]} rows, {df.shape[1]} columns")
        if 'Name' in df.columns:
            print(f"  Unique Names: {df['Name'].nunique()}")
        elif 'Asset' in df.columns:
            print(f"  Unique Assets: {df['Asset'].nunique()}")

    return risc_output_dfs



## updated on 9/24/2025
def table_sort_key(item, pdts_str):
    """
    Custom sorting key function for RICS output tables.
    
    Sorting hierarchy:
    1. GCP{pdts}_{data_type}
    2. Loading (geography -> property; region->product) 
    3. PDTermStructure (if pdts=true)
    4. ChildModelType
    5. ChildBond (bond -> lgd -> lgdk)
    6. ChildFRN (frn -> lgd -> lgdk)
    7. AmortisingBond (principal -> coupon -> amortisingbond -> lgd -> lgdk)
    8. AmortisingFRN
    """
    table_name = item[0]  # item is (table_name, dataframe)
    
    # Define main category priorities
    # Check for basic GCP files first (GC has no suffix, CRE has _CRE, RETAIL has _RETAIL)
    if (table_name == f'GCP{pdts_str}' or 
        table_name == f'GCP{pdts_str}_CRE' or 
        table_name == f'GCP{pdts_str}_RETAIL'):
        return (1, 0, table_name)
    
    elif 'LoadingsParameterSet' in table_name:
        # Sub-priority for loadings: geography -> property; region->product
        if 'Geography' in table_name:
            return (2, 1, table_name)
        elif 'Property' in table_name:
            return (2, 2, table_name)
        elif 'Region' in table_name:
            return (2, 3, table_name)
        elif 'Product' in table_name:
            return (2, 4, table_name)
        else:
            return (2, 5, table_name)  # Other loadings
    
    elif 'PDTermStructureParameterSet' in table_name:
        return (3, 0, table_name)

    elif 'ChildModelTypes' in table_name:
        return (4, 0, table_name)
    
    elif 'ChildBond' in table_name:
        # Sub-priority: bond -> lgd -> lgdk
        if 'LGDKTermStructureParameterSet' in table_name:
            return (5, 3, table_name)
        elif 'LGDMeanTermStructureParameterSet' in table_name:
            return (5, 2, table_name)
        else:
            return (5, 1, table_name)  # Basic ChildBond
    
    elif 'ChildFRN' in table_name:
        # Sub-priority: frn -> lgd -> lgdk
        if 'LGDKTermStructureParameterSet' in table_name:
            return (6, 3, table_name)
        elif 'LGDMeanTermStructureParameterSet' in table_name:
            return (6, 2, table_name)
        else:
            return (6, 1, table_name)  # Basic ChildFRN
    
    elif 'ChildAmortisingBond' in table_name:
        # Sub-priority: amortisingbond -> lgd -> lgdk -> principal -> coupon
        if 'CouponPaymentScheduleParameterSet' in table_name:
            return (7, 3, table_name)
        elif 'PrincipalPaymentScheduleParameterSet' in table_name:
            return (7, 2, table_name)
        elif 'LGDKTermStructureParameterSet' in table_name:
            return (7, 5, table_name)
        elif 'LGDMeanTermStructureParameterSet' in table_name:
            return (7, 4, table_name)
        else:
            return (7, 1, table_name)  # Basic ChildAmortisingBond
    
    elif 'ChildAmortisingFRN' in table_name:
        # Sub-priority similar to bond but for FRN
        if 'PrincipalPaymentScheduleParameterSet' in table_name:
            return (8, 2, table_name)
        elif 'LGDKTermStructureParameterSet' in table_name:
            return (8, 4, table_name)
        elif 'LGDMeanTermStructureParameterSet' in table_name:
            return (8, 3, table_name)
        else:
            return (8, 1, table_name)  # Basic ChildAmortisingFRN
    

    
    elif 'Holdings' in table_name:
        return (9, 0, table_name)  # Holdings at the end
    
    else:
        return (10, 0, table_name)  # Any other files



### updated on 9/24/2025
def save_rics_output_files(risc_output_dfs, path_outputs, output_name, pdts_str):
    # Iterate over risc_output_dfs and save each DataFrame as a CSV file
    output_dir = os.path.join(path_outputs, output_name)
    os.makedirs(output_dir, exist_ok=True)

    # Sort the items according to the custom key
    sorted_items = sorted(risc_output_dfs.items(), key=lambda item: table_sort_key(item, pdts_str))

    count = 1
    for table_name, df in sorted_items:
        if "Holdings" in table_name:
            csv_filename = f"{table_name}.csv"
        else:
            csv_filename = f"{count}_{table_name}.csv"
            count += 1

        csv_path = os.path.join(output_dir, csv_filename)
        df.drop_duplicates(inplace=True)
        df.to_csv(csv_path, index=False)

       



def generate_rics_outputs(combined_data, gcorr_mapping, data_type, Model_Assumptions, coupon_frequencies, Floating_Reference_Yield_Curves, Start_Date, data_path, path_outputs, RICS_version="10.6"):

    
    if not 'AGENCY' in data_type:
        GCP_df = process_counterparty(combined_data['counterparty'], gcorr_mapping, Model_Assumptions['Others'])
    else:
        GCP_df = process_agency_counterparty(combined_data['counterparty'], Model_Assumptions['Agency'])
    GCP_df.drop_duplicates(inplace=True) 


    # Print duplicate 'Name' values in GCP_df
    duplicate_names = GCP_df[GCP_df.duplicated(subset=['Name'], keep=False)]
    if not duplicate_names.empty:
        print("Duplicate 'Name' values in GCP_df:")
        # pd.set_option('display.max_columns', None)
        # print(duplicate_names)
        duplicate_names.to_csv(os.path.join(path_outputs, f"duplicate_names_{data_type}.csv"), index=False)


    pdts_df = GCP_df[GCP_df['PDTS'] == True]
    non_pdts_df = GCP_df[GCP_df['PDTS'] == False]


    if not pdts_df.empty:
        print('----PDTS----')
        pdts_flag = True
        df_rics_output_pdts = process_rics_output_files(pdts_flag, pdts_df, combined_data, gcorr_mapping, data_type, Model_Assumptions['Others'], coupon_frequencies, Floating_Reference_Yield_Curves, Start_Date, data_path, RICS_version)
        # modified 09/24/2025
        pdts_flag_str = '_PDTS' if pdts_flag else ''
        output_name = f"{data_type}/GCP{pdts_flag_str}"
        # modified 09/24/2025
        save_rics_output_files(df_rics_output_pdts, path_outputs, output_name, pdts_flag_str)

        print("GCP RICS outputs generated successfully for start date: ", Start_Date)
        
    if not non_pdts_df.empty:
        print('----NON PDTS----')
        pdts_flag = False
        df_rics_output_non_pdts = process_rics_output_files(pdts_flag, non_pdts_df, combined_data, gcorr_mapping, data_type, Model_Assumptions['Others'], coupon_frequencies, Floating_Reference_Yield_Curves, Start_Date, data_path, RICS_version)
        # modified 09/24/2025
        pdts_flag_str = '_PDTS' if pdts_flag else ''
        output_name = f"{data_type}/GCP{pdts_flag_str}"
        # modified 09/24/2025
        save_rics_output_files(df_rics_output_non_pdts, path_outputs, output_name, pdts_flag_str)

        print("GCP RICS outputs generated successfully for start date: ", Start_Date)


