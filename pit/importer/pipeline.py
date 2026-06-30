# -*- coding: utf-8 -*-
"""
RICS API Bulk Import Tool
@author: peic
"""

import sys
import os
import pandas as pd
import re
import yaml
import time
import warnings

# Suppress FutureWarnings from pandas
warnings.filterwarnings('ignore', category=FutureWarning)

#=======================================================================================================================
# Load Configuration from YAML file
def load_config(config_file='config_CMHC_5Y.yaml'):
    """Load configuration from YAML file."""
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    return config

def normalize_output_config(config_dict):
    """Return sanitized output configuration; blank values mean no outputs."""
    issuer_bond_output = config_dict.get('Issuer_Bond_Output') or {}

    raw_outputs = issuer_bond_output.get('outputs') or []
    if not isinstance(raw_outputs, list):
        raw_outputs = [raw_outputs]
    outputs = [
        item.strip() for item in raw_outputs
        if isinstance(item, str) and item.strip()
    ]

    raw_selection = issuer_bond_output.get('selection') or []
    if not isinstance(raw_selection, list):
        raw_selection = [raw_selection]

    selection = []
    for item in raw_selection:
        if isinstance(item, list):
            cleaned = [
                entry.strip() for entry in item
                if isinstance(entry, str) and entry.strip()
            ]
            selection.append(cleaned)
        elif isinstance(item, str):
            cleaned_item = item.strip()
            if cleaned_item:
                selection.append([cleaned_item])

    # Keep Outputs/Selection index-aligned.
    pair_count = min(len(outputs), len(selection))
    return outputs[:pair_count], selection[:pair_count]

#=======================================================================================================================

from pit.importer.read_rics_files import *
from io import StringIO

# Bound at runtime by run() (real SG) or by tests (FakeSG). Never initialized at import.
sim = None
BulkImporter = None
ParameterSetImporter = None
DuplicateImportAction = None
String = None
File = None
Path_Infos = {}
multiple_GCP_types = {}

# Settings globals — bound by run()
load_sim = None
keep_existing_portfolios = None
import_economies = None
import_transition_matrices = None
import_mpr_models = None
import_zscore_models = None
baseDate = None
baseEconomy = None
structured_portfolios_parameters = None
userDefined_combined_structured_nonstructured_portfolios = None
Outputs = None
Selection = None
bho_output_path = None


def import_param_set(file_path, issuers, nameChild):
    """Import parameter set from file."""
    # Filter out None issuers
    valid_issuers = [issuer for issuer in issuers if issuer is not None]

    if not valid_issuers:
        print(f"Error: No valid issuers provided for parameter set '{nameChild}'")
        return

    print(f"Importing {nameChild} for {len(valid_issuers)} issuers")
    # Read as DataFrame, sort, then convert back to list of strings
    try:
        df = pd.read_csv(file_path)
        if len(df.columns) >= 3:
            # Convert second column to numeric for proper sorting (if it's numeric)
            col1_name = df.columns[0]
            col2_name = df.columns[1]
            col3_name = df.columns[2]

            # Try to convert second column to numeric, keep as string if it fails
            df[col2_name] = pd.to_numeric(df[col2_name], errors='ignore')

            # Sort by first three columns
            df = df.sort_values(by=[col1_name, col2_name, col3_name])

            # Convert back to CSV format (header + data rows)
            output = StringIO()
            df.to_csv(output, index=False, lineterminator='\n')
            paramSetData = output.getvalue().strip().split('\n')
        else:
            # If less than 3 columns, just read normally
            paramSetData = list(File.ReadAllLines(file_path))
    except Exception as e:
        # Fallback to original method if DataFrame reading fails
        print(f"Warning: Could not read as DataFrame, using original method: {e}")
        paramSetData = list(File.ReadAllLines(file_path))
    depth = 0
    if len(paramSetData) > 1 and paramSetData[1]:
        first = re.split(r'[;,]', paramSetData[1], maxsplit=1)[0]
        depth = first.count('.')
    try:
        ParameterSetImporter.Import(valid_issuers, nameChild, paramSetData, depth)
        print(f"Successfully imported {nameChild} for {len(valid_issuers)} issuers")
    except Exception as e:
        print(f"Error importing parameter set '{nameChild}': {e}")
        # Don't raise - continue with other imports
        pass


def import_param_set_by_name(nameChild, file_name, csv_files, issuers):
    """Find and import parameter set by name."""
    if not issuers:
        print(f"No issuers provided for {nameChild}")
        return

    # Filter out None issuers
    valid_issuers = [issuer for issuer in issuers if issuer is not None]
    if not valid_issuers:
        print(f"No valid issuers found for {nameChild}")
        return

    # For IndustryFactorLoadings, also search for IndustryLoadings (without Factor)
    # This handles cases where merged files may have different naming conventions
    # e.g., "IndustryFactorLoadings" vs "IndustryLoadings"
    file_path = None
    if nameChild == 'IndustryFactorLoadings':
        # First try exact match
        file_path = next((f for f in csv_files if file_name in f), None)
        # If not found, try searching for files with both "Industry" and "Loadings"
        if not file_path:
            file_path = next((f for f in csv_files if 'Industry' in f and 'Loadings' in f), None)
    else:
        # For other parameter sets, use exact match
        file_path = next((f for f in csv_files if file_name in f), None)

    if file_path:
        print(f"Importing {nameChild} from {os.path.basename(file_path)}")
        import_param_set(file_path, valid_issuers, nameChild)
    else:
        print(f"File containing '{file_name}' not found for {nameChild}")


def convert_to_param_value(value):
    """
    Convert a value to a string suitable for parameter setting.
    If the value is numeric and represents an integer, convert it to int first.
    This ensures values like 12.0 become "12" instead of "12.0".
    """
    if pd.isna(value):
        return str(value)

    # If already an integer type, convert directly
    if isinstance(value, int):
        return str(value)

    # Try to convert to numeric
    try:
        numeric_value = pd.to_numeric(value, errors='raise')
        # Check if it's a float that represents an integer (e.g., 12.0, 4.0)
        # This handles both Python float and numpy float types
        if isinstance(numeric_value, float) and numeric_value.is_integer():
            return str(int(numeric_value))
        # If it's already an integer type (including numpy int types)
        elif isinstance(numeric_value, int) or (hasattr(numeric_value, 'dtype') and 'int' in str(numeric_value.dtype)):
            return str(int(numeric_value))
        # For other numeric types, convert to string
        else:
            return str(numeric_value)
    except (ValueError, TypeError):
        # If not numeric or conversion fails, return as string
        return str(value)

def sanitize_child_model_name(model_name, child_type):
    """Create a safe fallback model name when raw naming fails."""
    name = str(model_name).strip()
    # Keep alnum/underscore only for fallback naming.
    name = re.sub(r'[^A-Za-z0-9_]', '_', name)
    if not name:
        name = child_type
    if not re.match(r'^[A-Za-z]', name):
        name = f"{child_type}_{name}"
    return name

def create_child_model(parent_issuer, child_type, model_name, row):
    """Create and configure a child model.
    Returns: (model, nan_warnings) where nan_warnings is a list of (column_name, model_name) tuples
    """
    nan_warnings = []
    try:
        bond_id = model_name.split('.')[-1] if '.' in model_name else model_name
        bond_id = str(bond_id).strip()
        if not bond_id:
            print(f"Skipping {child_type} with empty model name for parent {parent_issuer.Name}")
            return None, []

        # Skip if this child already exists under the same parent.
        try:
            existing_model = parent_issuer.SubModel(bond_id)
        except Exception:
            existing_model = None
        if existing_model is not None:
            return existing_model, []

        # Create the model
        new_model = parent_issuer.AddModel(child_type)

        # Prefer raw identifier. If rejected, use a safe fallback instead of default Bond1/Bond2 names.
        try:
            new_model.Name = bond_id
        except Exception:
            fallback_name = sanitize_child_model_name(bond_id, child_type)
            new_model.Name = fallback_name
            print(f"Warning: Could not use child name '{bond_id}', fallback to '{fallback_name}'")

        # Set parameters from CSV row
        for col_name, value in row.items():
            if col_name != 'Name':
                try:
                    param = new_model.Parameter(col_name)
                    if pd.notna(value) and str(value).strip() != '':
                        # Set parameter value if not None/NaN/empty
                        param.Value = convert_to_param_value(value)
                    else:
                        # If value is None/NaN/empty, track it for warning
                        nan_warnings.append((col_name, model_name))
                except Exception:
                    pass  # Skip parameters that can't be set

        return new_model, nan_warnings  # Return the created model and warnings
    except Exception as e:
        print(f"Failed to create {child_type} model {model_name}: {e}")
        return None, []

