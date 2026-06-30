import os
import datetime


def write_granular_counterparty_summary(f, title, summary_data):
    """
    Write granular counterparty (GC/GCCRE/GCRETAIL) summary section.

    Args:
        f: File handle to write to
        title: Section title (e.g., "GCCRE (COMMERCIAL REAL ESTATE) PROCESSING")
        summary_data: Dictionary containing summary information
    """
    f.write(f"{title}\n")
    f.write("-" * 80 + "\n")
    f.write(f"Data Type: {summary_data.get('data_type', 'N/A')}\n")
    f.write(f"Number of Issuers: {summary_data.get('num_issuers', 0):,}\n")
    f.write(f"Number of Factors: {summary_data.get('num_factors', 0):,}\n")
    f.write(f"Number of Instruments: {summary_data.get('num_instruments', 0):,}\n")
    f.write(f"Number of Matured Instruments (Filtered): {summary_data.get('num_matured_instruments', 0):,}\n")
    f.write(f"Number of LGD Records: {summary_data.get('num_lgd_records', 0):,}\n")
    f.write(f"Number of PD Records: {summary_data.get('num_pd', 0):,}\n")
    f.write(f"Number of Cashflow Records: {summary_data.get('num_cashflow_records', 0):,}\n")

    # List all generated files dynamically from rics_df keys
    f.write("\nOutput Files Generated:\n")

    # Filter out the metadata keys to get only file names
    metadata_keys = {'data_type', 'num_issuers', 'num_factors', 'num_pd',
                    'num_instruments', 'num_lgd_records', 'num_cashflow_records',
                    'matured_instruments', 'num_matured_instruments'}

    file_keys = [key for key in summary_data.keys() if key not in metadata_keys]

    if file_keys:
        # Sort files for better readability
        file_keys_sorted = sorted(file_keys)
        total_files = 0
        total_rows = 0

        for file_key in file_keys_sorted:
            file_info = summary_data[file_key]
            # Handle both dict format (new) and integer format (old) for backward compatibility
            if isinstance(file_info, dict):
                row_count = file_info.get('rows', 0)
                unique_names = file_info.get('unique_names', 0)
                f.write(f"  - {file_key}.csv ({row_count:,} rows, {unique_names:,} unique names)\n")
            else:
                # Legacy format: just an integer
                row_count = file_info
                f.write(f"  - {file_key}.csv ({row_count:,} rows)\n")
            total_files += 1
            total_rows += row_count

        f.write(f"\nTotal: {total_files} files with {total_rows:,} total rows\n")
    else:
        f.write("  (No file information available)\n")

    f.write("\n" + "-" * 80 + "\n\n")


def write_summary_file(output_dir, start_date, summaries):
    """
    Write a summary file with processing information.

    Args:
        output_dir: Directory to save the summary file
        start_date: Processing date
        summaries: Dictionary containing summary information from different processors
    """
    import datetime

    summary_file = os.path.join(output_dir, 'RICS_Format_Converter_Summary.txt')

    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("RICS FORMAT CONVERTER - PROCESSING SUMMARY\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"Processing Date: {start_date}\n")
        f.write(f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("\n" + "-" * 80 + "\n\n")

        # Agency MBS Summary
        if 'agency_mbs' in summaries and summaries['agency_mbs']:
            f.write("AGENCY MBS PROCESSING\n")
            f.write("-" * 80 + "\n")
            mbs_summary = summaries['agency_mbs']
            f.write(f"Data Type: {mbs_summary.get('data_type', 'N/A')}\n")
            f.write(f"Number of Issuers: {mbs_summary.get('num_issuers', 0)}\n")
            f.write(f"Number of Instruments: {mbs_summary.get('num_instruments', 0)}\n")
            f.write(f"Number of Removed Instruments (SurvivalFactor == 0): {mbs_summary.get('num_removed_instruments', 0)}\n")
            f.write("\nOutput Files Generated:\n")
            f.write("  - AgencyMBSIssuer.csv\n")
            f.write("  - AgencyMBSIssuer_LaggardDistributionParameterSet.csv\n")
            f.write("  - AgencyMBSIssuerChildMBS.csv\n")
            f.write("  - AgencyMBSIssuerChildModelTypes.csv\n")
            f.write("\n" + "-" * 80 + "\n\n")

        # Granular Counterparty Summaries (GC, GCCRE, GCRETAIL)
        if 'gc' in summaries and summaries['gc']:
            write_granular_counterparty_summary(f, "GC (CORPORATE) PROCESSING", summaries['gc'])

        if 'gccre' in summaries and summaries['gccre']:
            write_granular_counterparty_summary(f, "GCCRE (COMMERCIAL REAL ESTATE) PROCESSING", summaries['gccre'])

        if 'gcretail' in summaries and summaries['gcretail']:
            write_granular_counterparty_summary(f, "GCRETAIL (RETAIL) PROCESSING", summaries['gcretail'])

        # Portfolio Summary
        if 'portfolio' in summaries and summaries['portfolio']:
            f.write("PORTFOLIO PROCESSING\n")
            f.write("-" * 80 + "\n")
            port_summary = summaries['portfolio']
            f.write(f"Number of Portfolios: {port_summary.get('num_portfolios', 0)}\n\n")

            holdings_per_portfolio = port_summary.get('num_holdings_per_portfolio', {})
            if holdings_per_portfolio:
                f.write("Holdings per Portfolio:\n")
                total_holdings = 0
                for portfolio_name, count in sorted(holdings_per_portfolio.items()):
                    f.write(f"  - {portfolio_name}: {count:,} holdings\n")
                    total_holdings += count
                f.write(f"\nTotal Holdings Across All Portfolios: {total_holdings:,}\n")

            f.write("\nOutput Files Generated:\n")
            f.write("  - CompositePortfolio.csv\n")
            f.write("  - CompositePortfolio_Holdings.csv\n")
            f.write("\n" + "-" * 80 + "\n\n")

        f.write("\n" + "=" * 80 + "\n")
        f.write("PROCESSING COMPLETED SUCCESSFULLY\n")
        f.write("=" * 80 + "\n")

    print(f"\nSummary file created: {summary_file}")
    return summary_file
