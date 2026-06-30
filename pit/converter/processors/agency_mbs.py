"""
Agency MBS (Mortgage-Backed Securities) Data Processing Class
Handles processing and transformation of Agency MBS data for RICS import
"""

import pandas as pd
from typing import Optional, Dict
from pit.converter.processors.convert_to_rics import *


class AgencyMBS:
    """
    Class for processing Agency MBS (Mortgage-Backed Securities) data.
    """
    
    def __init__(self, type: str, data: Dict[str, Optional[pd.DataFrame]], rics_import_format: str, output_path: str):

        self.type = type
        self.issuers = data.get('issuers')
        self.laggard = data.get('laggard')
        self.instruments = data.get('instruments')

        self.rics_import_format = rics_import_format

        self.output_path = os.path.join(output_path, self.type)
        os.makedirs(self.output_path, exist_ok=True)
        
        # Store removed instruments (SurvivalFactor == 0) for portfolio filtering
        self.removed_instruments = []
        
        self._validate_data()
    
    def _validate_data(self):
        """
        Validate that required data is present.
        """
        if self.issuers is None:
            raise ValueError("Agency MBS: Issuers data is required")
        if self.laggard is None:
            raise ValueError("Agency MBS: Laggard data is required")
        if self.instruments is None:
            raise ValueError("Agency MBS: Instruments data is required")
    
    def process_issuers(self) -> pd.DataFrame:
        processed = self.issuers.copy()
        processed.rename(columns={"counterpartyName": "Name"}, inplace=True)

        self.issuers = create_dataframe_from_columns("AgencyMBSIssuer", self.rics_import_format, processed)

        laggard_processed = self.laggard.copy()
        laggard_processed.rename(columns={"counterpartyName": "Name"}, inplace=True)
        laggard_processed['ParameterSetIndex'] = laggard_processed.groupby('Name').cumcount() + 1

        self.laggard = create_dataframe_from_columns("LaggardDistributionParameterSet", self.rics_import_format, laggard_processed)


    
    def process_instruments(self) -> pd.DataFrame:
        processed = self.instruments.copy()
        
        # Identify and save instruments with SurvivalFactor == 0 before filtering
        if 'SurvivalFactor' in processed.columns:
            removed_df = processed[processed['SurvivalFactor'] == 0].copy()
            
            if not removed_df.empty:
                # Create unique instrument identifiers for filtering
                removed_df['InstrumentID'] = (
                    removed_df['counterpartyName'].astype(str) + '.' + 
                    removed_df['instrumentName'].astype(str)
                )
                self.removed_instruments = removed_df['InstrumentID'].unique().tolist()
                print(f"  Found {len(self.removed_instruments)} instruments with SurvivalFactor == 0 (will be excluded)")
        
        # Filter out instruments with SurvivalFactor == 0
        processed = processed[processed['SurvivalFactor'] != 0]
        print(f"  Filtered instruments: Removed {len(self.instruments) - len(processed)} instruments. Remaining: {len(processed)}")

        processed['Name'] = processed['counterpartyName'] + "." + processed['instrumentName']

        self.instruments = create_dataframe_from_columns("ChildMBS", self.rics_import_format, processed)

        childModelTypes = processed[['Name']].copy()
        childModelTypes['Type'] = "MBS"

        childModelTypes_processed = create_dataframe_from_columns("ChildModelTypes", self.rics_import_format, childModelTypes)

        return childModelTypes_processed
    
    def save_data(self, data):
        self.issuers.to_csv(os.path.join(self.output_path, f'{self.type}Issuer.csv'), index=False)
        self.laggard.to_csv(os.path.join(self.output_path, f'{self.type}Issuer_LaggardDistributionParameterSet.csv'), index=False)
        self.instruments.to_csv(os.path.join(self.output_path, f'{self.type}IssuerChildMBS.csv'), index=False)
        data.to_csv(os.path.join(self.output_path, f'{self.type}IssuerChildModelTypes.csv'), index=False)


    
    def get_summary(self) -> Dict:
        """
        Get summary statistics of the Agency MBS data.
        
        Returns:
            dict: Summary statistics
        """
        summary = {
            'data_type': 'Agency_MBS',
            'num_issuers': len(self.issuers) if self.issuers is not None else 0,
            'num_instruments': len(self.instruments) if self.instruments is not None else 0,
            'removed_instruments': self.removed_instruments,
            'num_removed_instruments': len(self.removed_instruments),
        }
        return summary
    
    def run(self):
        """
        Run the Agency MBS processing.
        """
        print('\n' + 'Agency MBS processing started...')
        self.process_issuers()
        childModelTypes = self.process_instruments()
        summary = self.get_summary()
        print(summary)

        self.save_data(childModelTypes)

        print('\n' + 'Agency MBS processing completed.\n')
        return summary