# need to adjust for Selective agency mbs model import (only import instruments for 3 given issuers) !!!
def import_GCP_agency_mbs(GCP_model, importer, subfolder, csv_files, typeChild, currency_list, model_lists=None):
    """Import AgencyMBS issuer from file."""
    if model_lists is None:
        model_lists = {}
    # issuer level
    gcp_file = next((f for f in csv_files if os.path.basename(f) in ["AgencyMBSIssuer.csv", "MBSAgencies.csv"]), None)
    if not gcp_file:
        print(f"No AgencyMBSIssuer file found in {subfolder}")
        return currency_list, 0, 0, []

    print(f" *****Importing {typeChild} from {os.path.basename(gcp_file)}*****")
    # Use synchronous Import instead of ImportAsync to ensure completion
    import_success = False
    try:
        importer.Import(GCP_model, typeChild, gcp_file)
        import_success = True
        print(f"  Import completed successfully")
    except AttributeError:
        # If Import doesn't exist, use ImportAsync and wait
        importer.ImportAsync(GCP_model, typeChild, gcp_file)
        # Wait a bit for async import to complete
        time.sleep(3)  # Increased wait time
        import_success = True
        print(f"  Async import initiated, waiting for completion...")
    except Exception as e:
        print(f"Error during import: {e}")
        import traceback
        traceback.print_exc()
        # Continue anyway to see if models were created

    # Additional wait after import to ensure models are created
    if import_success:
        time.sleep(1)

    # Get issuers from the imported data
    df_gcp = pd.read_csv(gcp_file)
    df_gcp = df_gcp.sort_values(by=df_gcp.columns[0]).reset_index(drop=True)
    issuer_names = df_gcp['Name'].unique().tolist()
    print(f"Looking for {len(issuer_names)} issuers: {issuer_names}")
    issuers = []

    # Retry finding issuers a few times in case import is still completing
    max_retries = 10  # Increased retries
    for retry in range(max_retries):
        issuers = []
        for name in issuer_names:
            try:
                issuer = sim.FindModelByName(name)
                if issuer is not None:
                    issuers.append(issuer)
            except Exception:
                pass  # Will retry

        if len(issuers) == len(issuer_names):  # Found all issuers
            print(f"Found all {len(issuers)} issuers on retry {retry + 1}")
            break
        elif len(issuers) > len(issuer_names) * 0.5:  # If we found at least 50% of issuers
            print(f"Found {len(issuers)}/{len(issuer_names)} issuers on retry {retry + 1}, continuing...")
            # Don't break, keep trying to find all
        if retry < max_retries - 1:
            time.sleep(1)  # Increased wait time between retries

    if not issuers:
        print(f"No valid issuers found in {subfolder}")
        return currency_list, 0, 0, []

    print(f"Found {len(issuers)} issuers")

    if 'Economy' in df_gcp.columns:
        currency_list.extend(df_gcp['Economy'].dropna().unique().tolist())

    # parameter set level
    print(f"Importing Parameter Sets from {os.path.basename(gcp_file)}")
    import_param_set_by_name('LaggardDistribution', "Laggard", csv_files, issuers)

    # Import child models (bonds, FRNs, etc.)
    child_types_file = next((f for f in csv_files if "ChildModelTypes" in f), None)
    if child_types_file:
        df_types = pd.read_csv(child_types_file)
        df_types = df_types.sort_values(by=df_types.columns[0]).reset_index(drop=True)
        output_data = df_types['Name'].unique().tolist()
        child_types = df_types['Type'].unique().tolist()
        print('------Start importing child models------')
        for child_type in child_types:
            child_file = next((f for f in csv_files if f"{child_type}.csv" in os.path.basename(f)), None)
            if child_file:
                print(f" ***Importing {child_type} models from {os.path.basename(child_file)}***")
                df_child = pd.read_csv(child_file)

                # Order the dataframe by first column, or by the first three columns if the filename contains "parameterset" in the child_types_file
                if "parameterset" in os.path.basename(child_file).lower():
                    df_child = df_child.sort_values(by=df_child.columns[:3].tolist()).reset_index(drop=True)
                else:
                    df_child = df_child.sort_values(by=df_child.columns[0]).reset_index(drop=True)

                # Remove duplicate instrument rows by Name to avoid duplicate child creation.
                if 'Name' in df_child.columns:
                    original_count = len(df_child)
                    df_child['Name'] = df_child['Name'].astype(str).str.strip()
                    df_child = df_child[df_child['Name'] != '']
                    df_child = df_child.drop_duplicates(subset=['Name'], keep='first').reset_index(drop=True)
                    removed_count = original_count - len(df_child)
                    if removed_count > 0:
                        print(f"    Removed {removed_count} duplicate/blank {child_type} rows by Name")

                created_models = []
                for _, row in df_child.iterrows():
                    model_name = row.get('Name', '')
                    # Find parent issuer - split by '.' and match first part exactly
                    parent_name = model_name.split('.')[0] if '.' in model_name else model_name
                    parent = next((issuer for issuer in issuers
                                 if issuer.Name == parent_name), None)
                    if parent:
                        new_model, nan_warnings = create_child_model(parent, child_type, model_name, row)
                        if new_model:
                            created_models.append(new_model)
                            # Track NaN warnings
                            if nan_warnings:
                                if 'nan_warnings' not in model_lists:
                                    model_lists['nan_warnings'] = []
                                model_lists['nan_warnings'].extend(nan_warnings)

                print(f"------Completed importing {child_type} models------")
    else:
        output_data = issuer_names

    # Count total child models (instruments) created - sum up from created_models
    total_child_models = 0
    if child_types_file:
        df_types = pd.read_csv(child_types_file)
        df_types = df_types.sort_values(by=df_types.columns[0]).reset_index(drop=True)
        child_types = df_types['Type'].unique().tolist()
        for child_type in child_types:
            child_file = next((f for f in csv_files if f"{child_type}.csv" in os.path.basename(f)), None)
            if child_file:
                df_child = pd.read_csv(child_file)
                # Count models that have matching parent issuers
                for _, row in df_child.iterrows():
                    model_name = row.get('Name', '')
                    parent_name = model_name.split('.')[0] if '.' in model_name else model_name
                    parent = next((issuer for issuer in issuers if issuer.Name == parent_name), None)
                    if parent:
                        total_child_models += 1

    return currency_list, len(issuers), total_child_models, output_data


