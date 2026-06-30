#### Read all CSV files in all subfolders of RICS_Files
import os
import glob
import re
import shutil
import pandas as pd
import sys
import time

from pit.importer.bho import BHOFileGenerator

def find_matching_patterns(filename):
    """Find files that match common patterns (case-insensitive)"""
    patterns = [
        'industry',
        'childmodeltypes', 
        'childbond',
        'childfrn',
        'childamortisingbond',
        'childamortisingfrn',
        'childbond_lgdmean',
        'childfrn_lgdmean',
        'childamortisingbond_lgdmean',
        'childamortisingfrn_lgdmean',
        'childbond_lgdk',
        'childfrn_lgdk',
        'childamortisingbond_lgdk',
        'childamortisingfrn_lgdk',
        'childamortisingbond_principalpayment',
        'childamortisingfrn_principalpayment',
        'childamortisingbond_couponpayment',
        'geographyloadings',
        'propertytypeloadings',
        'regionloadings',
        'producttypeloadings',
        'pdtermstructure'
    ]
    
    matching_patterns = []
    for pattern in patterns:
        if pattern in filename.lower():
            matching_patterns.append(pattern)
    return matching_patterns

def normalize_duplicate_columns(df):
    """
    Normalize duplicate columns in a DataFrame:
    - ZScoreModel and Z-ScoreModel -> keep Z-ScoreModel
    - MPR and MPRModel -> keep MPRModel
    
    Note: Coupon vs CouponCurve are NOT duplicates - they are used in different file types:
    - Bond files use 'Coupon' 
    - FRN files use 'CouponCurve'
    """
    # ZScoreModel and Z-ScoreModel are the same
    if 'ZScoreModel' in df.columns and 'Z-ScoreModel' in df.columns:
        # Fill empty Z-ScoreModel with ZScoreModel values
        df['Z-ScoreModel'] = df['Z-ScoreModel'].fillna(df['ZScoreModel'])
        df = df.drop(columns=['ZScoreModel'])
    elif 'ZScoreModel' in df.columns:
        # Rename ZScoreModel to Z-ScoreModel for consistency
        df = df.rename(columns={'ZScoreModel': 'Z-ScoreModel'})
    
    # MPR and MPRModel are the same
    if 'MPR' in df.columns and 'MPRModel' in df.columns:
        # Fill empty MPRModel with MPR values
        df['MPRModel'] = df['MPRModel'].fillna(df['MPR'])
        df = df.drop(columns=['MPR'])
    elif 'MPR' in df.columns:
        # Rename MPR to MPRModel for consistency
        df = df.rename(columns={'MPR': 'MPRModel'})
    
    return df

def merge_csv_files(source_file, target_file):
    """Merge two CSV files by concatenating rows and consolidating duplicate columns"""
    try:
        df_source = pd.read_csv(source_file)
        df_target = pd.read_csv(target_file)
        
        # Normalize duplicate columns in both dataframes
        df_source = normalize_duplicate_columns(df_source)
        df_target = normalize_duplicate_columns(df_target)
        
        df_merged = pd.concat([df_target, df_source], ignore_index=True)
        df_merged.to_csv(target_file, index=False)
        print(f"  Merged {os.path.basename(source_file)} -> {os.path.basename(target_file)}")
        return True
    except Exception as e:
        print(f"  Error merging {source_file} into {target_file}: {e}")
        return False

def clean_filename(filename):
    """Remove model type suffixes from filename"""
    model_suffixes = ['_CLO', '_CRE', '_RETAIL', '_SOV']
    for suffix in model_suffixes:
        if suffix + '.csv' in filename:
            cleaned = filename.replace(suffix + '.csv', '.csv')
            print(f"    Removed suffix '{suffix}' from {filename}")
            return cleaned
    return filename

def copy_file_with_log(source_file, target_path, log_message):
    """Copy file and log the operation"""
    shutil.copy2(source_file, target_path)
    print(f"    {log_message}")

def copy_csv_with_normalization(source_file, target_path, log_message):
    """Copy CSV file and normalize duplicate columns"""
    try:
        if source_file.lower().endswith('.csv'):
            df = pd.read_csv(source_file)
            df = normalize_duplicate_columns(df)
            df.to_csv(target_path, index=False)
            print(f"    {log_message} (normalized columns)")
        else:
            # For non-CSV files, just copy
            shutil.copy2(source_file, target_path)
            print(f"    {log_message}")
    except Exception as e:
        # If normalization fails, fall back to regular copy
        print(f"    Warning: Could not normalize {os.path.basename(source_file)}, using regular copy: {e}")
        shutil.copy2(source_file, target_path)
        print(f"    {log_message}")

