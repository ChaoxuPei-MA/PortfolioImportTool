import pandas as pd
from pathlib import Path
from typing import Dict, Optional
import glob


def load_user_data(data_types: list, file_types: list, user_data_path: str) -> Dict[str, Dict[str, Optional[pd.DataFrame]]]:
    """
    Read CSV files from UserData directory and organize them by data type.
    Args:
        data_types (list): List of data types to load
        file_types (list): List of file types to load
        user_data_path (str): Path to the UserData directory
    Returns:
        dict: Nested dictionary with structure:
            {
                "GC": {
                    "issuers": DataFrame or None,
                    "instruments": DataFrame or None,
                    "pd": DataFrame or None,
                    "lgd": DataFrame or None,
                    "cashflow": DataFrame or None,
                    "portfolio": DataFrame or None
                },
                "CRE": {...},
                "Agency_MBS": {...}
            }
    """

    # Convert to Path object
    user_data_dir = Path(user_data_path)
    
    if not user_data_dir.exists():
        print(f"Error: UserData directory not found at {user_data_path}")
        return {}
    
    print(f"Loading data from: {user_data_dir}")
    print(f"Data types to process: {data_types}\n")
    
    # Initialize result dictionary
    result = {}
    # Process each data type
    for data_type in data_types:
        # Normalize data_type to uppercase for consistency
        data_type_normalized = data_type.upper()
        print(f"Processing data type: {data_type} (normalized to: {data_type_normalized})")
        result[data_type_normalized] = {}
        
        # Try both the main directory and a subdirectory named after the data type
        # Also try original case and normalized case for subdirectory
        search_dirs = [
            user_data_dir,  # Main directory
            user_data_dir / data_type,  # Subdirectory with original data type name
            user_data_dir / data_type_normalized,  # Subdirectory with normalized name
        ]
        
        for file_type in file_types:
            # Try different naming conventions with both original and normalized data type
            possible_filenames = [
                # With normalized (uppercase) data type
                f"{data_type_normalized}_{file_type}.csv",
                f"{data_type_normalized}_{file_type}s.csv",  # plural
                f"{data_type_normalized}_{file_type.capitalize()}.csv",
                f"{data_type_normalized}_{file_type.capitalize()}s.csv",  # plural with capital
                f"{data_type_normalized}_{file_type.upper()}.csv",
                f"{data_type_normalized}_{file_type.upper()}s.csv",  # plural uppercase
                # With original data type (for backward compatibility)
                f"{data_type}_{file_type}.csv",
                f"{data_type}_{file_type}s.csv",  # plural
                f"{data_type}_{file_type.capitalize()}.csv",
                f"{data_type}_{file_type.capitalize()}s.csv",  # plural with capital
                f"{data_type}_{file_type.upper()}.csv",
                f"{data_type}_{file_type.upper()}s.csv",  # plural uppercase
                # Also try without data_type prefix (for files in subdirectories)
                f"{file_type}.csv",
                f"{file_type}s.csv",  # plural
                f"{file_type.capitalize()}.csv",
                f"{file_type.capitalize()}s.csv",  # plural with capital
                f"{file_type.upper()}.csv",
                f"{file_type.upper()}s.csv",  # plural uppercase
            ]
            
            # Special handling: also search for files that contain the file_type in the name
            # (e.g., GCCRE_GeographyPropertyfactors.csv for "factors")
            pattern_matches = []
            for search_dir in search_dirs:
                if search_dir.exists():
                    # Look for files containing the file_type in their name (with both cases)
                    for dt in [data_type_normalized, data_type]:
                        search_pattern = f"{dt}_*{file_type}*.csv"
                        matches = list(search_dir.glob(search_pattern))
                        if matches:
                            pattern_matches.extend([m.name for m in matches])
            
            # Add pattern matches to possible filenames
            possible_filenames.extend(pattern_matches)
            
            # Try to find and load the file
            df_loaded = False
            for search_dir in search_dirs:
                if not search_dir.exists():
                    continue
                    
                for filename in possible_filenames:
                    file_path = search_dir / filename
                    if file_path.exists():
                        try:
                            df = pd.read_csv(file_path)
                            result[data_type_normalized][file_type] = df
                            print(f"  [+] Loaded {filename} ({len(df)} rows, {len(df.columns)} columns)")
                            df_loaded = True
                            break
                        except Exception as e:
                            print(f"  [X] Error reading {filename}: {str(e)}")
                            result[data_type_normalized][file_type] = None
                            df_loaded = True
                            break
                
                if df_loaded:
                    break
            
            if not df_loaded:
                result[data_type_normalized][file_type] = None
                print(f"  - {file_type}: Not found (set to None)")
        
        print()  # Empty line between data types
    
    # Print summary
    print("="*70)
    print("SUMMARY")
    print("="*70)
    for data_type, files in result.items():
        loaded_count = sum(1 for v in files.values() if v is not None)
        total_count = len(files)
        print(f"{data_type}: {loaded_count}/{total_count} files loaded")
        for file_type, df in files.items():
            if df is not None:
                print(f"  - {file_type}: {len(df)} rows")
    print("="*70)
    
    return result


def print_data_structure(data: Dict[str, Dict[str, Optional[pd.DataFrame]]]):
    print("\n" + "="*70)
    print("DETAILED DATA STRUCTURE")
    print("="*70)
    
    for data_type, files in data.items():
        print(f"\n{data_type}:")
        for file_type, df in files.items():
            if df is not None:
                print(f"  {file_type}:")
                print(f"    - Shape: {df.shape}")
                print(f"    - Columns: {list(df.columns)[:10]}")  # Show first 10 columns
                if len(df.columns) > 10:
                    print(f"      ... and {len(df.columns) - 10} more columns")
            else:
                print(f"  {file_type}: None")


def load_mapping_tables(mapping_file, mapping_tables):
    """
    Load mapping tables from Excel file and return a dictionary of DataFrames
    """
    mapping_data = {}
    for table, sheet_name in mapping_tables.items():
        mapping_data[table] = pd.read_excel(mapping_file, sheet_name=sheet_name)
    return mapping_data