def import_GCP_nonagency_mbs(GCP_model, importer, subfolder, csv_files, csv_info, model_lists):
    """
    Import non-Agency MBS issuer from file:
    GCP/GCP_PDTS/GCP_CRE/GCP_PDTS_CRE/GCP_RETAIL/GCP_PDTS_RETAIL
    """
    # Get configuration for this subfolder
    typeChild = csv_info['typeChild']
    model_type = csv_info['model_type']
    pdts_flag = csv_info['pdts_flag']

    gcp_file_list = [
        "1_GCP",
        "1_GCP_CLO",
        "1_GCP_CRE",
        "1_GCP_RETAIL",
        "1_GCP_SOV",
        "1_GCP_PDTS",
        "1_GCP_PDTS_CLO",
        "1_GCP_PDTS_CRE",
        "1_GCP_PDTS_RETAIL",
        "1_GCP_PDTS_SOV",
        "1_GranularCounterparty",
        "GranularCounterparty.csv",
        "GranularCounterpartyWithPDTermStructure.csv",
        "GranularCounterpartyCRE.csv",
        "GranularCounterpartyCREWithPDTermStructure.csv",
        "GranularCounterpartyRetail.csv",
        "GranularCounterpartyRetailWithPDTermStructure.csv"
        ]

    # issuer level - find GCP file, prioritizing exact matches and excluding parameter set files
    gcp_file = None
    # Remove numeric prefixes and suffixes for comparison
    def normalize_filename(basename):
        """Remove numeric prefix and .csv extension for comparison"""
        name = re.sub(r'^\d+_', '', basename)  # Remove leading digits and underscore
        name = name.replace('.csv', '')  # Remove .csv extension
        return name

    # First, prioritize files starting with "1_" that are not child models or parameter sets
    # This ensures we get the main GCP file, not child model files
    for f in csv_files:
        basename = os.path.basename(f)
        # Skip parameter set files
        if "ParameterSet" in basename:
            continue
        # Skip child model files
        if "Child" in basename:
            continue
        # Prioritize files starting with "1_"
        if basename.startswith("1_"):
            normalized_name = normalize_filename(basename)
            # Check if it matches any pattern (excluding child models)
            for pattern in gcp_file_list:
                pattern_base = re.sub(r'^\d+_', '', pattern.replace('.csv', ''))
                if normalized_name == pattern_base or normalized_name.startswith(pattern_base):
                    gcp_file = f
                    break
            if gcp_file:
                break

    # If still not found, try exact matches from gcp_file_list
    if not gcp_file:
        for pattern in gcp_file_list:
            # Normalize pattern (remove numeric prefix if present, remove .csv)
            pattern_base = re.sub(r'^\d+_', '', pattern.replace('.csv', ''))
            for f in csv_files:
                basename = os.path.basename(f)
                # Skip parameter set files
                if "ParameterSet" in basename:
                    continue
                # Skip child model files
                if "Child" in basename:
                    continue
                # Normalize filename for comparison
                normalized_name = normalize_filename(basename)
                # Check if normalized name matches the normalized pattern
                if normalized_name == pattern_base:
                    gcp_file = f
                    break
            if gcp_file:
                break

    # If still not found, try broader matching but still exclude parameter sets and child models
    if not gcp_file:
        for pattern in gcp_file_list:
            pattern_base = re.sub(r'^\d+_', '', pattern.replace('.csv', ''))
            for f in csv_files:
                basename = os.path.basename(f)
                if "ParameterSet" not in basename and "Child" not in basename:
                    normalized_name = normalize_filename(basename)
                    # Check if the pattern is contained in the normalized name
                    # But require that it's not a child model (more specific check)
                    if pattern_base in normalized_name and not any(child_type in normalized_name for child_type in ["ChildBond", "ChildFRN", "ChildAmortising"]):
                        gcp_file = f
                        break
            if gcp_file:
                break

    if not gcp_file:
        print(f"No GCP file found in {subfolder}")
        return model_lists, 0, 0, []

    print(f" *****Importing {typeChild} from {os.path.basename(gcp_file)}*****")

    # Check for existing models to prevent duplicates
    df_gcp_check = pd.read_csv(gcp_file)
    df_gcp_check = df_gcp_check.sort_values(by=df_gcp_check.columns[0]).reset_index(drop=True)
    existing_issuer_names = df_gcp_check['Name'].unique().tolist()
    existing_issuers = []
    for name in existing_issuer_names:
        try:
            existing_issuer = sim.FindModelByName(name)
            if existing_issuer is not None:
                existing_issuers.append(existing_issuer)
        except Exception:
            pass

    # If models already exist, remove them to prevent duplicates with numbered suffixes
    if existing_issuers:
        print(f"Warning: Found {len(existing_issuers)} existing models with matching names. Removing them to prevent duplicates...")
        for issuer in existing_issuers:
            try:
                issuer.Delete()
            except Exception as e:
                print(f"  Could not delete existing model {issuer.Name}: {e}")
        # Wait a bit for deletions to complete
        time.sleep(1)

    # Use synchronous Import instead of ImportAsync to ensure completion
    import_succeeded = False
    try:
        importer.Import(GCP_model, typeChild, gcp_file)
        import_succeeded = True
        print(f"Import completed successfully using Import()")
    except AttributeError:
        # If Import doesn't exist, use ImportAsync and wait
        try:
            importer.ImportAsync(GCP_model, typeChild, gcp_file)
            import_succeeded = True
            print(f"Import initiated using ImportAsync()")
        except Exception as e:
            print(f"Error during ImportAsync: {e}")
            import_succeeded = False
    except Exception as e:
        print(f"Error during Import: {e}")
        import_succeeded = False
        # Try ImportAsync as fallback
        try:
            print(f"Attempting fallback to ImportAsync...")
            importer.ImportAsync(GCP_model, typeChild, gcp_file)
            import_succeeded = True
            print(f"Fallback ImportAsync initiated")
        except Exception as e2:
            print(f"Error during fallback ImportAsync: {e2}")
            import_succeeded = False

    if not import_succeeded:
        print(f"ERROR: Import failed for {os.path.basename(gcp_file)}. Cannot proceed with finding issuers.")
        return model_lists, 0, 0, []

    # Wait a bit for import to complete (especially for async imports)
    time.sleep(2)

    # Get issuers from the imported data
    df_gcp = pd.read_csv(gcp_file)
    df_gcp = df_gcp.sort_values(by=df_gcp.columns[0]).reset_index(drop=True)
    issuer_names = df_gcp['Name'].unique().tolist()
    print(f"Looking for {len(issuer_names)} issuers: {issuer_names}")
    issuers = []

    # Retry finding issuers a few times in case import is still completing
    max_retries = 10  # Increased retries
    for retry in range(max_retries):
        issuers = []
        for name in issuer_names:
            try:
                issuer = sim.FindModelByName(name)
                if issuer is not None:
                    issuers.append(issuer)
            except Exception as e:
                pass  # Will retry

        if len(issuers) == len(issuer_names):  # Found all issuers
            print(f"Found all {len(issuers)} issuers on retry {retry + 1}")
            break
        elif len(issuers) > len(issuer_names) * 0.5:  # If we found at least 50% of issuers
            print(f"Found {len(issuers)}/{len(issuer_names)} issuers on retry {retry + 1}, continuing...")
            # Don't break, keep trying to find all
        if retry < max_retries - 1:
            time.sleep(1)  # Increased wait time between retries

    # Report missing issuers
    found_names = {issuer.Name for issuer in issuers if issuer is not None}
    missing_names = [name for name in issuer_names if name not in found_names]
    if missing_names:
        print(f"Warning: Could not find {len(missing_names)} issuers after import")
        if len(missing_names) <= 10:
            for name in missing_names:
                print(f"  Missing: {name}")
        else:
            print(f"  First 10 missing: {missing_names[:10]}")

    if not issuers:
        print(f"No valid issuers found in {subfolder}")
        return model_lists, 0, 0, []

    print(f"Found {len(issuers)} valid issuers out of {len(issuer_names)} total")

    # Collect unique models (avoid duplicates)
    model_lists['transition_matrices'].extend(df_gcp['TransitionMatrix'].unique().tolist())

    # Find column containing 'MPR'
    mpr_column = next((col for col in df_gcp.columns if 'MPR' in col), None)
    if mpr_column:
        model_lists['mpr_models'].extend(df_gcp[mpr_column].unique().tolist())

    if not pdts_flag:
        zscore_column = next((col for col in df_gcp.columns if 'ScoreModel' in col), None)
        if zscore_column:
            model_lists['zscore_models'].extend(df_gcp[zscore_column].unique().tolist())


    # Import parameter sets based on model type
    print(f"Importing Parameter Sets from {os.path.basename(gcp_file)}")
    if model_type == "" or model_type == "_CLO":
        import_param_set_by_name('IndustryFactorLoadings', "IndustryFactorLoadings", csv_files, issuers)
    elif model_type == "_CRE":
        import_param_set_by_name('GeographyLoadings', "GeographyLoadings", csv_files, issuers)
        import_param_set_by_name('PropertyTypeLoadings', "PropertyTypeLoadings", csv_files, issuers)
    elif model_type == "_RETAIL":
        import_param_set_by_name('RegionLoadings', "RegionLoadings", csv_files, issuers)
        import_param_set_by_name('ProductTypeLoadings', "ProductTypeLoadings", csv_files, issuers)
    elif model_type == "_SOV":
        import_param_set_by_name('SovereignLoadings', "SovereignLoadings", csv_files, issuers)

    if pdts_flag:
        import_param_set_by_name('PDTermStructure', "PDTermStructureParameterSet", csv_files, issuers)


    # Import child models (bonds, FRNs, etc.)
    child_types_file = next((f for f in csv_files if "ChildModelTypes" in f), None)
    if child_types_file:
        df_types = pd.read_csv(child_types_file)
        df_types = df_types.sort_values(by=df_types.columns[0]).reset_index(drop=True)
        output_data = df_types['Name'].unique().tolist()
        child_types = df_types['Type'].unique().tolist()
        print('------Start importing child models------')
        for child_type in child_types:
            child_file = next((f for f in csv_files if re.search(rf"Child{child_type}{model_type}\.csv$", os.path.basename(f)) or re.search(rf"Child{child_type}\.csv$", os.path.basename(f))), None)

            if child_file:
                print(f" ***Importing {child_type} models from {os.path.basename(child_file)}***")
                df_child = pd.read_csv(child_file)

                if "parameterset" in os.path.basename(child_file).lower():
                    df_child = df_child.sort_values(by=df_child.columns[:3].tolist()).reset_index(drop=True)
                else:
                    df_child = df_child.sort_values(by=df_child.columns[0]).reset_index(drop=True)

                # Remove duplicate instrument rows by Name to avoid duplicate child creation.
                if 'Name' in df_child.columns:
                    original_count = len(df_child)
                    df_child['Name'] = df_child['Name'].astype(str).str.strip()
                    df_child = df_child[df_child['Name'] != '']
                    df_child = df_child.drop_duplicates(subset=['Name'], keep='first').reset_index(drop=True)
                    removed_count = original_count - len(df_child)
                    if removed_count > 0:
                        print(f"    Removed {removed_count} duplicate/blank {child_type} rows by Name")

                # Collect currencies from child models
                if 'Economy' in df_child.columns:
                    model_lists['currency_list'].extend(df_child['Economy'].dropna().unique().tolist())

                created_models = []
                for _, row in df_child.iterrows():
                    model_name = row.get('Name', '')
                    # Find parent issuer - split by '.' and match first part exactly
                    parent_name = model_name.split('.')[0] if '.' in model_name else model_name
                    parent = next((issuer for issuer in issuers
                                 if issuer.Name == parent_name), None)
                    if parent:
                        new_model, nan_warnings = create_child_model(parent, child_type, model_name, row)
                        if new_model:
                            created_models.append(new_model)
                            # Track NaN warnings
                            if nan_warnings and 'nan_warnings' not in model_lists:
                                model_lists['nan_warnings'] = []
                            if nan_warnings:
                                model_lists['nan_warnings'].extend(nan_warnings)

                # Import parameter sets for created models only
                if created_models:
                    if "Amortising" in child_type:
                        import_param_set_by_name('PrincipalPaymentSchedule', f"Child{child_type}_PrincipalPaymentSchedule", csv_files, created_models)
                        if "Bond" in child_type:
                            import_param_set_by_name('CouponPaymentSchedule', f"Child{child_type}_CouponPaymentSchedule", csv_files, created_models)

                    print(f"    Found {len(created_models)} created {child_type} models, importing parameter sets...")
                    import_param_set_by_name('LGDMeanTermStructure', f"Child{child_type}_LGDMeanTermStructure", csv_files, created_models)
                    import_param_set_by_name('LGDKTermStructure', f"Child{child_type}_LGDKTermStructure", csv_files, created_models)
                else:
                    print(f"    No {child_type} models were created, skipping parameter set import")

                print(f"------Completed importing {child_type} models------")

    else:
        output_data = issuer_names

    # Count total child models (instruments) created
    total_child_models = 0
    if child_types_file:
        df_types = pd.read_csv(child_types_file)
        df_types = df_types.sort_values(by=df_types.columns[0]).reset_index(drop=True)
        child_types = df_types['Type'].unique().tolist()
        for child_type in child_types:
            child_file = next((f for f in csv_files if re.search(rf"Child{child_type}{model_type}\.csv$", os.path.basename(f)) or re.search(rf"Child{child_type}\.csv$", os.path.basename(f))), None)
            if child_file:
                df_child = pd.read_csv(child_file)
                # Count models that have matching parent issuers
                for _, row in df_child.iterrows():
                    model_name = row.get('Name', '')
                    parent_name = model_name.split('.')[0] if '.' in model_name else model_name
                    parent = next((issuer for issuer in issuers if issuer.Name == parent_name), None)
                    if parent:
                        total_child_models += 1

    return model_lists, len(issuers), total_child_models, output_data




