import pandas as pd
from typing import Optional, Dict

from pit.converter.processors.convert_to_rics import *
from pit.converter.processors.update_import_files import *


class GC_GCCRE_GCRETAIL:

    
    def __init__(self, type: str, start_date: str, data: Dict[str, Optional[pd.DataFrame]], GCorr_data: Dict[str, pd.DataFrame], parameters_default_values: Dict[str, str], rics_import_format: Dict[str, str], output_dir: str, mapping_data: Dict[str, pd.DataFrame], rics_version: str = "10.6"):

        self.type = type
        self.rics_version = rics_version
        self.start_date = pd.to_datetime(start_date, format='%Y%m%d')

        self.flag = "RETAIL" if "RETAIL" in type else "CRE" if "CRE" in type else "" if type == 'GC' else "SOV" if type == 'SOV' else None
        # Template suffix: for looking up column formats (GC uses _CLO template which has CountryCode)
        self.template_suffix = "_CLO" if type == 'GC' else ""
        # File suffix: for output file naming (GC has no suffix, CRE has _CRE, RETAIL has _RETAIL)
        self.file_suffix = f"_{self.flag}" if self.flag else ""

        self.issuers = data.get('issuers')
        self.factors = data.get('factors')
        self.pds = data.get('pds')
        self.instruments = data.get('instruments')
        self.lgd = data.get('lgd')
        self.cashflow = data.get('cashflows')  # Fixed: 'cashflows' not 'cashflow'
        self.couponPayments = data.get('couponPayments')

        self.GCorr_data = GCorr_data

        self.pdIssuers = None
        self.nonPdIssuers = None

        self.parameters_default_values = parameters_default_values
        self.rics_import_format = rics_import_format
        self.output_dir = output_dir

        self.mapping_data = mapping_data
        
        # Store matured instruments for portfolio filtering
        self.matured_instruments = []
        
        self._validate_data()
    
    def _validate_data(self):
        """
        Validate that required data is present.
        """
        if self.issuers is None:
            raise ValueError(f"{self.type}: Issuers data is required")
        if self.factors is None:
            raise ValueError(f"{self.type}: Factors data is required")
        if self.instruments is None:
            raise ValueError(f"{self.type}: Instruments data is required")
        if self.lgd is None:
            raise ValueError(f"{self.type}: LGD data is required")
    
    def filter_matured_instruments(self):
        """
        Filter out matured instruments (MaturityDate < start_date) from instruments, LGD, cashflow, and couponPayments.
        Returns a list of matured instrument identifiers for portfolio filtering.
        """
        if self.instruments is None or self.instruments.empty:
            print(f"  No instruments to filter for {self.type}")
            return []
        
        # Create a copy to work with
        instruments_df = self.instruments.copy()
        
        # Check if MaturityDate column exists
        if 'MaturityDate' not in instruments_df.columns:
            print(f"  Warning: MaturityDate column not found in {self.type} instruments. Skipping maturity filter.")
            return []
        
        # Convert MaturityDate to datetime, handling empty/NaN values
        instruments_df['MaturityDate'] = pd.to_datetime(instruments_df['MaturityDate'], errors='coerce')
        
        # Identify matured instruments (MaturityDate < start_date)
        matured_mask = instruments_df['MaturityDate'] < self.start_date
        matured_instruments_df = instruments_df[matured_mask].copy()
        
        if matured_instruments_df.empty:
            print(f"  No matured instruments found for {self.type}")
            return []
        
        # Create unique instrument identifiers for filtering
        # Using counterpartyName.instrumentName format
        matured_instruments_df['InstrumentID'] = (
            matured_instruments_df['counterpartyName'].astype(str) + '.' + 
            matured_instruments_df['instrumentName'].astype(str)
        )
        
        matured_instrument_ids = matured_instruments_df['InstrumentID'].unique().tolist()
        num_matured = len(matured_instrument_ids)
        
        print(f"  Found {num_matured} matured instruments in {self.type} (maturity < {self.start_date.strftime('%Y-%m-%d')})")
        
        # Filter out matured instruments from self.instruments
        non_matured_mask = ~matured_mask
        self.instruments = instruments_df[non_matured_mask].reset_index(drop=True)
        
        # Ensure InstrumentID column is not in the instruments dataframe (safety check)
        if 'InstrumentID' in self.instruments.columns:
            self.instruments = self.instruments.drop(columns=['InstrumentID'])
        
        print(f"  Removed {num_matured} matured instruments from {self.type} instruments. Remaining: {len(self.instruments)}")
        
        # Remove from LGD if exists
        if self.lgd is not None and not self.lgd.empty:
            original_lgd_count = len(self.lgd)
            lgd_df = self.lgd.copy()
            lgd_df['InstrumentID'] = (
                lgd_df['counterpartyName'].astype(str) + '.' + 
                lgd_df['instrumentName'].astype(str)
            )
            self.lgd = lgd_df[~lgd_df['InstrumentID'].isin(matured_instrument_ids)].drop(columns=['InstrumentID']).reset_index(drop=True)
            removed_lgd = original_lgd_count - len(self.lgd)
            if removed_lgd > 0:
                print(f"  Removed {removed_lgd} matured instrument records from {self.type} LGD")
        
        # Remove from cashflow if exists
        if self.cashflow is not None and not self.cashflow.empty:
            original_cashflow_count = len(self.cashflow)
            cashflow_df = self.cashflow.copy()
            cashflow_df['InstrumentID'] = (
                cashflow_df['counterpartyName'].astype(str) + '.' + 
                cashflow_df['instrumentName'].astype(str)
            )
            self.cashflow = cashflow_df[~cashflow_df['InstrumentID'].isin(matured_instrument_ids)].drop(columns=['InstrumentID']).reset_index(drop=True)
            removed_cashflow = original_cashflow_count - len(self.cashflow)
            if removed_cashflow > 0:
                print(f"  Removed {removed_cashflow} matured instrument records from {self.type} cashflows")
        
        # Remove from couponPayments if exists
        if self.couponPayments is not None and not self.couponPayments.empty:
            original_coupon_count = len(self.couponPayments)
            coupon_df = self.couponPayments.copy()
            coupon_df['InstrumentID'] = (
                coupon_df['counterpartyName'].astype(str) + '.' + 
                coupon_df['instrumentName'].astype(str)
            )
            self.couponPayments = coupon_df[~coupon_df['InstrumentID'].isin(matured_instrument_ids)].drop(columns=['InstrumentID']).reset_index(drop=True)
            removed_coupon = original_coupon_count - len(self.couponPayments)
            if removed_coupon > 0:
                print(f"  Removed {removed_coupon} matured instrument records from {self.type} couponPayments")
        
        # Store matured instruments for later use
        self.matured_instruments = matured_instrument_ids
        
        # Return list with counterpartyName and instrumentName for portfolio filtering
        matured_list = matured_instruments_df[['counterpartyName', 'instrumentName', 'MaturityDate']].to_dict('records')
        
        return matured_list


    
    def process_issuers(self) -> pd.DataFrame:

        processed = self.issuers.copy()
        processed.rename(columns={"counterpartyName": "Name","ZScoreModel":"Z-ScoreModel","MPR":"MPRModel"}, inplace=True)

        # Use template_suffix for template formatting (GC uses _CLO template which has CountryCode)
        template_flag = self.template_suffix

        if self.pds is not None and not self.pds.empty:
            pds = self.pds.copy()
            pds.rename(columns={"counterpartyName": "Name", "pd": "PD"}, inplace=True)
            pds['ParameterSetIndex'] = pds.groupby('Name').cumcount() + 1
            
            rics_pd = create_dataframe_from_columns("PDTermStructureParameterSet", self.rics_import_format, pds)
            rics_pd.drop_duplicates(inplace=True)
            rics_pd = validate_issuer_pd(rics_pd, name_col='Name', years_col='Years', pd_col='PD')
            self.pdIssuers = rics_pd['Name'].unique().tolist()

            df_nonpd = processed[~processed["Name"].isin(self.pdIssuers)].copy()
            if not df_nonpd.empty or df_nonpd is not None:
                tmp = df_nonpd[df_nonpd["CreditClass"].isna()]
                if not tmp.empty and tmp is not None:
                    print(f'Warning: CreditClass is not provided for issuers in {self.type}_Issuers_Missing_CreditClass.csv:')
                    tmp.to_csv(os.path.join(self.output_dir, f'{self.type}_Issuers_Missing_CreditClass.csv'), index=False)
                
                df_nonpd = create_dataframe_from_columns(f"GCP{template_flag}", self.rics_import_format, df_nonpd)
                df_nonpd.drop_duplicates(inplace=True)
                self.nonPdIssuers = df_nonpd['Name'].unique().tolist()

            df_pd = processed[processed["Name"].isin(self.pdIssuers)].copy()
            df_pd.drop_duplicates(inplace=True)
            
            # Check if ImpliedCreditClass exists in rics_pd before merging
            if 'ImpliedCreditClass' in pds.columns:
                df_pd = pd.merge(df_pd, pds[["Name","ImpliedCreditClass"]], on='Name', how='left')
            else:
                # Add ImpliedCreditClass column if it doesn't exist in rics_pd
                df_pd['ImpliedCreditClass'] = ''

            
            tmp = df_pd[df_pd["CreditClass"].isna()].drop_duplicates()
            if not tmp.empty and tmp is not None:
                print(f'Warning: CreditClass is not provided for issuers in {self.type}_PDTS_Issuers_Missing_CreditClass.csv:')
                tmp.to_csv(os.path.join(self.output_dir, f'{self.type}_PDTS_Issuers_Missing_CreditClass.csv'), index=False)

            # Fill ImpliedCreditClass with default value only for missing values
            # Convert string 'TRUE'/'FALSE' to proper format, handle empty/None values
            default_value = self.parameters_default_values['ImpliedCreditClass_default_value']
            mask = df_pd['ImpliedCreditClass'].isna() | (df_pd['ImpliedCreditClass'] == '')
            df_pd.loc[mask, 'ImpliedCreditClass'] = default_value
            
            # Normalize ImpliedCreditClass: convert string TRUE/FALSE to proper boolean format
            # Handle case-insensitive TRUE/FALSE strings from CSV
            df_pd['ImpliedCreditClass'] = df_pd['ImpliedCreditClass'].apply(
                lambda x: 'True' if str(x).strip().upper() == 'TRUE' or x is True 
                else 'False' if str(x).strip().upper() == 'FALSE' or x is False 
                else str(x)
            )
            
            df_pd['CreditClass'] = np.where(
                (df_pd['ImpliedCreditClass'] == 'False') & (df_pd['CreditClass'].isna()),
                self.parameters_default_values['CreditClass_default_value'],
                df_pd['CreditClass'])

            df_pd = create_dataframe_from_columns(f"GCP_PDTS{template_flag}", self.rics_import_format, df_pd)
            df_pd.drop_duplicates(inplace=True)
            
        else:
            df_nonpd = processed
            df_nonpd.drop_duplicates(inplace=True)
            
            tmp = df_nonpd[df_nonpd["CreditClass"].isna()]
            if not tmp.empty and tmp is not None:
                print(f'Warning: CreditClass is not provided for issuers in {self.type}_Issuers_Missing_CreditClass.csv:')
                tmp.to_csv(os.path.join(self.output_dir, f'{self.type}_Issuers_Missing_CreditClass.csv'), index=False)
            df_nonpd = create_dataframe_from_columns(f"GCP{template_flag}", self.rics_import_format, df_nonpd)
            df_nonpd.drop_duplicates(inplace=True)
            self.nonPdIssuers = df_nonpd['Name'].unique().tolist()

            df_pd = None
            rics_pd = None
        
        return df_nonpd, df_pd, rics_pd

    def format_pid(self, x):
            if pd.notna(x):
                x_str = str(x).replace('PID_', '')
                return x_str.zfill(6)
            return x

    def process_GCorr_Corp_Factors(self, df_gcorr, id, cols):
        cwgt_cols = [col for col in df_gcorr.columns if cols in col.lower()]
        # Transform wide to long format and filter for value == 1
        df_gcorr_cwgt = df_gcorr[[id] + cwgt_cols].melt(
            id_vars=[id], 
            value_vars=cwgt_cols,
            var_name='factors',
            value_name='weights'
        )
        return df_gcorr_cwgt
    
    def create_equal_weight_national_factors(self, counterparty_names: list) -> pd.DataFrame:
        """
        Create equal-weight factor assignments for counterparties using all national factors.
        
        Args:
            counterparty_names: List of counterparty names to assign factors to
            
        Returns:
            DataFrame with counterpartyName, factors, and weights columns
        """
        tmp_list = []
        industry_factors = self.mapping_data['countryRegion']
        industry_factors = industry_factors[industry_factors['factorcode'].str.startswith('N')]
        weights = 1.0 / len(industry_factors['factorcode'].unique())
        
        for id in counterparty_names:
            for factor in industry_factors['factorcode'].unique().tolist():
                tmp_list.append({
                    'counterpartyName': id,
                    'factors': factor,
                    'weights': weights
                })
        
        return pd.DataFrame(tmp_list)
    
    def _process_gcorr_factors_for_private_issuers(
        self,
        df_corp_public: pd.DataFrame,
        df_corp: pd.DataFrame,
        df_gcorr: pd.DataFrame,
        public_names: list,
        groupby_cols: str
    ) -> pd.DataFrame:

        # Extract GCorr info for public companies
        df_GCorr_info = df_corp_public.loc[
            df_corp_public['counterpartyName'].isin(public_names),
            [groupby_cols, 'RSQ', 'pid']
        ].copy()
        # Get all iwgt (industry weight) columns from GCorr data
        iwgt_cols = [col for col in df_gcorr.columns if 'iwgt' in col.lower()]
        # Merge with GCorr data to get industry weights
        df_GCorr_info = df_GCorr_info.merge(
            df_gcorr[['pid'] + iwgt_cols], 
            on='pid', 
            how='left'
        )
        # Remove pid column as it's no longer needed
        df_GCorr_info.drop(columns=['pid'], inplace=True)
        
        # Group by specified column(s) and calculate mean values
        df_GCorr_info = df_GCorr_info.groupby(groupby_cols).mean().reset_index()
        
        # Save GCorr factors to CSV
        df_GCorr_factors = df_GCorr_info.copy()
        """
        output_path = os.path.join(
            self.output_dir, 
            f'{self.type}_GCorr_factors_public_by_{groupby_cols}.csv'
        )
        df_GCorr_factors.to_csv(output_path, index=False)
        """
        
        return df_GCorr_factors
    
    def process_gc_issuers(self) -> pd.DataFrame:

        df_Corp = self.issuers.copy()
        df_Corp['pid'] = df_Corp['pid'].apply(self.format_pid)
        issuer_names = self.issuers['counterpartyName'].unique().tolist()

        df_industryFactors = self.factors.copy()

        groupby_cols = self.parameters_default_values['corp_private_groupby_columnName']


        # rsqs
        gcorr_rsqs = self.GCorr_data['rsqs'].copy()
        gcorr_rsqs['pid'] = gcorr_rsqs['pid'].apply(self.format_pid)

        df_Corp['public_rsq'] = np.where(
            df_Corp['pid'].isin(gcorr_rsqs['pid']),
            True,
            False
        )
        # countryCode
        df_gcorr = self.GCorr_data['factors'].copy()
        df_gcorr['pid'] = df_gcorr['pid'].apply(self.format_pid)

        df_gcorr_cwgt = self.process_GCorr_Corp_Factors(df_gcorr, 'pid', 'cwgt')
        df_gcorr_cwgt['factors'] = 'C' + df_gcorr_cwgt['factors'].str.replace('cwgt', '').str.zfill(2)
        # Filter for rows where weight equals 1
        df_gcorr_cwgt = df_gcorr_cwgt[df_gcorr_cwgt['weights'] == 1][['pid', 'factors']]

        df_Corp['public_countrycode'] = np.where(
            df_Corp['pid'].isin(df_gcorr['pid']),
            True,
            False
        )

        df_Corp['UsePublicData'] = np.where(
            (df_Corp['public_rsq'] & df_Corp['public_countrycode']),
            True,
            False
        )

        df_Corp['Sector'] = np.where(
            df_Corp['ZScoreModel'].str.contains('^(?:na|row|eur)', regex=True, case=False),
            df_Corp['ZScoreModel'].str.replace('^(?:na|row|eur)', '', regex=True, case=False),
            np.nan
        )
        
        tmp_region_map = self.mapping_data['countryRegion'].set_index('factorcode')['Region'].to_dict()

        tmp_rsqs_map = gcorr_rsqs.set_index('pid')['RSQ'].to_dict()
        tmp_countrycode_map = df_gcorr_cwgt.set_index('pid')['factors'].to_dict()

        if self.parameters_default_values['Using_GCorr_Corp_country']:
            df_Corp['CountryCode'] = np.where(
                df_Corp['public_countrycode'] ,
                df_Corp['pid'].map(tmp_countrycode_map),
                df_Corp['CountryCode']
            )
            df_Corp['region'] = np.where(
                (df_Corp['UsePublicData']) & (df_Corp['Sector'].notna()),
                df_Corp['CountryCode'].map(tmp_region_map),
                np.nan
            )
            df_Corp['ZScoreModel'] = np.where(
                (df_Corp['UsePublicData']) & (df_Corp['Sector'].notna()),
                df_Corp['region'] + df_Corp['Sector'],
                df_Corp['ZScoreModel']
            )
        else:
            df_Corp['CountryCode'] = np.where(
                df_Corp['public_countrycode'] & df_Corp['CountryCode'].isna(),
                df_Corp['pid'].map(tmp_countrycode_map),
                df_Corp['CountryCode']
            )
            df_Corp['region'] = np.where(
                (df_Corp['UsePublicData']) & (df_Corp['Sector'].notna()),
                df_Corp['CountryCode'].map(tmp_region_map),
                np.nan
            )
            df_Corp['ZScoreModel'] = np.where(
                (df_Corp['UsePublicData']) & (df_Corp['Sector'].notna()),
                df_Corp['region'] + df_Corp['Sector'],
                df_Corp['ZScoreModel']
            )

        if self.parameters_default_values['Using_GCorr_Corp_RSQ']:
            df_Corp['RSQ'] = np.where(
                df_Corp['UsePublicData'],
                df_Corp['pid'].map(tmp_rsqs_map),
                df_Corp['RSQ']
            )
        else:
            df_Corp['RSQ'] = np.where(
                df_Corp['UsePublicData'] & df_Corp['RSQ'].isna(),
                df_Corp['pid'].map(tmp_rsqs_map),
                df_Corp['RSQ']
            )
        
        # fill country code if not provided by country column
        if df_Corp['CountryCode'].isna().any():
            tmp_map = self.mapping_data['country'].set_index('TwoLetterCode')['GCorrCountryCode'].to_dict()
            df_Corp['CountryCode'] = df_Corp['CountryCode'].fillna(df_Corp['country'].map(tmp_map))

        
        # has pid and public data
        df_Corp_public = df_Corp[df_Corp['UsePublicData'] == True].copy() # public data or public country code?

        # industry factors for public data
        df_gcorr_iwgt = self.process_GCorr_Corp_Factors(df_gcorr, 'pid', 'iwgt')
        df_gcorr_iwgt = df_gcorr_iwgt[df_gcorr_iwgt['weights'] > 0][['pid', 'factors', 'weights']]
        df_gcorr_iwgt['factors'] = 'N' + df_gcorr_iwgt['factors'].str.replace('iwgt', '').str.zfill(2)
        tmp = df_Corp_public[['counterpartyName','pid']].drop_duplicates(ignore_index=True)
        factorsDF_Corp_public = pd.merge(
            tmp,
            df_gcorr_iwgt, 
            on='pid',
            how='left'
        )
        factorsDF_Corp_public = factorsDF_Corp_public[self.factors.columns].drop_duplicates()
        
        
        if self.parameters_default_values['Using_GCorr_Corp_industry']:
            public_names = factorsDF_Corp_public['counterpartyName'].unique().tolist()
            df_factors = df_industryFactors[~(df_industryFactors['counterpartyName'].isin(public_names))].copy()
            df_factors = pd.concat([df_factors, factorsDF_Corp_public[df_factors.columns]])
        else:
            public_names = factorsDF_Corp_public['counterpartyName'].unique().tolist() 
            public_names = df_industryFactors.loc[df_industryFactors['factors'].isna() & df_industryFactors['counterpartyName'].isin(public_names), 'counterpartyName'].unique().tolist()
            df_factors = df_industryFactors[~(df_industryFactors['counterpartyName'].isin(public_names))].copy()
            df_factors = pd.concat([
                df_factors, 
                factorsDF_Corp_public.loc[factorsDF_Corp_public['counterpartyName'].isin(public_names),df_factors.columns]
                ])

        # Validate groupby_cols before processing
        is_valid_groupby_cols = (
            groupby_cols is not None 
            and isinstance(groupby_cols, str) 
            and groupby_cols.strip() != '' 
            and groupby_cols in df_Corp.columns
        )
        
        if is_valid_groupby_cols and df_Corp[groupby_cols].notna().any():
            # Corp Private - process GCorr factors for private issuers
            df_GCorr_factors = self._process_gcorr_factors_for_private_issuers(
                df_corp_public=df_Corp_public,
                df_corp=df_Corp,
                df_gcorr=df_gcorr,
                public_names=public_names,
                groupby_cols=groupby_cols
            )
        else:
            if not is_valid_groupby_cols:
                print(f"Warning: groupby_cols '{groupby_cols}' is invalid or not in df_Corp columns. Skipping GCorr factors processing for private issuers.")
            df_GCorr_factors = None
        
        # Fill missing RSQ values in Corp data
        if df_Corp['RSQ'].isna().any():
            if self.parameters_default_values['corp_rsq_fill_default_value']:
                # Option 1: Fill with default value from parameters
                df_Corp['RSQ'] = df_Corp['RSQ'].fillna(
                    self.parameters_default_values['corp_rsq_default_value']
                )
            elif is_valid_groupby_cols and df_GCorr_factors is not None:
                # Option 2: Fill using grouped mapping from GCorr data
                tmp_map = df_GCorr_factors[[groupby_cols, 'RSQ']].copy()
                tmp_map = tmp_map.set_index(groupby_cols)['RSQ'].to_dict()
                df_Corp['RSQ'] = df_Corp['RSQ'].fillna(
                    df_Corp[groupby_cols].map(tmp_map)
                )
                df_GCorr_factors.drop(columns=['RSQ'], inplace=True)
            else:
                print("Warning: Cannot use grouped mapping for RSQ. Using default value instead.")
                df_Corp['RSQ'] = df_Corp['RSQ'].fillna(
                    self.parameters_default_values['corp_rsq_default_value']
                )
        

        
        factors_private = df_factors.loc[df_factors['factors'].isna()].copy()
        print("The number of private issuers:", len(factors_private['counterpartyName'].unique().tolist()))
        df_factors = df_factors[df_factors['factors'].notna()]

        df_Corp_private = df_Corp[df_Corp['counterpartyName'].isin(factors_private['counterpartyName'])].copy()
        df_Corp_private.to_csv(os.path.join(self.output_dir, f'{self.type}_Corp_private_issuers.csv'), index=False)
        
        
        if factors_private['factors'].isna().any():
            
            if self.parameters_default_values['corp_factors_fill_value_groupby'] and is_valid_groupby_cols and df_GCorr_factors is not None:
                print("corp_factors_fill_value_groupby is true")

                factorsDF_Corp_private = df_Corp_private[['counterpartyName',groupby_cols]].merge(df_GCorr_factors, on=groupby_cols, how='left')

                # Check if any issuers have all NaN iwgt values (no match found in GCorr reference)
                iwgt_cols = [col for col in factorsDF_Corp_private.columns if 'iwgt' in col.lower()]
                if iwgt_cols:
                    print("*********iwgt_cols is not empty*********")
                    factorsDF_Corp_private['has_factors'] = factorsDF_Corp_private[iwgt_cols].notna().any(axis=1)
                    issuers_with_factors = factorsDF_Corp_private[factorsDF_Corp_private['has_factors']].copy()
                    issuers_without_factors = factorsDF_Corp_private[~factorsDF_Corp_private['has_factors']]['counterpartyName'].unique().tolist()

                    # Process issuers that have matching factors in GCorr
                    if not issuers_with_factors.empty:
                        print("--issuers_with_factors is not empty--")
                        issuers_with_factors.drop(columns=[groupby_cols, 'has_factors'], inplace=True)
                        issuers_with_factors = self.process_GCorr_Corp_Factors(issuers_with_factors, 'counterpartyName', 'iwgt')
                        issuers_with_factors['factors'] = 'N' + issuers_with_factors['factors'].str.replace('iwgt', '').str.zfill(2)
                        issuers_with_factors = issuers_with_factors[issuers_with_factors['weights'] > 0][['counterpartyName', 'factors', 'weights']]
                        issuers_with_factors.drop_duplicates(ignore_index=True, inplace=True)
                        df_factors = pd.concat([df_factors, issuers_with_factors[df_factors.columns]])
                
                    # For issuers without matching factors, use equal-weight distribution
                    if issuers_without_factors:
                        print("--issuers_without_factors is not empty--")
                        factorsDF_no_match = self.create_equal_weight_national_factors(issuers_without_factors)
                        df_factors = pd.concat([df_factors, factorsDF_no_match[df_factors.columns]])
                
                else:
                    print("iwgt_cols is empty")
                    # Save the values of 'counterpartyName' and groupby_cols for debugging, then output to CSV
                    debug_filename_base = os.path.join(self.output_dir, f'{self.type}_no_iwgt_factorsDF_Corp_private.csv')
                    factorsDF_Corp_private[['counterpartyName', groupby_cols]].to_csv(debug_filename_base, index=False)

                    # average
                    counterparty_names = factorsDF_Corp_private['counterpartyName'].unique().tolist()
                    factorsDF_Corp_private = self.create_equal_weight_national_factors(counterparty_names)
                    df_factors = pd.concat([df_factors, factorsDF_Corp_private])
            
                # factorsDF_Corp_private.to_csv(os.path.join(self.output_dir, f'{self.type}_factorsDF_Corp_private.csv'), index=False)

            else:
                print("corp_factors_fill_value_groupby is false")
                counterparty_names = factors_private['counterpartyName'].unique().tolist()
                factorsDF_Corp_private = self.create_equal_weight_national_factors(counterparty_names)
                df_factors = pd.concat([df_factors, factorsDF_Corp_private])
        

        # Check whether issuer_names are all in df_Corp
        missing_issuers = [x for x in issuer_names if x not in df_Corp['counterpartyName'].values]
        tmp = self.issuers[self.issuers['counterpartyName'].isin(missing_issuers)]
        if not tmp.empty and tmp is not None:
            print(f"Warning: f'{self.type}_Issuers_Missing_after_GCorr.csv'")
            tmp.to_csv(os.path.join(self.output_dir, f'{self.type}_Issuers_Missing_after_GCorr.csv'), index=False)

        self.issuers = df_Corp.sort_values(by=df_Corp.columns[0])

        factorsDF = df_factors.copy()
        # check if these issuers are in df_industryFactors, then remove them from df_industryFactors
        missing_factors = [x for x in self.issuers['counterpartyName'].unique().tolist() if x not in factorsDF['counterpartyName'].unique().tolist()]
        tmp = self.issuers[self.issuers['counterpartyName'].isin(missing_factors)]
        if not tmp.empty and tmp is not None:
            print(f"Warning: f'{self.type}_Issuers_Missing_Factors_after_GCorr.csv'")
            tmp.to_csv(os.path.join(self.output_dir, f'{self.type}_Issuers_Missing_Factors_after_GCorr.csv'), index=False)

        # check factorsDF has nan values
        tmp = factorsDF[factorsDF['factors'].isna()]
        if not tmp.empty and tmp is not None:
            print(f"Warning: f'{self.type}_Factors_Missing_after_GCorr.csv'")
            tmp.to_csv(os.path.join(self.output_dir, f'{self.type}_Factors_Missing_after_GCorr.csv'), index=False)
        

        factorsDF = factorsDF[self.factors.columns].drop_duplicates()
        self.factors = factorsDF.sort_values(by=factorsDF.columns[:3].tolist())        




    def process_factors(self) -> pd.DataFrame:
        processed = self.factors.copy()
        processed.rename(columns={"counterpartyName": "Name"}, inplace=True)

        tmp = processed[~processed["Name"].isin(self.issuers["counterpartyName"])]
        if not tmp.empty and tmp is not None:
            print(f"Warning: Factors are not provided for issuers in {self.type}_Issuers_Missing_Factors.csv:")
            tmp.to_csv(os.path.join(self.output_dir, f'{self.type}_Issuers_Missing_Factors.csv'), index=False)

        factors = {}
        if "RETAIL" in self.type:
            factors["Region"] = "RETGU"
            factors["ProductType"] = "RETPU"
        elif "CRE" in self.type:
            factors["Geography"] = "CREG"
            factors["PropertyType"] = "CREP"
        elif self.type == 'GC':
            factors["Industry"] = "N"
        elif self.type == 'SOV':
            factors["Sovereign"] = "SOV" # what is the sovereign factor code?

        df_factors = {}
        for factor in factors:
            df_factors[factor] = processed[processed["factors"].str.contains(factors[factor], na=False)].copy()
            df_factors[factor] = df_factors[factor].sort_values(by=["Name", "factors"])
            df_factors[factor]['ParameterSetIndex'] = df_factors[factor].groupby('Name').cumcount() + 1
            df_factors[factor].rename(columns={"factors": factor + "Code", "weights": "Exposure"}, inplace=True)
            # Use IndustryFactorLoadingsParameterSet for GC, otherwise use {factor}LoadingsParameterSet
            format_name = f"{factor}FactorLoadingsParameterSet" if factor == "Industry" else f"{factor}LoadingsParameterSet"
            df_factors[factor] = create_dataframe_from_columns(format_name, self.rics_import_format, df_factors[factor])
            df_factors[factor].drop_duplicates(inplace=True)
            df_factors[factor] = normalize_exposures_by_group(df_factors[factor], 'Exposure', "factors")

        return df_factors


    def process_instruments(self) -> pd.DataFrame:
        df = self.instruments.copy()
        df['Name'] = df['counterpartyName'].astype(str) + '.' + df['instrumentName'].astype(str)
        df['PricingCurve'] = df['Economy'].astype(str) + "." + "NominalYieldCurves.NominalYieldCurve"

        df_instruments = {}  
        df_instruments['ChildModelTypes'] = pd.DataFrame(columns=self.rics_import_format['ChildModelTypes'])
        for instrument_type in df['instrumentType'].unique().tolist():
            if instrument_type == 'Amortising':
                key1 = 'Amortising'
            elif instrument_type == 'Bullet':
                key1 = ''
            df_tmp = df[df['instrumentType'] == instrument_type].copy()
            for interest_type in df_tmp['interestType'].unique().tolist():  # Fixed: use df_tmp instead of df
                if interest_type == 'Fixed':
                    key2 = 'Bond'
                elif interest_type == 'Floating':
                    key2 = 'FRN'
                df_instruments[key1+key2] = df_tmp[df_tmp['interestType'] == interest_type].copy()
                
                
                if df_instruments[key1+key2].empty or df_instruments[key1+key2] is None:
                    continue
                else:
                    table_name = f"Child{key1+key2}"
                    if table_name in self.rics_import_format and "RBCFactors" in self.rics_import_format[table_name]:
                        if "RBCFactors" not in df_instruments[key1+key2].columns:
                            df_instruments[key1+key2]["RBCFactors"] = ""
                    df_instruments[key1+key2]['ParameterSetIndex'] = df_instruments[key1+key2].groupby('Name').cumcount() + 1
                    df_instruments[key1+key2] = create_dataframe_from_columns(table_name, self.rics_import_format, df_instruments[key1+key2])
                    df_instruments[key1+key2].drop_duplicates(inplace=True)
                    df_instruments[key1+key2]['Type'] = key1+key2
                    tmp = df_instruments[key1+key2][['Name','Type']].copy().drop_duplicates()
                    df_instruments[key1+key2] = df_instruments[key1+key2].drop(columns=['Type'])
                    df_instruments['ChildModelTypes'] = pd.concat([df_instruments['ChildModelTypes'], tmp])
        
        df_instruments['ChildModelTypes'] = create_dataframe_from_columns("ChildModelTypes", self.rics_import_format, df_instruments['ChildModelTypes'])
        df_instruments['ChildModelTypes'].drop_duplicates(inplace=True)

        return df_instruments
    
    def process_lgd(self) -> Dict[str, pd.DataFrame]:
        # Placeholder for LGD processing logic
        processed = self.lgd.copy()
        processed['Name'] = processed['counterpartyName'].astype(str) + '.' + processed['instrumentName'].astype(str)

        # Convert lgdDate to datetime if it's not already
        # Try to convert lgdDate to datetime, but handle floats as Years directly
        try:
            processed['lgdDate'] = pd.to_datetime(processed['lgdDate'])
            processed['Years'] = process_date_to_years(processed, 'lgdDate', self.start_date)
        except (ValueError, TypeError):
            # If failed and column is float (or convertible to float), treat as Years
            if pd.api.types.is_float_dtype(processed['lgdDate']):
                processed['Years'] = processed['lgdDate']
            else:
                raise(ValueError(f"Error: lgdDate column must be a datetime or convertible to datetime, or a float (Years)."))

        processed.rename(columns={'lgd': 'LGD', 'lgdVariance': 'K'}, inplace=True)
        processed['ParameterSetIndex'] = processed.groupby('Name').cumcount() + 1
        df = {}
        df['LGDMeanTermStructureParameterSet'] = create_dataframe_from_columns("LGDMeanTermStructureParameterSet", self.rics_import_format, processed)
        df['LGDMeanTermStructureParameterSet'].drop_duplicates(inplace=True)
        df['LGDKTermStructureParameterSet'] = create_dataframe_from_columns("LGDKTermStructureParameterSet", self.rics_import_format, processed)
        df['LGDKTermStructureParameterSet'].drop_duplicates(inplace=True)

        return df
    

    def process_cashflow(self) -> Optional[pd.DataFrame]:
        
        if self.cashflow is not None and len(self.cashflow) > 0:
            processed = self.cashflow.copy()
            processed.rename(columns={'cashflowDate': 'Date', 'cashflowAmount': 'PaymentAmount'}, inplace=True)
            processed['Name'] = processed['counterpartyName'].astype(str) + '.' + processed['instrumentName'].astype(str)
            processed['ParameterSetIndex'] = processed.groupby('Name').cumcount() + 1

            processed = create_dataframe_from_columns("PrincipalPaymentScheduleParameterSet", self.rics_import_format, processed)
            processed.drop_duplicates(inplace=True)
            processed = normalize_exposures_by_group(processed, 'PaymentAmount', "principal")
        else:
            processed = None

        if self.couponPayments is not None:
            coupon_cashflow = self.couponPayments.copy()
            coupon_cashflow['Name'] = coupon_cashflow['counterpartyName'].astype(str) + '.' + coupon_cashflow['instrumentName'].astype(str)
            coupon_cashflow['ParameterSetIndex'] = coupon_cashflow.groupby('Name').cumcount() + 1

            coupon_cashflow = create_dataframe_from_columns("CouponPaymentScheduleParameterSet", self.rics_import_format, coupon_cashflow)
            coupon_cashflow.drop_duplicates(inplace=True)
            coupon_cashflow = normalize_exposures_by_group(coupon_cashflow, 'PaymentAmount', "coupon")
        else:
            coupon_cashflow = None

        return processed, coupon_cashflow
    
    
    def get_summary(self, rics_df: Dict) -> Dict:
        summary = {
            'data_type': self.type,
            'num_issuers': len(self.issuers) if self.issuers is not None else 0,
            'num_factors': len(self.factors) if self.factors is not None else 0,
            'num_pd': len(self.pds) if self.pds is not None else 0,
            'num_instruments': len(self.instruments) if self.instruments is not None else 0,
            'num_lgd_records': len(self.lgd) if self.lgd is not None else 0,
            'num_cashflow_records': len(self.cashflow) if self.cashflow is not None else 0,
        }
        # Extract file information from nested rics_df structure
        # rics_df has keys like 'PD' or 'NonPD', each containing a dict of file DataFrames
        for pdts_type_key in rics_df:
            if isinstance(rics_df[pdts_type_key], dict):
                for file_key, file_df in rics_df[pdts_type_key].items():
                    if file_df is not None and hasattr(file_df, 'shape'):
                        summary[file_key] = {
                            'rows': file_df.shape[0],
                            'unique_names': file_df['Name'].nunique() if 'Name' in file_df.columns else 0
                        }
        return summary

    def process_data_to_rics(self, pdts: Dict, df_pd: pd.DataFrame, df_factors: Dict, rics_pd: pd.DataFrame, df_instruments: Dict, df_lgd: Dict, cashflow: pd.DataFrame, coupon_cashflow: pd.DataFrame) -> Dict:
        
        if pdts['col'] == 'PD':
            issuers = self.pdIssuers
        elif pdts['col'] == 'NonPD':
            issuers = self.nonPdIssuers

        # granular counterparty
        rics_df = {}
        rics_df[f'GCP{pdts["name"]}{self.file_suffix}'] = df_pd.sort_values(by=df_pd.columns[0])
        # factor loadings
        for factor in df_factors:
            tmp = df_factors[factor].copy()
            tmp = tmp[tmp['Name'].isin(issuers)]
            # Sort by first three columns of the DataFrame
            # Use IndustryFactorLoadingsParameterSet for GC (Industry), otherwise use {factor}LoadingsParameterSet
            format_suffix = "FactorLoadingsParameterSet" if factor == "Industry" else "LoadingsParameterSet"
            rics_df[f'GCP{pdts["name"]}_{factor}{format_suffix}{self.file_suffix}'] = tmp.sort_values(by=tmp.columns[:3].tolist())
        
        # pd term structure
        if rics_pd is not None and not rics_pd.empty and pdts['name'] == '_PDTS':
            rics_df[f'GCP{pdts["name"]}_PDTermStructureParameterSet{self.file_suffix}'] = rics_pd.sort_values(by=rics_pd.columns[:3].tolist())

        # child
        child_issuers = {}
        for instrument in df_instruments:
            if instrument != 'ChildModelTypes' and df_instruments[instrument] is not None and not df_instruments[instrument].empty:
                tmp = df_instruments[instrument].copy()
                # Extract counterparty name from instrument Name (format: "counterparty.instrument")
                tmp['CounterpartyName'] = tmp['Name'].str.split('.').str[0]
                tmp = tmp[tmp['CounterpartyName'].isin(issuers)]
                tmp = tmp.drop(columns=['CounterpartyName'])
                if not tmp.empty and tmp is not None:
                    rics_df[f'GCP{pdts["name"]}_Child{instrument}{self.file_suffix}'] = tmp.sort_values(by=tmp.columns[0])
                child_issuers[instrument] = tmp['Name'].unique().tolist()

        # Filter ChildModelTypes by issuers (same as other child instruments)
        tmp_child_model_types = df_instruments['ChildModelTypes'].copy()
        tmp_child_model_types['CounterpartyName'] = tmp_child_model_types['Name'].str.split('.').str[0]
        tmp_child_model_types = tmp_child_model_types[tmp_child_model_types['CounterpartyName'].isin(issuers)]
        tmp_child_model_types = tmp_child_model_types.drop(columns=['CounterpartyName'])
        rics_df[f'GCP{pdts["name"]}_ChildModelTypes{self.file_suffix}'] = tmp_child_model_types.sort_values(by=tmp_child_model_types.columns[:2].tolist())

        # lgd: bond or frn or amortising bond or amortising frn
        for lgd in df_lgd:
            tmp = df_lgd[lgd].copy()
            for name, issuer in child_issuers.items():
                if issuer is not None and len(issuer) > 0:
                    rics_df[f'GCP{pdts["name"]}_Child{name}_{lgd}{self.file_suffix}'] = tmp[tmp['Name'].isin(issuer)].sort_values(by=tmp.columns[:3].tolist())

        # interpolate lgd mean and k for amortising bond or amortising frn
        if self.parameters_default_values['interpolate_lgd_lgdk_for_amortising']:
            for name, issuer in child_issuers.items():
                if 'Amortising' in name and issuer is not None and len(issuer) > 0:
                    tmp_lgd = rics_df[f'GCP{pdts["name"]}_Child{name}_LGDMeanTermStructureParameterSet{self.file_suffix}']
                    # Check if interpolation is needed (more than 1 unique year per instrument)
                    # This optimization skips unnecessary processing when data has only single points
                    max_years_per_instrument = tmp_lgd.groupby('Name')['Years'].count().max()
                
                    if max_years_per_instrument > 1:
                        # Multiple years exist - perform monthly interpolation
                        name_order = rics_df[f'GCP{pdts["name"]}_Child{name}{self.file_suffix}']['Name'].tolist()
                        tmp_lgdk = rics_df[f'GCP{pdts["name"]}_Child{name}_LGDKTermStructureParameterSet{self.file_suffix}']
                        tmp = pd.merge(tmp_lgd, tmp_lgdk, on=['Name', 'ParameterSetIndex', 'Years'], how='left')
                    
                        rics_df[f'GCP{pdts["name"]}_Child{name}_LGDMeanTermStructureParameterSet{self.file_suffix}'], rics_df[f'GCP{pdts["name"]}_Child{name}_LGDKTermStructureParameterSet{self.file_suffix}'] = interpolate_lgd_lgdk(tmp, name_order)
        else:
            pass  # Don't interpolate when FALSE

        
        
        # cashflow: amortising bond or amortising frn
        if cashflow is not None:
            for name, issuer in child_issuers.items():
                if "Amortising" in name:
                    if issuer is not None and len(issuer) > 0:
                        matched = cashflow[cashflow['Name'].isin(issuer)]
                        rics_df[f'GCP{pdts["name"]}_Child{name}_PrincipalPaymentScheduleParameterSet{self.file_suffix}'] = matched.sort_values(by=matched.columns[:3].tolist())
                else: 
                    continue
            if coupon_cashflow is not None:
                for name, issuer in child_issuers.items():
                    if "Amortising" in name:
                        if issuer is not None and len(issuer) > 0:
                            rics_df[f'GCP{pdts["name"]}_Child{name}_CouponPaymentScheduleParameterSet{self.file_suffix}'] = coupon_cashflow[coupon_cashflow['Name'].isin(issuer)].sort_values(by=coupon_cashflow.columns[:3].tolist())
                    else:
                        continue    
            else:
                for name, issuer in child_issuers.items():
                    if "Amortising" in name:
                        if issuer is not None and len(issuer) > 0:
                            rics_df[f'GCP{pdts["name"]}_Child{name}_CouponPaymentScheduleParameterSet{self.file_suffix}'] = pd.DataFrame(columns=self.rics_import_format['CouponPaymentScheduleParameterSet'])
                    else:
                        continue

        return rics_df

    
    def run(self):
        """
        Run the processing.
        """
        print(f'\n{self.type} processing started...')

        if self.type == 'GC':
            self.process_gc_issuers()

        df_nonpd, df_pd, rics_pd = self.process_issuers()

        df_factors = self.process_factors()

        # Apply maturity filter on self.instruments, and update self.instruments
        # Also remove matured instruments from self.lgd, self.cashflow, self.couponPayments
        print(f"\nApplying maturity filter for {self.type}...")
        matured_instruments_list = self.filter_matured_instruments()
        
        df_instruments = self.process_instruments()

        df_lgd = self.process_lgd()
        cashflow, coupon_cashflow = self.process_cashflow()

        
        rics_df = {}
        if self.pdIssuers is not None and len(self.pdIssuers) > 0: 
            pdts_dict = {
                'col': 'PD',
                'name': '_PDTS'
            }

            rics_df[pdts_dict['col']] = self.process_data_to_rics(pdts_dict, df_pd, df_factors, rics_pd, df_instruments, df_lgd, cashflow, coupon_cashflow)

            pdts_flag_str = '_PDTS' if pdts_dict['col'] == 'PD' else ''
            pdts_output_name = 'PD' if pdts_dict['col'] == 'PD' else ''
            output_name = f"{self.type}{pdts_output_name}"
            save_rics_output_files(rics_df[pdts_dict['col']], self.output_dir, output_name, pdts_flag_str)

        if self.nonPdIssuers is not None and len(self.nonPdIssuers) > 0:
            pdts_dict = {
                'col': 'NonPD',
                'name': ''
            }
            rics_df[pdts_dict['col']] = self.process_data_to_rics(pdts_dict, df_nonpd, df_factors, rics_pd, df_instruments, df_lgd, cashflow, coupon_cashflow)

            pdts_flag_str = '_PDTS' if pdts_dict['col'] == 'PD' else ''
            pdts_output_name = 'PD' if pdts_dict['col'] == 'PD' else ''
            output_name = f"{self.type}{pdts_output_name}"
            save_rics_output_files(rics_df[pdts_dict['col']], self.output_dir, output_name, pdts_flag_str)

        
        summary = self.get_summary(rics_df)
        summary['matured_instruments'] = self.matured_instruments
        summary['num_matured_instruments'] = len(self.matured_instruments)
        print(summary)


        print(f'\n{self.type} processing completed,\n')
        return summary