def process_files_no_prefix_mode(files_without_prefix, files_with_prefix, merged_folder):
    """Process files when max_prefix=0: keep non-prefixed as-is, remove prefixes from others"""
    # Copy files without prefix as-is
    if len(files_without_prefix) > 0:
        for merge_file in files_without_prefix:
            merge_fname = os.path.basename(merge_file)
            cleaned_fname = clean_filename(merge_fname)
            target_path = os.path.join(merged_folder, cleaned_fname)
            copy_csv_with_normalization(merge_file, target_path, f"Copied {merge_fname} -> {cleaned_fname} (no prefix)")
    
    # Remove prefixes from prefixed files
    if len(files_with_prefix) > 0:
        for merge_file in files_with_prefix:
            merge_fname = os.path.basename(merge_file)
            cleaned_fname = clean_filename(merge_fname)
            new_fname = re.sub(r'^\d+_', '', cleaned_fname)
            target_path = os.path.join(merged_folder, new_fname)
            copy_csv_with_normalization(merge_file, target_path, f"Copied {merge_fname} -> {new_fname} (removed prefix)")

def process_files_with_prefix_mode(files_without_prefix, files_with_prefix, merged_folder, next_prefix):
    """Process files when max_prefix>0: add prefixes to maintain consistency"""
    # Add prefixes to non-prefixed files
    if len(files_without_prefix) > 0:
        for merge_file in files_without_prefix:
            merge_fname = os.path.basename(merge_file)
            cleaned_fname = clean_filename(merge_fname)
            new_fname = f'{next_prefix}_{cleaned_fname}'
            target_path = os.path.join(merged_folder, new_fname)
            copy_csv_with_normalization(merge_file, target_path, f"Copied {merge_fname} -> {new_fname} (added prefix)")
            next_prefix += 1
    
    # Update prefixes on already-prefixed files
    if len(files_with_prefix) > 0:
        for merge_file in files_with_prefix:
            merge_fname = os.path.basename(merge_file)
            cleaned_fname = clean_filename(merge_fname)
            new_fname = re.sub(r'^\d+_', f'{next_prefix}_', cleaned_fname)
            target_path = os.path.join(merged_folder, new_fname)
            copy_csv_with_normalization(merge_file, target_path, f"Copied {merge_fname} -> {new_fname} (updated prefix)")
            next_prefix += 1
    
    return next_prefix - 1

# Sort unprocessed files by their original prefix to maintain order
def get_original_prefix(file_path):
    fname = os.path.basename(file_path)
    match = re.match(r'^(\d+)_', fname)
    return int(match.group(1)) if match else float('inf')  # Files without prefix go to end

def get_file_sort_priority(file_path):
    """Get sort priority for files - ensures proper ordering with GCP file first, then parameter sets"""
    fname = os.path.basename(file_path)
    # Remove existing prefix for comparison
    base_name = re.sub(r'^\d+_', '', fname).lower()
    
    # Priority order (return tuple for consistent sorting):
    # 1. GranularCounterparty.csv (main GCP file)
    if 'parameterset' not in base_name and 'child' not in base_name and 'holdings' not in base_name:
        return (1, 0, base_name)
    # 2. IndustryFactorLoadingsParameterSet or other Loadings parameter sets
    elif 'loadingsparameterset' in base_name:
        if 'industry' in base_name:
            return (2, 1, base_name)
        elif 'geography' in base_name:
            return (2, 2, base_name)
        elif 'property' in base_name:
            return (2, 3, base_name)
        elif 'region' in base_name:
            return (2, 4, base_name)
        elif 'product' in base_name:
            return (2, 5, base_name)
    elif 'pdtermstructureparameterset' in base_name:
        return (3, 0, base_name)
    # 3. ChildModelTypes
    elif 'childmodeltypes' in base_name:
        return (4, 0, base_name)
    # 4. Child models and their parameter sets (sorted alphabetically)
    else:
        # Extract existing prefix if any
        match = re.match(r'^(\d+)_', fname)
        if match:
            return (5, int(match.group(1)), base_name)  # Keep original prefix order within this group
        else:
            return (5, float('inf'), base_name)  # Sort alphabetically if no prefix

def remove_readonly(func, path, exc):
    """Helper function to handle read-only files during deletion"""
    os.chmod(path, 0o777)
    func(path)