def process_GCP_imports(subfolder, csv_files, csv_info, model_lists):
    """Process all CSV files in a subfolder."""
    print(f"Processing {subfolder}...")

    model_type = csv_info['model_type']
    output_type = csv_info['output_type']
    print(f"Model type: {model_type}")
    print(f"Output type: {output_type}")

    # Import GCP models using BulkImporter
    GCP_model = sim.FindModelByFullyQualifiedName("RICS.Assets.GranularCounterparties")
    importer = BulkImporter()

    # Track issuers and child models imported
    num_issuers = 0
    num_child_models = 0

    # Import main GCP file
    if model_type == "AgencyMBS":
        currency_list, issuers_count, child_models_count, model_lists['output_data'][output_type] = import_GCP_agency_mbs(GCP_model, importer, subfolder, csv_files, csv_info['typeChild'], model_lists['currency_list'], model_lists)
        model_lists['currency_list'] = currency_list
        num_issuers = issuers_count
        num_child_models = child_models_count
    else:
        model_lists, issuers_count, child_models_count, model_lists['output_data'][output_type] = import_GCP_nonagency_mbs(GCP_model, importer, subfolder, csv_files, csv_info, model_lists)
        num_issuers = issuers_count
        num_child_models = child_models_count

    # Store issuer and child model counts for this subfolder
    if 'issuer_counts' not in model_lists:
        model_lists['issuer_counts'] = {}
    if 'child_model_counts' not in model_lists:
        model_lists['child_model_counts'] = {}
    model_lists['issuer_counts'][subfolder] = num_issuers
    model_lists['child_model_counts'][subfolder] = num_child_models

    print(f'*****Granular Counterparties imported successfully*****')
    return model_lists


def apply_portfolio_params(df, portfolio_name, params):
    """Apply portfolio parameters to a dataframe."""
    if not params or not params[0]:  # Check if enabled
        return None
    df = df.copy()
    df['Name'] = portfolio_name
    df['Economy'] = params[1] if len(params) > 1 else df.get('Economy', '')
    df['WeightDefinition'] = params[2] if len(params) > 2 else df.get('WeightDefinition', '')
    df['ParameterSetIndex'] = df.groupby('Name').cumcount() + 1
    return df


