import pandas as pd
from typing import Optional, Dict
from pit.converter.processors.convert_to_rics import *


class Portfolio:

    def __init__(self, data: Dict[str, Optional[pd.DataFrame]], rics_import_format: str, output_path: str, portfolio_subdir: str = 'portfolio'):

        self.portfolios = data.get('Portfolios')
        self.holdings = data.get('Holdings')

        self.rics_import_format = rics_import_format

        self.output_path = os.path.join(output_path, portfolio_subdir) if portfolio_subdir else output_path
        os.makedirs(self.output_path, exist_ok=True)
        
        self._validate_data()
    
    def _validate_data(self):
        """
        Validate that required data is present.
        """
        if self.portfolios is None:
            raise ValueError("Portfolio: Portfolios data is required")
        if self.holdings is None:
            raise ValueError("Portfolio: Holdings data is required")
    
    def process_portfolios(self) -> pd.DataFrame:
        processed = self.portfolios.copy()
        processed.rename(columns={"portfolioName": "Name"}, inplace=True)

        self.portfolios = create_dataframe_from_columns("Portfolios", self.rics_import_format, processed)


    def process_holdings(self) -> pd.DataFrame:
        processed = self.holdings.copy()
        processed.rename(columns={"portfolioName": "Name"}, inplace=True)
        processed['ParameterSetIndex'] = processed.groupby('Name').cumcount() + 1

        processed['Asset'] = processed['counterpartyName'] + "." + processed['instrumentName']
        processed.rename(columns={"Weights": "Weight","CurrencyHedge":"CurrencyHedge"}, inplace=True)
        
        self.holdings = create_dataframe_from_columns("Holdings", self.rics_import_format, processed)

    
    def save_data(self):
        self.portfolios.to_csv(os.path.join(self.output_path, f'CompositePortfolio.csv'), index=False)
        self.holdings.to_csv(os.path.join(self.output_path, f'CompositePortfolio_HoldingsParameterSet.csv'), index=False)

    
    def get_summary(self) -> Dict:

        summary = {
            'num_portfolios': len(self.portfolios) if self.portfolios is not None else 0,
            'num_holdings_per_portfolio': self.holdings.groupby('Name')['Asset'].count().to_dict() if self.holdings is not None else {},
        }
        return summary
    
    def run(self):
        """
        Run Portfolio processing.
        """
        print('\n' + 'Portfolio processing started...')

        self.process_portfolios()
        self.process_holdings()
        summary = self.get_summary()
        print(summary)

        self.save_data()

        print('\n' + 'Portfolio processing completed.\n')
        return summary