def safe_remove_folder(folder_path, max_retries=3, delay=0.5):
    """Safely remove a folder with retry logic and read-only file handling"""
    if not os.path.exists(folder_path):
        return True
    
    for attempt in range(max_retries):
        try:
            # Use onerror callback to handle read-only files
            shutil.rmtree(folder_path, onerror=remove_readonly)
            return True
        except PermissionError as e:
            if attempt < max_retries - 1:
                print(f"  Warning: Permission error deleting {os.path.basename(folder_path)}, retrying in {delay}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
            else:
                print(f"  Error: Could not delete {os.path.basename(folder_path)} after {max_retries} attempts: {e}")
                return False
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"  Warning: Error deleting {os.path.basename(folder_path)}, retrying in {delay}s... (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(delay)
            else:
                print(f"  Error: Could not delete {os.path.basename(folder_path)} after {max_retries} attempts: {e}")
                return False
    return False

def archive_folders(base_dir, base_folder, base_folder_name, merge_folder_paths):
        # Move original folders to 'archive' folder
    archive_folder = os.path.join(base_dir, "archive")
    try:
        # Create archive folder if it doesn't exist
        if not os.path.exists(archive_folder):
            os.makedirs(archive_folder)
            print(f"  Created archive folder: {archive_folder}")
        
        # Move base folder to archive
        base_archive_path = os.path.join(archive_folder, base_folder_name)
        if os.path.exists(base_archive_path):
            if not safe_remove_folder(base_archive_path):
                print(f"  Warning: Could not remove existing archive folder {base_folder_name}, skipping archive")
                return
        shutil.move(base_folder, base_archive_path)
        print(f"  Moved {base_folder_name} folder to: {base_archive_path}")
        
        # Move merge folders to archive
        for merge_folder_name, merge_folder_path in merge_folder_paths:
            merge_archive_path = os.path.join(archive_folder, merge_folder_name)
            if os.path.exists(merge_archive_path):
                if not safe_remove_folder(merge_archive_path):
                    print(f"  Warning: Could not remove existing archive folder {merge_folder_name}, skipping archive for this folder")
                    continue
            shutil.move(merge_folder_path, merge_archive_path)
            print(f"  Moved {merge_folder_name} folder to: {merge_archive_path}")
        
        print("Original folders archived to 'archive' folder.")
        
    except Exception as e:
        print(f"  Warning: Could not archive original folders to 'archive': {e}")
        print(f"Original folders {base_folder_name} and {[name for name, _ in merge_folder_paths]} remain unchanged.")
    

def merge_folders_to_base(base_dir, base_folder_name, folders_to_merge):
    """
    Merge multiple folders into a base folder:
    1. Create a new '{base_folder_name}_Merged' folder with merged files
    2. Copy base folder files to the new folder first
    3. Merge/add files from other folders to the new folder
    4. Keep all original folders unchanged
    5. For 1_GCP*.csv -> concatenate to 1_Granular*.csv
    6. For other files, match by pattern (*industryfactor*, *ChildModelTypes*, etc.)
    7. Files from merge folders only: copy to new folder with updated prefix digit
    
    Args:
        base_dir: Directory containing the folders
        base_folder_name: Name of the base folder (e.g., 'GC')
        folders_to_merge: List of folder names to merge into base (e.g., ['GCP_CLO'])
    """
    # Define GCP file list at function level so it's accessible everywhere
    gcp_file_list = [
        "GranularCounterparty",
        "GranularCounterpartyWithPDTermStructure",
        "GranularCounterpartyCRE",
        "GranularCounterpartyCREWithPDTermStructure",
        "GranularCounterpartyRetail",
        "GranularCounterpartyRetailWithPDTermStructure",
        "GCP",
        "GCP_PDTS"
    ]
    
    base_folder = os.path.join(base_dir, base_folder_name)
    merged_folder = os.path.join(base_dir, f"{base_folder_name}_Merged")
    
    # Check if base folder exists
    if not os.path.isdir(base_folder):
        print(f"---Base folder {base_folder_name} not found---")
        return
    
    # Check if any merge folders exist
    merge_folder_paths = []
    for folder_name in folders_to_merge:
        folder_path = os.path.join(base_dir, folder_name)
        if os.path.isdir(folder_path):
            merge_folder_paths.append((folder_name, folder_path))
    
    if not merge_folder_paths:
        print(f"No merge folders found for {base_folder_name}")
        return
    
    print(f"Merging {[name for name, _ in merge_folder_paths]} into {base_folder_name} -> output to {merged_folder}...")
    
    # Create merged folder
    if os.path.exists(merged_folder):
        if not safe_remove_folder(merged_folder):
            raise Exception(f"Could not remove existing merged folder {merged_folder}. Please close any programs using files in this folder and try again.")
    os.makedirs(merged_folder)
    print(f"  Created output folder: {merged_folder}")
    
    # Copy all base folder files to the merged folder first, with numeric prefixes for sorting
    base_files = glob.glob(os.path.join(base_folder, "*.csv"))
    # Sort base files by priority: GCP file first, then Loadings parameter set, then others
    base_files.sort(key=get_file_sort_priority)
    prefix_num = 1
    for base_file in base_files:
        base_fname = os.path.basename(base_file)
        cleaned_fname = clean_filename(base_fname)
        # Remove existing prefix if any, then add new prefix
        cleaned_fname_no_prefix = re.sub(r'^\d+_', '', cleaned_fname)
        new_fname = f'{prefix_num}_{cleaned_fname_no_prefix}'
        target_path = os.path.join(merged_folder, new_fname)
        copy_csv_with_normalization(base_file, target_path, f"Copied {base_fname} -> {new_fname}")
        prefix_num += 1
    print(f"  Copied {len(base_files)} files from {base_folder_name} to merged folder (with prefixes 1-{prefix_num-1})")

    # Find maximum prefix number in merged folder for new file numbering
    merged_files = glob.glob(os.path.join(merged_folder, "*.csv"))
    
    # Find GCP file in merged folder after getting the file list
    merged_gcp_file = None
    for merged_file in merged_files:
        merged_fname = os.path.basename(merged_file)
        merged_base_name = re.sub(r'^\d+_', '', merged_fname.replace('.csv', ''))
        
        for gcp_pattern in gcp_file_list:
            if merged_base_name.lower() == gcp_pattern.lower():
                merged_gcp_file = merged_file
                break
        if merged_gcp_file:
            break
    

    max_prefix = 0
    for merged_file in merged_files:
        fname = os.path.basename(merged_file)
        # Extract leading digits
        match = re.match(r'^(\d+)_', fname)
        if match:
            prefix_num = int(match.group(1))
            max_prefix = max(max_prefix, prefix_num)

    # Process each merge folder
    for merge_folder_name, merge_folder_path in merge_folder_paths:
        print(f"  Processing {merge_folder_name}...")
        
        # Get all CSV files from current merge folder
        merge_files = glob.glob(os.path.join(merge_folder_path, "*.csv"))
        
        # Track processed files and used merge targets
        processed_files = set()
        used_merge_targets = set()

        # Find GCP file in merge folder
        merge_gcp_file = None
        for merge_file in merge_files:
            merge_fname = os.path.basename(merge_file)
            merge_base_name = re.sub(r'^\d+_', '', merge_fname.replace('.csv', ''))
            
            for gcp_pattern in gcp_file_list:
                if merge_base_name.lower() == gcp_pattern.lower():
                    merge_gcp_file = merge_file
                    break
            if merge_gcp_file:
                break


        # Process each file in the merge folder
        for merge_file in merge_files:
            merge_fname = os.path.basename(merge_file)
            
            # Skip Portfolio files (just copy them)
            if merge_fname.lower().startswith('portfolio'):
                target_path = os.path.join(merged_folder, merge_fname)
                shutil.copy2(merge_file, target_path)
                print(f"    Copied portfolio file: {merge_fname}")
                processed_files.add(merge_file)
                continue
            
            merged = False
            
            # Check if current file is a GCP file that should be merged with the found merged_gcp_file
            is_current_file_gcp = False
            if merge_file:
                current_merge_fname = os.path.basename(merge_file)
                current_merge_base_name = re.sub(r'^\d+_', '', current_merge_fname.replace('.csv', ''))
                
                # Remove model suffixes for comparison
                current_merge_clean = clean_filename(current_merge_base_name + '.csv').replace('.csv', '')
                
                for gcp_pattern in gcp_file_list:
                    gcp_base_name = re.sub(r'^\d+_', '', gcp_pattern.replace('.csv', ''))
                    
                    if current_merge_clean.lower() == gcp_base_name.lower() or current_merge_base_name.lower() == gcp_base_name.lower():
                        is_current_file_gcp = True
                        break
            
            if merged_gcp_file and merged_gcp_file not in used_merge_targets and is_current_file_gcp:
                if merge_csv_files(merge_file, merged_gcp_file):
                    merged = True
                    processed_files.add(merge_file)
                    used_merge_targets.add(merged_gcp_file)
                    # print(f"    Merged GCP file: {os.path.basename(merge_file)} -> {os.path.basename(merged_gcp_file)}")
            
            # If not merged yet, try pattern matching with more precise logic
            if not merged:
                merge_patterns = find_matching_patterns(merge_fname)
                
                if merge_patterns:
                    # Find merged files with matching patterns, but require more precise matching
                    best_match_file = None
                    best_match_score = 0
                    
                    # Check if merge file is a parameter set file
                    # Include issuer-level parameter sets (PDTermStructure, IndustryFactorLoadings, etc.)
                    merge_is_param_set = any(p in merge_patterns for p in [
                        'childamortisingbond_lgdmean', 'childamortisingfrn_lgdmean',
                        'childamortisingbond_lgdk', 'childamortisingfrn_lgdk',
                        'childamortisingbond_principalpayment', 'childamortisingfrn_principalpayment',
                        'childamortisingbond_couponpayment', 'childfrn_lgdmean', 'childfrn_lgdk',
                        'childbond_lgdmean', 'childbond_lgdk'
                    ]) or 'parameterset' in merge_fname.lower()
                    
                    for merged_file in merged_files:
                        if merged_file not in used_merge_targets:
                            merged_fname = os.path.basename(merged_file)
                            merged_patterns = find_matching_patterns(merged_fname)
                            
                            # Check if merged file is a parameter set file
                            # Include issuer-level parameter sets (PDTermStructure, IndustryFactorLoadings, etc.)
                            merged_is_param_set = any(p in merged_patterns for p in [
                                'childamortisingbond_lgdmean', 'childamortisingfrn_lgdmean',
                                'childamortisingbond_lgdk', 'childamortisingfrn_lgdk',
                                'childamortisingbond_principalpayment', 'childamortisingfrn_principalpayment',
                                'childamortisingbond_couponpayment', 'childfrn_lgdmean', 'childfrn_lgdk',
                                'childbond_lgdmean', 'childbond_lgdk'
                            ]) or 'parameterset' in merged_fname.lower()
                            
                            # Critical: parameter set files should only match with parameter set files
                            # and main files should only match with main files
                            if merge_is_param_set != merged_is_param_set:
                                continue  # Skip this match - one is param set, other is not
                            
                            # Calculate match score - higher score means better match
                            common_patterns = [p for p in merge_patterns if p in merged_patterns]
                            if common_patterns:
                                # Prefer more specific patterns (longer pattern names)
                                score = sum(len(p) for p in common_patterns)
                                
                                # For parameter set files, prioritize exact parameter set name matches
                                if merge_is_param_set:
                                    # Check if both files have the same parameter set name in their filenames
                                    merge_param_name = None
                                    merged_param_name = None
                                    param_names = ['pdtermstructure', 'industryfactorloadings', 'geographyloadings',
                                                  'propertytypeloadings', 'regionloadings', 'producttypeloadings',
                                                  'lgdmean', 'lgdk', 'principalpayment', 'couponpayment']
                                    for param_name in param_names:
                                        # Only extract parameter set name if it's actually in a parameter set file
                                        if param_name in merge_fname.lower() and 'parameterset' in merge_fname.lower():
                                            # For issuer-level params, make sure it's not a child model file
                                            if param_name in ['pdtermstructure', 'industryfactorloadings', 'geographyloadings',
                                                             'propertytypeloadings', 'regionloadings', 'producttypeloadings']:
                                                if 'child' not in merge_fname.lower():
                                                    merge_param_name = param_name
                                            else:
                                                # For child-level params, it's fine
                                                merge_param_name = param_name
                                        if param_name in merged_fname.lower() and 'parameterset' in merged_fname.lower():
                                            if param_name in ['pdtermstructure', 'industryfactorloadings', 'geographyloadings',
                                                             'propertytypeloadings', 'regionloadings', 'producttypeloadings']:
                                                if 'child' not in merged_fname.lower():
                                                    merged_param_name = param_name
                                            else:
                                                merged_param_name = param_name
                                    # If parameter set names match, boost the score significantly
                                    if merge_param_name == merged_param_name and merge_param_name:
                                        score += 1000
                                    # If parameter set names don't match, reduce score significantly
                                    elif merge_param_name != merged_param_name and (merge_param_name or merged_param_name):
                                        score = 0  # Don't match different parameter set types
                                
                                # Bonus for having exact child type match 
                                merge_child_type = None
                                merged_child_type = None
                                
                                for pattern in ['childamortisingbond', 'childamortisingfrn', 'childbond', 'childfrn']:
                                    if pattern in merge_fname.lower():
                                        merge_child_type = pattern
                                    if pattern in merged_fname.lower():
                                        merged_child_type = pattern
                                
                                # Only allow exact child type matches, or if no child type is involved
                                if merge_child_type == merged_child_type or (merge_child_type is None or merged_child_type is None):
                                    # For parameter set files, also check that they have the same parameter set type
                                    if merge_is_param_set:
                                        # Extract parameter set type from both files
                                        merge_param_type = None
                                        merged_param_type = None
                                        
                                        # Check for child model parameter set types
                                        for param_pattern in ['_lgdmean', '_lgdk', '_principalpayment', '_couponpayment']:
                                            if param_pattern in merge_fname.lower():
                                                merge_param_type = param_pattern
                                            if param_pattern in merged_fname.lower():
                                                merged_param_type = param_pattern
                                        
                                        # Check for issuer-level parameter set types
                                        # These should only match if "ParameterSet" is in the filename
                                        issuer_param_patterns = ['pdtermstructure', 'industryfactorloadings', 'geographyloadings', 
                                                               'propertytypeloadings', 'regionloadings', 'producttypeloadings']
                                        for param_pattern in issuer_param_patterns:
                                            # Only match if it's actually a parameter set file (has "parameterset" in name)
                                            # and not a child model file (doesn't have "child" in name)
                                            if param_pattern in merge_fname.lower() and 'parameterset' in merge_fname.lower() and 'child' not in merge_fname.lower():
                                                merge_param_type = param_pattern
                                            if param_pattern in merged_fname.lower() and 'parameterset' in merged_fname.lower() and 'child' not in merged_fname.lower():
                                                merged_param_type = param_pattern
                                        
                                        # Only match if they have the same parameter set type
                                        if merge_param_type != merged_param_type:
                                            continue
                                    
                                    # For non-parameter set files, ensure they don't match parameter set files
                                    # and that child types match exactly
                                    if not merge_is_param_set:
                                        # If one has a child type and the other doesn't, don't match
                                        if (merge_child_type is not None and merged_child_type is None) or \
                                           (merge_child_type is None and merged_child_type is not None):
                                            continue
                                        # If both have child types, they must match exactly
                                        if merge_child_type is not None and merged_child_type is not None:
                                            if merge_child_type != merged_child_type:
                                                continue
                                    
                                    if score > best_match_score:
                                        best_match_score = score
                                        best_match_file = merged_file
                    
                    if best_match_file:
                        if merge_csv_files(merge_file, best_match_file):
                            merged = True
                            processed_files.add(merge_file)
                            used_merge_targets.add(best_match_file)
            
            # If still not merged, check for exact filename match (case-insensitive)
            if not merged:
                for merged_file in merged_files:
                    if merged_file not in used_merge_targets:
                        merged_fname = os.path.basename(merged_file)
                        if merged_fname.lower() == merge_fname.lower():
                            if merge_csv_files(merge_file, merged_file):
                                merged = True
                                processed_files.add(merge_file)
                                used_merge_targets.add(merged_file)
                            break

        
        # Handle unprocessed files from this merge folder
        unprocessed_files = [f for f in merge_files if f not in processed_files]
        if unprocessed_files:
            print(f"    Processing unmatched files from {merge_folder_name}...")
            
            # Separate files with and without prefix digits
            files_with_prefix = [f for f in unprocessed_files if re.match(r'^\d+_', os.path.basename(f))]
            files_without_prefix = [f for f in unprocessed_files if not re.match(r'^\d+_', os.path.basename(f))]
            
            # Sort files with prefix by their original prefix to maintain order
            files_with_prefix.sort(key=get_original_prefix)
            
            if max_prefix == 0:
                # Case 1: No existing prefixed files - keep files as-is, remove prefixes from others  
                print(f"    No existing prefixed files detected (max_prefix=0)")
                process_files_no_prefix_mode(files_without_prefix, files_with_prefix, merged_folder)
            else:
                # Case 2: Existing prefixed files found - add prefixes to maintain consistency
                print(f"    Existing prefixed files detected (max_prefix={max_prefix})")
                next_prefix = max_prefix + 1
                max_prefix = process_files_with_prefix_mode(files_without_prefix, files_with_prefix, merged_folder, next_prefix)
    
    print(f"*****Merge completed! Output saved to: {merged_folder}*****")
    
    # Move original folders to 'archive' folder
    archive_folders(base_dir, base_folder, base_folder_name, merge_folder_paths)

    print(f"*****archived original folders*****")
    
    return merged_folder




def read_rics_files(base_dir):
    """
    Read all CSV files from all subfolders of RICS_Files directory.
    Args:
        base_dir (str): Base directory path containing subfolders with CSV files
    Returns:
        dict: Dictionary where keys are subfolder names and values are dictionaries 
              containing CSV data with filename as key and pandas DataFrame as value
    """
    result_dict = {}
    subfolder_info_dict = {}
    csv_portfolio_files = {}  # Dictionary: {subfolder_name: portfolio_file_path}
    
    # Check if base directory exists
    if not os.path.exists(base_dir):
        print(f"Directory {base_dir} does not exist!")
        return result_dict, subfolder_info_dict, csv_portfolio_files
    
    # Get all subdirectories in RICS_Files
    subfolders = [f for f in os.listdir(base_dir) 
                  if os.path.isdir(os.path.join(base_dir, f))]
    # Remove 'archive' from subfolders if present
    for folder_to_remove in ["archive"]:
        if folder_to_remove in subfolders:
            subfolders.remove(folder_to_remove)

    
    print(f"Found subfolders: {subfolders}")
    
    for subfolder in subfolders:
        subfolder_path = os.path.join(base_dir, subfolder)
        csv_files = glob.glob(os.path.join(subfolder_path, "*.csv"))

        # Only collect Portfolio_*.csv files directly in subfolder (not in portfolio subfolder)
        portfolio_files_in_folder = glob.glob(os.path.join(subfolder_path, "Portfolio_*.csv"))
        
        # Map subfolder to portfolio file(s) - if multiple files, use the first one
        if portfolio_files_in_folder:
            if subfolder.lower() == "gcp_clo" or subfolder.lower() == "gc_merged":
                key = "Agency_CMBS"
            else:
                # Remove "PDTS" from subfolder name to create key (e.g., GCP_PDTS_CLO -> GCP_CLO)
                key = subfolder.replace("_PDTS", "").replace("PDTS_", "")
            # Use cleaned subfolder name as key, first portfolio file as value
            csv_portfolio_files[key] = portfolio_files_in_folder[0]
            print(f"  Found {len(portfolio_files_in_folder)} portfolio file(s) in {subfolder} (key: {key})")
            for pf in portfolio_files_in_folder:
                print(f"    - {os.path.basename(pf)}")
            if len(portfolio_files_in_folder) > 1:
                print(f"    Warning: Multiple portfolio files found, using first one: {os.path.basename(portfolio_files_in_folder[0])}")
        
        # Remove any files that contain "Holdings" substring
        csv_files = [f for f in csv_files if "Holdings" not in f]

        result_dict[subfolder] = csv_files
        print(f"Found {len(csv_files)} CSV files in {subfolder}")

        # Determine model type and type child based on directory name
        if "PD" in subfolder:
            pdts_flag = True
        else:
            pdts_flag = False
            
        if "RETAIL" in subfolder:
            model_type = "_RETAIL"
            
            if pdts_flag:
                typeChild = "GranularCounterpartyRetailWithPDTermStructure"
                output_type = "GCRETAILPD"
            else:   
                typeChild = "GranularCounterpartyRetail"
                output_type = "GCRETAIL"
        elif "CRE" in subfolder and "RETAIL" not in subfolder:
            model_type = "_CRE"
            if pdts_flag:
                typeChild = "GranularCounterpartyCREWithPDTermStructure"
                output_type = "GCCREPD"
            else:   
                typeChild = "GranularCounterpartyCRE"
                output_type = "GCCRE"
        elif "CLO" in subfolder or subfolder in ["GC", 'GC_Merged', "GCPD", "GCPD_Merged"]:
            if subfolder in ["GC", 'GC_Merged','GCPD', 'GCPD_Merged']:
                model_type = ""
            else:
                model_type = "_CLO"
            if pdts_flag:
                typeChild = "GranularCounterpartyWithPDTermStructure"
                output_type = "GCPD"
            else:
                typeChild = "GranularCounterparty"
                output_type = "GC"
        elif "MBS" in subfolder:
            model_type = "AgencyMBS"
            output_type = "MBS"
            typeChild = "AgencyMBSIssuer"
        elif "Sovereign" in subfolder or "SOV" in subfolder.upper(): ## need to check in the future
            model_type = "_SOV"
            if pdts_flag:
                typeChild = "GranularCounterpartySovereignWithPDTermStructure"
                output_type = "GCSOVPD"
            else:   
                typeChild = "GranularCounterpartySovereign"
                output_type = "GCSOV"
        else:
            # Default case for unrecognized subfolders
            model_type = ""
            output_type = ""
            typeChild = ""
            
        # Store metadata for this subfolder
        subfolder_info_dict[subfolder] = {
            'pdts_flag': pdts_flag,
            'model_type': model_type,
            'output_type': output_type,
            'typeChild': typeChild
            }

    return result_dict, subfolder_info_dict, csv_portfolio_files


def read_portfolio_files(base_dir):

    result_dict = []
    # Check if base directory exists
    if not os.path.exists(base_dir):
        print(f"Directory {base_dir} does not exist!")
        return result_dict

    csv_files = glob.glob(os.path.join(base_dir, "*.csv"))
    result_dict.extend(csv_files)
    print(f"Found {len(csv_files)} CSV files in {base_dir}")

    return result_dict


def generate_output_bho_files(model_lists, Selection, Outputs, bho_output_path):
    """
    Generate BHO files for issuer and bond level outputs based on selection criteria.
    
    Args:
        model_lists: Dictionary containing output_data with keys and data
        Selection: List of lists specifying what to include, e.g., [["All"], ["GC","GCCRE"]]
        Outputs: List of output types to generate, e.g., ["CreditClass", "TotalValue"]
        bho_output_path: Directory path for output BHO files
    
    Note:
        MBS does not support CreditClass, DefaultFlag, TotalValue, or Recovery outputs.
        If the output type is one of these and selection is "All" or "MBS", MBS data will be excluded.
    """
    # Early return if outputs or selection is empty - no output will be generated
    if not Outputs:
        print("No output types specified - skipping output generation")
        return [], []
    
    if not Selection:
        print("No selection criteria specified - skipping output generation")
        return [], []
    
    # Define restricted output types for MBS
    MBS_RESTRICTED_OUTPUTS = ['CreditClass', 'DefaultFlag', 'TotalValue', 'Recovery']
    
    data_to_output = []
    mbs_identifiers_tracking = []  # Track which identifiers are MBS for each selection item
    # For each item in Selection, create a separate data_to_output list
    # Selection is a list of lists, e.g., [["All"], ["GC","GCCRE"]]
    # Selection and Outputs are paired by index: Selection[0] pairs with Outputs[0]
    # We need to collect the identifiers from output_data and flatten them
    for idx, selection_item in enumerate(Selection):
        # Get the corresponding output type for this selection
        output_type = Outputs[idx] if idx < len(Outputs) else None
        # Check if this output type is restricted for MBS
        is_restricted_for_mbs = output_type in MBS_RESTRICTED_OUTPUTS if output_type else False
        
        item_data = []
        mbs_identifiers = set()  # Track MBS identifiers for this selection item
        if isinstance(selection_item, list):
            if "All" in selection_item:
                # If "All" is in the list, add all identifiers from output_data
                # But exclude MBS if output type is restricted
                for key, data in model_lists['output_data'].items():
                    # Skip MBS if output type is restricted
                    if is_restricted_for_mbs and key == "MBS":
                        print(f"  Skipping MBS data for restricted output type: {output_type}")
                        continue
                    # Track MBS identifiers for non-restricted outputs
                    is_mbs_key = (key == "MBS")
                    # data is a list, so extend instead of append to flatten
                    if isinstance(data, list):
                        item_data.extend(data)
                        if is_mbs_key:
                            mbs_identifiers.update(data)
                    elif isinstance(data, str):
                        item_data.append(data)
                        if is_mbs_key:
                            mbs_identifiers.add(data)
            else:
                # Otherwise, add identifiers where key is in that list
                # But exclude MBS if output type is restricted and MBS is in selection
                for key, data in model_lists['output_data'].items():
                    if key in selection_item:
                        # Skip MBS if output type is restricted
                        if is_restricted_for_mbs and key == "MBS":
                            print(f"  Skipping MBS data for restricted output type: {output_type}")
                            continue
                        # Track MBS identifiers for non-restricted outputs
                        is_mbs_key = (key == "MBS")
                        # data is a list, so extend instead of append to flatten
                        if isinstance(data, list):
                            item_data.extend(data)
                            if is_mbs_key:
                                mbs_identifiers.update(data)
                        elif isinstance(data, str):
                            item_data.append(data)
                            if is_mbs_key:
                                mbs_identifiers.add(data)
        else:
            # If selection item is a string (for backward compatibility)
            if selection_item == "All":
                for key, data in model_lists['output_data'].items():
                    # Skip MBS if output type is restricted
                    if is_restricted_for_mbs and key == "MBS":
                        print(f"  Skipping MBS data for restricted output type: {output_type}")
                        continue
                    # Track MBS identifiers for non-restricted outputs
                    is_mbs_key = (key == "MBS")
                    # data is a list, so extend instead of append to flatten
                    if isinstance(data, list):
                        item_data.extend(data)
                        if is_mbs_key:
                            mbs_identifiers.update(data)
                    elif isinstance(data, str):
                        item_data.append(data)
                        if is_mbs_key:
                            mbs_identifiers.add(data)
            else:
                for key, data in model_lists['output_data'].items():
                    if key == selection_item:
                        # Skip MBS if output type is restricted
                        if is_restricted_for_mbs and key == "MBS":
                            print(f"  Skipping MBS data for restricted output type: {output_type}")
                            continue
                        # Track MBS identifiers for non-restricted outputs
                        is_mbs_key = (key == "MBS")
                        # data is a list, so extend instead of append to flatten
                        if isinstance(data, list):
                            item_data.extend(data)
                            if is_mbs_key:
                                mbs_identifiers.update(data)
                        elif isinstance(data, str):
                            item_data.append(data)
                            if is_mbs_key:
                                mbs_identifiers.add(data)
        data_to_output.append(item_data)
        mbs_identifiers_tracking.append(mbs_identifiers)
    
    bho_output_files = []
    count = 0
    for output_type in Outputs:
        # Safety check: ensure we have selection data for this output
        if count >= len(data_to_output):
            print(f"Warning: No selection data available for output type '{output_type}' (index {count}) - skipping")
            count += 1
            continue
            
        if output_type in ['CreditClass', 'DefaultFlag']:
            # issuer level output
            # data_to_output[count] is now a flat list of identifiers
            issuer_ids = []
            current_item = data_to_output[count]
            if isinstance(current_item, list):
                for identifier in current_item:
                    if isinstance(identifier, str):
                        # If string contains a dot (e.g., "11A.1a"), extract issuer part
                        if '.' in identifier:
                            issuer_id = identifier.split('.')[0]
                            if issuer_id not in issuer_ids:
                                issuer_ids.append(issuer_id)
                        else:
                            # If no dot (e.g., "GC"), use as is
                            if identifier not in issuer_ids:
                                issuer_ids.append(identifier)
            
            if not issuer_ids:
                count += 1
                continue
            
            count += 1
            generator = BHOFileGenerator(
                output_type=output_type,
                bond_ids=issuer_ids
            )
            generator.generate(output_filename=f"Issuer_{output_type}.bho", csv_filename=f"Issuer_{output_type}.csv", output_dir=bho_output_path)
            bho_output_files.append(f"Issuer_{output_type}.bho")
        elif output_type in ['TotalValue', 'Price', 'Interest', 'Principal', 'Recovery', 'TotalReturn', 'TotalReturnIndex']:
            # bond level output
            # data_to_output[count] is now a flat list of bond identifiers
            bond_ids = []
            current_item = data_to_output[count]
            if isinstance(current_item, list):
                for identifier in current_item:
                    if isinstance(identifier, str):
                        bond_ids.append(identifier)

            if not bond_ids:
                count += 1
                continue

            # Get MBS identifiers for this output (if available)
            mbs_identifiers = mbs_identifiers_tracking[count] if count < len(mbs_identifiers_tracking) else set()

            count += 1
            generator = BHOFileGenerator(
                output_type=output_type,
                bond_ids=bond_ids,
                mbs_identifiers=mbs_identifiers
            )
            generator.generate(output_filename=f"Bond_{output_type}.bho", csv_filename=f"Bond_{output_type}.csv", output_dir=bho_output_path)
            bho_output_files.append(f"Bond_{output_type}.bho")
        else:
            print(f"Invalid output type: {output_type}")
            count += 1

    return data_to_output, bho_output_files
    