def process_structured_portfolios(csv_portfolio_files, structured_portfolios_parameters, cols):
    """Process structured portfolio files and apply configuration parameters."""
    df_structured_portfolio = pd.DataFrame()
    df_structured_holdings = pd.DataFrame()

    if not csv_portfolio_files:
        return df_structured_portfolio, df_structured_holdings

    # Mapping from subfolder names to config keys and portfolio names
    portfolio_mapping = {
        'agency_cmbs': ('agency_cmbs', 'Agency_CMBS'),
        'gcp_clo': ('structured_clo', 'Structured_CLO'),
        'gcp_cre': ('structured_cre', 'Structured_CRE'),
        'gcp_retail': ('structured_retail', 'Structured_RETAIL')
    }

    df_tmp = pd.DataFrame()
    df_all = pd.DataFrame()
    processed_flags = set()
    # Process individual portfolio files
    count_selected_portfolios = 0
    for subfolder_name, portfolio_file in csv_portfolio_files.items():
        try:
            df = pd.read_csv(portfolio_file)
            df_all = pd.concat([df_all, df], ignore_index=True)

            subfolder_lower = subfolder_name.lower()
            if subfolder_lower in portfolio_mapping:
                config_key, portfolio_name = portfolio_mapping[subfolder_lower]
                params = structured_portfolios_parameters.get(config_key, [False])

                df_processed = apply_portfolio_params(df, portfolio_name, params)
                if df_processed is not None:
                    df_tmp = pd.concat([df_tmp, df_processed], ignore_index=True)
                    processed_flags.add(config_key)
                    count_selected_portfolios += 1
        except Exception as e:
            print(f"Error processing structured portfolio file {portfolio_file}: {e}")
            continue

    # Save df_tmp before adding all_structured (needed for all_structured_selected comparison)
    df_tmp_before_all_structured = df_tmp.copy()

    # Process all_structured portfolio
    all_structured_params = structured_portfolios_parameters.get('all_structured', [False])
    if all_structured_params and all_structured_params[0] and not df_all.empty:
        # Check if all_structured has the same assets as df_tmp
        should_skip = False
        if not df_tmp_before_all_structured.empty:
            # Compare unique assets in df_all (all_structured) vs df_tmp_before_all_structured (selected portfolios only)
            if 'Asset' in df_all.columns and 'Asset' in df_tmp_before_all_structured.columns:
                assets_all_structured = set(df_all['Asset'].dropna().unique())
                assets_selected = set(df_tmp_before_all_structured['Asset'].dropna().unique())
                if assets_all_structured == assets_selected:
                    should_skip = True
                    print(f"Skipping All_Structured: contains same assets as existing portfolios")

        if not should_skip:
            df_all_processed = apply_portfolio_params(df_all, 'All_Structured', all_structured_params)
            if df_all_processed is not None:
                df_all_processed.drop_duplicates(inplace=True)
                df_tmp = pd.concat([df_tmp, df_all_processed], ignore_index=True)
                processed_flags.add('all_structured')

    # Process all_structured_selected portfolio (skip if all_structured contains the same assets)
    all_selected_params = structured_portfolios_parameters.get('all_structured_selected', [False])
    if (all_selected_params and all_selected_params[0] and not df_tmp_before_all_structured.empty):
        # Check if all_structured was processed and contains the same assets
        should_skip = False
        if 'all_structured' in processed_flags and not df_all.empty:
            # Compare unique assets in df_all (all_structured) vs df_tmp_before_all_structured (selected portfolios only)
            if 'Asset' in df_all.columns and 'Asset' in df_tmp_before_all_structured.columns:
                assets_all_structured = set(df_all['Asset'].dropna().unique())
                assets_selected = set(df_tmp_before_all_structured['Asset'].dropna().unique())
                if assets_all_structured == assets_selected:
                    should_skip = True
                    print(f"Skipping All_Structured_Selected: contains same assets as All_Structured")

        if not should_skip and count_selected_portfolios > 1:
            df_all_selected = apply_portfolio_params(df_tmp_before_all_structured, 'All_Structured_Selected', all_selected_params)
            if df_all_selected is not None:
                df_all_selected.drop_duplicates(inplace=True)
                df_tmp = pd.concat([df_tmp, df_all_selected], ignore_index=True)


    # Extract holdings and portfolio definitions
    if not df_tmp.empty:
        df_holdings = df_tmp[cols['holdings']].copy()
        df_holdings.drop_duplicates(inplace=True)
        df_structured_holdings = pd.concat([df_structured_holdings, df_holdings], ignore_index=True)

        df_portfolio = df_tmp[cols['portfolio']].copy()
        df_portfolio.drop_duplicates(inplace=True)
        df_structured_portfolio = pd.concat([df_structured_portfolio, df_portfolio], ignore_index=True)

    return df_structured_portfolio, df_structured_holdings


def archive_non_structured_portfolios(non_structured_portfolio_files, portfolio_path):

    df_nonstructured_portfolio = pd.DataFrame()
    df_nonstructured_holdings = pd.DataFrame()

    if non_structured_portfolio_files:
        print(f"Reading {len(non_structured_portfolio_files)} non-structured portfolio files...")
        for file_path in non_structured_portfolio_files:
            try:
                file_basename = os.path.basename(file_path)
                df = pd.read_csv(file_path)

                if 'Holdings' in file_basename:
                    # Holdings file (check this first since holdings files may contain 'CompositePortfolio' in name)
                    if df_nonstructured_holdings.empty:
                        df_nonstructured_holdings = df.copy()
                    else:
                        df_nonstructured_holdings = pd.concat([df_nonstructured_holdings, df], ignore_index=True)
                    print(f"  Read holdings from {file_basename}: {len(df)} rows")
                elif 'CompositePortfolio' in file_basename:
                    # Portfolio definition file
                    if df_nonstructured_portfolio.empty:
                        df_nonstructured_portfolio = df.copy()
                    else:
                        df_nonstructured_portfolio = pd.concat([df_nonstructured_portfolio, df], ignore_index=True)
                    print(f"  Read portfolio definitions from {file_basename}: {len(df)} rows")

            except Exception as e:
                print(f"Error reading non-structured portfolio file {file_path}: {e}")
                continue

    return df_nonstructured_portfolio, df_nonstructured_holdings


def update_portfolio_files(csv_portfolio_files, non_structured_portfolio_files, portfolio_path, structured_portfolios_parameters, userDefined_portfolios):

    print(f"\n*****Updating portfolio files based on config*****")

    cols = {
        'portfolio': ['Name','Economy','WeightDefinition'],
        'holdings': ['Name','ParameterSetIndex','Asset','Weight','CurrencyHedge']
        }

    # Process structured portfolios
    df_structured_portfolio, df_structured_holdings = process_structured_portfolios(
        csv_portfolio_files, structured_portfolios_parameters, cols
    )

    # If no structured portfolios, return early
    if df_structured_portfolio.empty and df_structured_holdings.empty:
        return non_structured_portfolio_files

    # Archive and read non-structured portfolios
    df_nonstructured_portfolio, df_nonstructured_holdings = archive_non_structured_portfolios(
        non_structured_portfolio_files, portfolio_path
    )


    def normalize_portfolio_columns(df):
        """Normalize portfolio dataframe to have only required columns"""
        if df.empty:
            return df
        # Map portfolioName to Name if needed
        if 'portfolioName' in df.columns and 'Name' not in df.columns:
            df['Name'] = df['portfolioName']
        # Select only required columns
        return df[[col for col in cols['portfolio'] if col in df.columns]].copy()

    df_nonstructured_portfolio = normalize_portfolio_columns(df_nonstructured_portfolio)
    df_structured_portfolio = normalize_portfolio_columns(df_structured_portfolio)

    # Combine portfolios
    df_combined_portfolio = pd.concat([df_nonstructured_portfolio, df_structured_portfolio], ignore_index=True)
    df_combined_holdings = pd.concat([df_nonstructured_holdings, df_structured_holdings], ignore_index=True)

    # Add All_Structured_NonStructured if enabled
    # need to remove all cases (all_structured and all_structured_selected and all_nonstructured) from df_combined_holdings
    all_params = structured_portfolios_parameters.get('all_structured_nonstructured', [False])
    if all_params[0] and not df_structured_portfolio.empty and not df_nonstructured_portfolio.empty:
        new_row = pd.DataFrame([{
            'Name': 'All_Structured_NonStructured',
            'Economy': all_params[1],
            'WeightDefinition': all_params[2]
        }])
        df_combined_portfolio = pd.concat([df_combined_portfolio, new_row], ignore_index=True)

        # Add holdings for All_Structured_NonStructured
        df_all_holdings = df_combined_holdings.copy()
        df_all_holdings = df_all_holdings.drop_duplicates(subset=['Asset', 'Weight', 'CurrencyHedge'])
        df_all_holdings['Name'] = 'All_Structured_NonStructured'
        df_all_holdings['ParameterSetIndex'] = df_all_holdings.groupby('Name').cumcount() + 1
        df_combined_holdings = pd.concat([df_combined_holdings, df_all_holdings], ignore_index=True)


    if userDefined_combined_structured_nonstructured_portfolios:
        for name in userDefined_combined_structured_nonstructured_portfolios:
            # Check if ALL required portfolios exist in df_combined_portfolio
            required_portfolios = userDefined_combined_structured_nonstructured_portfolios[name][0]
            existing_portfolios = set(df_combined_portfolio['Name'].unique())
            if not all(portfolio in existing_portfolios for portfolio in required_portfolios):
                print(f"Skipping {name}: not all required portfolios found. Required: {required_portfolios}, Found: {[p for p in required_portfolios if p in existing_portfolios]}")
                continue

            # Get holdings for the new portfolio from required portfolios
            required_portfolio_names = userDefined_combined_structured_nonstructured_portfolios[name][0]
            df_new_holdings = df_combined_holdings[
                df_combined_holdings['Name'].isin(required_portfolio_names)
            ].copy()

            # Drop duplicates based on (Asset, Weight, CurrencyHedge)
            df_new_holdings = df_new_holdings.drop_duplicates(subset=['Asset', 'Weight', 'CurrencyHedge'])

            # Check if an identical set of holdings already exists with a different name
            # Create a set of (Asset, Weight, CurrencyHedge) tuples for comparison
            if not df_new_holdings.empty:
                new_holdings_set = set(df_new_holdings[['Asset', 'Weight', 'CurrencyHedge']].apply(tuple, axis=1))

                # Check each existing portfolio in df_combined_holdings
                existing_portfolio_names = df_combined_holdings['Name'].unique()
                skip_creation = False

                for existing_name in existing_portfolio_names:
                    if existing_name == name:
                        continue  # Skip checking against itself

                    existing_holdings = df_combined_holdings[
                        df_combined_holdings['Name'] == existing_name
                    ].copy()
                    existing_holdings = existing_holdings.drop_duplicates(subset=['Asset', 'Weight', 'CurrencyHedge'])

                    if not existing_holdings.empty:
                        existing_holdings_set = set(existing_holdings[['Asset', 'Weight', 'CurrencyHedge']].apply(tuple, axis=1))

                        # Check if the sets are identical
                        if new_holdings_set == existing_holdings_set:
                            print(f"Skipping {name}: identical holdings already exist as '{existing_name}'")
                            skip_creation = True
                            break

                if not skip_creation:
                    # Create the new portfolio
                    df_new_holdings['Name'] = name
                    df_new_holdings['ParameterSetIndex'] = df_new_holdings.groupby('Name').cumcount() + 1
                    df_combined_holdings = pd.concat([df_combined_holdings, df_new_holdings], ignore_index=True)

                    new_row = pd.DataFrame([{
                        'Name': name,
                        'Economy': userDefined_combined_structured_nonstructured_portfolios[name][1],
                        'WeightDefinition': userDefined_combined_structured_nonstructured_portfolios[name][2]
                    }])
                    df_combined_portfolio = pd.concat([df_combined_portfolio, new_row], ignore_index=True)
            else:
                print(f"Skipping {name}: no holdings found for required portfolios {required_portfolio_names}")



    # Save files
    portfolio_path_imported = os.path.join(portfolio_path, "Portfolio_Imported")
    os.makedirs(portfolio_path_imported, exist_ok=True)

    updated_files = []
    if not df_combined_portfolio.empty and not df_combined_holdings.empty:
        portfolios_file = os.path.join(portfolio_path_imported, "CompositePortfolio.csv")
        holdings_file = os.path.join(portfolio_path_imported, "CompositePortfolio_HoldingsParameterSet.csv")

        df_combined_portfolio.drop_duplicates(inplace=True)
        df_combined_holdings.drop_duplicates(inplace=True)
        df_combined_portfolio[cols['portfolio']].to_csv(portfolios_file, index=False)
        df_combined_holdings[cols['holdings']].to_csv(holdings_file, index=False)

        print(f"Saved {len(df_combined_portfolio)} portfolios to {portfolios_file}")
        print(f"Saved {len(df_combined_holdings)} holdings to {holdings_file}")
        updated_files.extend([portfolios_file, holdings_file])

    print(f"*****Portfolio files updated successfully*****\n")

    return updated_files


def process_portfolio_imports(folder, files, currency_list, keep_existing_portfolios):
    """Process all CSV files in a subfolder."""
    print(f"Processing {folder}...")

    composite_file = next((f for f in files if os.path.basename(f) in ["CompositePortfolio.csv"]), None)
    if not composite_file:
        print(f"No CompositePortfolio file found in {folder}")
        return currency_list

    print(f" *****Importing CompositePortfolio from {os.path.basename(composite_file)}*****")

    # Read the CSV file
    df_composite = pd.read_csv(composite_file)
    df_composite = df_composite.sort_values(by=df_composite.columns[0]).reset_index(drop=True)
    portfolio_names = df_composite['Name'].unique().tolist()

    created_portfolios = []
    if not keep_existing_portfolios:
        ## every portfolio can be found in the csv file
        GCP_model = sim.FindModelByFullyQualifiedName("RICS.Portfolios")
        importer = BulkImporter()
        importer.ImportAsync(GCP_model, 'CompositePortfolio', composite_file)

        for name in portfolio_names:
            existing_portfolio = sim.FindModelByName(name)
            created_portfolios.append(existing_portfolio)
            print(f"Found existing portfolio: {name}")
    else:
        # Create portfolios using AddModel. This can keep the old model that does not exist in the csv file.
        for name in portfolio_names:
            # Check if portfolio already exists
            existing_portfolio = sim.FindModelByName(name)
            if existing_portfolio is None:
                # Create new CompositePortfolio model
                new_portfolio = sim.AddModel('CompositePortfolio')
                new_portfolio.Name = name

                # Set additional parameters from CSV if they exist
                portfolio_row = df_composite[df_composite['Name'] == name].iloc[0]
                for col_name, value in portfolio_row.items():
                    if col_name != 'Name' and pd.notna(value):
                        try:
                            param = new_portfolio.Parameter(col_name)
                            param.Value = convert_to_param_value(value)
                        except Exception:
                            pass  # Skip parameters that can't be set

                created_portfolios.append(new_portfolio)
                print(f"Created portfolio: {name}")
            else:
                created_portfolios.append(existing_portfolio)
                print(f"Found existing portfolio: {name}")

                ## updating parameters of existing portfolio
                portfolio_row = df_composite[df_composite['Name'] == name].iloc[0]
                for col_name, value in portfolio_row.items():
                    if col_name != 'Name' and pd.notna(value):
                        try:
                            param = existing_portfolio.Parameter(col_name)
                            param.Value = convert_to_param_value(value)
                        except Exception:
                            pass  # Skip parameters that can't be set


    print(f"Found {len(created_portfolios)} portfolios")

    if 'Economy' in df_composite.columns:
        currency_list.extend(df_composite['Economy'].dropna().unique().tolist())
    print(f"Found {len(set(currency_list))} unique currencies")

    # parameter set level
    if created_portfolios:
        print(f"Importing Parameter Sets from {os.path.basename(composite_file)}")

        nameChild = "Holdings"
        file_name = "HoldingsParameterSet"
        # Filter out None portfolios
        valid_portfolios = [portfolio for portfolio in created_portfolios if portfolio is not None]
        if not valid_portfolios:
            print(f"No valid portfolios found for {nameChild}")
            return currency_list

        file_path = next((f for f in files if file_name in f), None)
        if file_path:
            print(f"Importing {nameChild} from {os.path.basename(file_path)}")
            import_param_set(file_path, valid_portfolios, nameChild)
        else:
            print(f"File containing '{file_name}' not found for {nameChild}")

    print(f'*****Portfolios imported successfully*****')
    return currency_list





## import economy, transition matrix, mpr, zscore
def import_models(model_list, model_type):
    for model_name in set(model_list):
        if model_name and model_name != 'N/A':
            print(f"Importing {model_name} {model_type}")
            try:
                # Check if ANY model with this name exists
                existing_model = None
                existing_type = None
                try:
                    candidate = sim.FindModelByName(model_name)
                    if candidate:
                        existing_model = candidate
                        existing_type = candidate.GetType().Name
                except:
                    pass

                if existing_model is None:
                    # No model with this name exists, create it
                    new_model = sim.AddModel(model_type)
                    new_model.Name = model_name
                    print(f"Created {model_name} {model_type}")
                elif existing_type == model_type:
                    # Model with same name and type already exists
                    print(f"{model_name} {model_type} already exists")
                else:
                    # Model with same name but different type exists
                    print(f"Warning: Model {model_name} already exists as type {existing_type}, cannot create as {model_type}")
            except Exception as e:
                print(f"Warning: Could not create {model_type} model {model_name}: {e}")




def add_outputs(sim, granular_counterparties, identifier_list, output_type, csv_filename):
    """
    Add outputs for issuers or bonds.

    Args:
        sim: Simulation object
        granular_counterparties: GranularCounterparties model
        identifier_list: List of identifiers - issuer IDs (e.g., ["11A", "12A"])
                        or bond IDs (e.g., ["11A.1a", "11A.1b"])
        output_type: Output type name (e.g., "CreditClass", "TotalValue")
        csv_filename: Name of the output CSV file
    """
    # Map user-friendly output type names to API output type names
    output_type_mapping = {
        "TotalValue": "RolledUpTotalValue"
    }
    api_output_type = output_type_mapping.get(output_type, output_type)

    # Determine if this is issuer-level or bond-level output based on output_type
    is_issuer_level = "Issuer" in csv_filename
    is_bond_level = "Bond" in csv_filename

    if not is_issuer_level and not is_bond_level:
        print(f"Warning: Unknown output type '{output_type}'. Cannot determine issuer or bond level.")
        return

    # Get filename without .csv extension for matching
    filename_base = csv_filename.replace('.csv', '') if csv_filename.endswith('.csv') else csv_filename

    # Try to add the output file, handle if it already exists
    output_file = None
    try:
        output_file = sim.AddOutputFile(csv_filename)
    except Exception as e:
        """
        error_msg = str(e).lower()
        # If file already exists, find it by checking name without .csv extension
        if "already exists" in error_msg or "already exist" in error_msg:
            for existing_file in sim.OutputFiles:
                try:
                    for attr in ['Src', 'Name', 'FileName', 'File', 'Source']:
                        if hasattr(existing_file, attr):
                            try:
                                file_name = getattr(existing_file, attr)
                                file_name_base = file_name.replace('.csv', '') if isinstance(file_name, str) else str(file_name)
                                if file_name_base == filename_base:
                                    output_file = existing_file
                                    print(f"Found existing output file {csv_filename}, using it")
                                    break
                            except:
                                continue
                    if output_file:
                        break
                    if filename_base in str(existing_file):
                        output_file = existing_file
                        print(f"Found existing output file {csv_filename}, using it")
                        break
                except:
                    continue

            if output_file is None:
                print(f"Warning: Output file {csv_filename} exists but cannot be accessed, skipping")
                return
        else:
            raise
        """
        print(f"Removing output file {csv_filename}")
        sim.RemoveOutputFile(csv_filename.replace('.csv', ''))
        output_file = sim.AddOutputFile(csv_filename)

    if output_file is None:
        print(f"Warning: Could not create output file {csv_filename}")
        return

    added_count = 0

    if is_issuer_level:
        # For issuer-level outputs: extract issuer names, remove duplicates
        issuer_names = []
        for identifier in identifier_list:
            if isinstance(identifier, str):
                issuer_name = identifier.split('.')[0] if '.' in identifier else identifier
                if issuer_name not in issuer_names:
                    issuer_names.append(issuer_name)

        # Add outputs for each unique issuer
        for issuer_name in issuer_names:
            try:
                counterparty = granular_counterparties.SubModel(issuer_name)
                if counterparty is None:
                    continue

                output = counterparty.Output(api_output_type)
                if output is None:
                    continue

                selected_output = output_file.AddOutput(output)
                if selected_output is not None:
                    selected_output.NumberFormat = '0.0000'
                    added_count += 1
            except Exception:
                pass

    elif is_bond_level:
        # For bond-level outputs: split identifiers and add outputs
        for identifier in identifier_list:
            if not isinstance(identifier, str) or '.' not in identifier:
                continue

            try:
                counterparty_name, bond_name = identifier.split('.', 1)

                counterparty = granular_counterparties.SubModel(counterparty_name)
                if counterparty is None:
                    continue

                bond = counterparty.SubModel(bond_name)
                if bond is None:
                    continue

                output = bond.Output(api_output_type)
                if output is None:
                    continue

                selected_output = output_file.AddOutput(output)
                if selected_output is not None:
                    selected_output.NumberFormat = '0.0000'
                    added_count += 1
            except Exception:
                pass

    print(f"Successfully added {added_count} outputs to {csv_filename}")



def main():
    """Main entry point for the RICS API Bulk Import tool."""
    print("RICS API Bulk Import tool started.")

    # Initialize simulation
    if load_sim:
        sim.Load(Path_Infos['load_simPath'])
        # Update base parameters even when loading existing simulation
        sim.Parameter('BaseDate').Value = baseDate
        sim.Parameter('BaseEconomy').Value = baseEconomy
        print(f"Loaded simulation and updated base parameters: BaseDate={baseDate}, BaseEconomy={baseEconomy}")
    else:
        sim.Create("RICS")
        economy = sim.AddModel('Economy')
        economy.Name = baseEconomy
        sim.Parameter('BaseEconomy').Value = baseEconomy
        sim.Parameter('BaseDate').Value = baseDate
        print(f"Created {baseEconomy} economy and set base parameters")

    # Process all subfolders for GCP imports
    rics_data, rics_info, csv_portfolio_files = read_rics_files(Path_Infos['rics_gc_path'])

    model_lists = {
        'transition_matrices': [],
        'mpr_models': [],
        'zscore_models': [],
        'currency_list': [],
        'nan_warnings': [],  # Track NaN values that were replaced by defaults
        'output_data': {}  # save issuer and bond output data
    }

    if rics_data is not None:
        for subfolder, csv_files in rics_data.items():
            model_lists = process_GCP_imports(subfolder, csv_files, rics_info[subfolder], model_lists)
    else:
        print(f'No GCP files found in {Path_Infos["rics_gc_path"]}')

    ## Process portfolio imports
    non_structured_portfolio_files = read_portfolio_files(Path_Infos['rics_portfolio_path'])
    # Update portfolio files based on structured_portfolios and userDefined config
    portfolio_files = None  # Initialize to None
    if csv_portfolio_files:
        print(f"\nFound {len(csv_portfolio_files)} structured portfolio files from subfolders:")
        for subfolder, pf in csv_portfolio_files.items():
            print(f"  {subfolder} -> {pf}")

        portfolio_files = update_portfolio_files(
            csv_portfolio_files,
            non_structured_portfolio_files,
            Path_Infos['rics_portfolio_path'],
            structured_portfolios_parameters,
            userDefined_combined_structured_nonstructured_portfolios
        )
        print(f"Updated {len(portfolio_files)} portfolio files in main portfolio directory")
    else:
        # If no structured portfolios, use non-structured portfolio files
        portfolio_files = non_structured_portfolio_files

    if portfolio_files is not None and len(portfolio_files) > 0:
        model_lists['currency_list'] = process_portfolio_imports(Path_Infos['rics_portfolio_path'], portfolio_files, model_lists['currency_list'], keep_existing_portfolios)
    else:
        print(f'No portfolio files found in {Path_Infos["rics_portfolio_path"]}')



    print(f'*********Models to be imported*********')
    print(set(model_lists['currency_list']))
    print(set(model_lists['transition_matrices']))
    print(set(model_lists['mpr_models']))
    print(set(model_lists['zscore_models']))

    # Remove baseEconomy from currency_list if present
    if baseEconomy in model_lists['currency_list']:
        model_lists['currency_list'] = [c for c in model_lists['currency_list'] if c != baseEconomy]

    for key in model_lists.keys():
        if key == 'currency_list':
            if baseEconomy in model_lists[key]:
                model_lists[key] = [c for c in model_lists[key] if c != baseEconomy]
        elif key in ['transition_matrices', 'mpr_models', 'zscore_models']:
            if 'Base' in model_lists[key]:
                model_lists[key] = [m for m in model_lists[key] if m != 'Base']

    if import_economies and len(model_lists['currency_list']) > 0:
        import_models(model_lists['currency_list'], 'Economy')
    else:
        print(f'No new economies to import')
    if import_transition_matrices and len(model_lists['transition_matrices']) > 0:
        import_models(model_lists['transition_matrices'], 'TransitionMatrix')
    else:
        print(f'No new transition matrices to import')
    if import_mpr_models and len(model_lists['mpr_models']) > 0:
        import_models(model_lists['mpr_models'], 'MPR')
    else:
        print(f'No new MPR models to import')
    if import_zscore_models and len(model_lists['zscore_models']) > 0:
        import_models(model_lists['zscore_models'], 'ZScoreCreditCycle')
    else:
        print(f'No new Z-Score models to import')

    # Generate BHO files for outputs
    data_to_output, bho_output_files = generate_output_bho_files(model_lists, Selection, Outputs, bho_output_path)

    # Import BHO output files
    if bho_output_files:
        print(f"Importing {len(bho_output_files)} output file(s)...")
        success_count = 0

        for bho_output_file in bho_output_files:
            file_path = os.path.abspath(os.path.join(bho_output_path, bho_output_file))
            file_name = os.path.basename(bho_output_file)
            try:
                sim.ImportOutputFiles(String(file_path), DuplicateImportAction.Overwrite)
                print(f"  Successfully imported {file_name}")
                success_count += 1
            except Exception as e:
                print(f"  Error importing {file_name}: {e}")

        print(f"Imported {success_count}/{len(bho_output_files)} output file(s)")

    """
    # Add outputs to simulation
    # Find Assets -> GranularCounterparties
    assets = sim.FindModels('Assets')[0]
    granular_counterparties = assets.SubModel('GranularCounterparties')

    count = 0
    for output_type in Outputs:
        if output_type in ["CreditClass", "DefaultFlag"]:
            outputfile = f"Issuer_{output_type}.csv"
        else:
            outputfile = f"Bond_{output_type}.csv"

        identifier_list = data_to_output[count]

        if identifier_list:
            add_outputs(sim, granular_counterparties, identifier_list, output_type, outputfile)
        else:
            print(f"Warning: No identifiers found for {output_type}, skipping output addition")

        count += 1
    """

    # Save simulation
    sim.Save(Path_Infos['outputPath'])
    print(f"Simulation saved to: {Path_Infos['outputPath']}")

    # Save issuer and child model import summary
    if 'issuer_counts' in model_lists and model_lists['issuer_counts']:
        summary_file = Path_Infos['outputPath'].replace('.bhs', '_import_summary.txt')
        with open(summary_file, 'w') as f:
            f.write("=" * 60 + "\n")
            f.write("RICS Bulk Import - Import Summary\n")
            f.write("=" * 60 + "\n\n")

            # Write import information
            f.write("Models Imported:\n")
            f.write("-" * 60 + "\n")
            total_issuers = 0
            total_child_models = 0
            for subfolder in model_lists['issuer_counts'].keys():
                issuer_count = model_lists['issuer_counts'].get(subfolder, 0)
                child_count = model_lists['child_model_counts'].get(subfolder, 0)
                f.write(f"{subfolder}:\n")
                f.write(f"  Issuers: {issuer_count}\n")
                f.write(f"  Instruments (Child Models): {child_count}\n")
                f.write("\n")
                total_issuers += issuer_count
                total_child_models += child_count
            f.write("-" * 60 + "\n")
            f.write(f"Total issuers imported: {total_issuers}\n")
            f.write(f"Total instruments (child models) imported: {total_child_models}\n")
            f.write("=" * 60 + "\n\n")

            # Write NaN warnings if any
            if 'nan_warnings' in model_lists and model_lists['nan_warnings']:
                f.write("Warnings - NaN Values Replaced by Defaults:\n")
                f.write("-" * 60 + "\n")
                # Group by column name
                warnings_by_column = {}
                for col_name, model_name in model_lists['nan_warnings']:
                    if col_name not in warnings_by_column:
                        warnings_by_column[col_name] = []
                    warnings_by_column[col_name].append(model_name)

                for col_name, model_names in sorted(warnings_by_column.items()):
                    f.write(f"Column '{col_name}': {len(model_names)} models with NaN/None values\n")
                    f.write(f"  Default value was used instead\n")
                    # Show first 10 model names
                    if len(model_names) <= 10:
                        for model_name in model_names:
                            f.write(f"    - {model_name}\n")
                    else:
                        for model_name in model_names[:10]:
                            f.write(f"    - {model_name}\n")
                        f.write(f"    ... and {len(model_names) - 10} more\n")
                    f.write("\n")
                f.write("=" * 60 + "\n")
        print(f"\nImport summary saved to: {summary_file}")
        print(f"Total issuers imported: {total_issuers}")
        print(f"Total instruments (child models) imported: {total_child_models}")



# ---------------------------------------------------------------------------
# run() entry point + SG injection
# ---------------------------------------------------------------------------

from pit.shared.config import require
from pit.importer import sg_api

REQUIRED_KEYS = [
    "paths.runtime_config",
    "paths.assembly_path",
    "paths.output_path",
    "settings.base_date",
    "settings.base_economy",
]


def _bind_sg(sg):
    """Bind SG handles into module globals so the existing functions can use them."""
    global sim, BulkImporter, ParameterSetImporter, DuplicateImportAction, String, File
    sim = sg.sim
    BulkImporter = sg.BulkImporter
    ParameterSetImporter = sg.ParameterSetImporter
    DuplicateImportAction = sg.DuplicateImportAction
    String = sg.String
    File = sg.File


def run(config: dict) -> None:
    require(config, REQUIRED_KEYS)
    global Path_Infos, multiple_GCP_types
    global load_sim, keep_existing_portfolios, import_economies, import_transition_matrices
    global import_mpr_models, import_zscore_models, baseDate, baseEconomy
    global structured_portfolios_parameters, userDefined_combined_structured_nonstructured_portfolios
    global Outputs, Selection, bho_output_path
    # --- BEGIN: config parsing copied verbatim from the original module block ---
    Path_Infos = {
        "runtime_config": config['paths']['runtime_config'],
        "assembly_path": config['paths']['assembly_path'],
        "dataPath": config['paths']['data_path'],
        "modelPath": config['paths']['model_path'],
        "licencePath": config['paths']['licence_path'],
        "rics_gc_path": os.path.join(config['paths']['rics_path'], 'granularCounterparty'),
        "rics_portfolio_path": os.path.join(config['paths']['rics_path'], 'portfolio'),
        "outputPath": config['paths']['output_path'],
        "load_simPath": config['paths']['load_sim_path']
    }

    multiple_GCP_types = config['multiple_gcp_types']

    structured_portfolios_parameters = config['structured_portfolios_parameters']
    userDefined_combined_structured_nonstructured_portfolios = config['userDefined_combined_structured_nonstructured_portfolios']

    # Settings
    load_sim = config['settings']['load_sim']
    # only works when load_sim is true and files can be found in portfolio
    keep_existing_portfolios = config['settings']['keep_existing_portfolios']
    import_economies = config['settings']['import_economies']
    import_transition_matrices = config['settings']['import_transition_matrices']
    import_mpr_models = config['settings']['import_mpr_models']
    import_zscore_models = config['settings']['import_zscore_models']
    baseDate = config['settings']['base_date']
    baseEconomy = config['settings']['base_economy']

    Outputs, Selection = normalize_output_config(config)
    bho_output_path = config['paths']['rics_path']
    # --- END copied block ---
    sg = sg_api.init_sg(
        runtime_config=Path_Infos["runtime_config"],
        assembly_path=Path_Infos["assembly_path"],
        model_path=Path_Infos["modelPath"],
        data_path=Path_Infos["dataPath"],
        licence_path=Path_Infos["licencePath"],
    )
    _bind_sg(sg)
    if multiple_GCP_types:  # Check if not None and not empty
        print("Starting to merge multiple folders for a single granular counterparty type...")
        for folder, types in multiple_GCP_types.items():
            merge_folders_to_base(Path_Infos['rics_gc_path'], folder, types)
    else:
        print("No multiple GCP types configured - skipping folder merge")
    main()


if __name__ == "__main__":
    import os
    from pit.shared.config import load_config
    run(load_config(os.environ.get("RICS_CONFIG_PATH", "config.yaml")))
