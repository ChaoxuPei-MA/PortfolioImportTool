import os

from pit.converter.summary import write_summary_file


def test_write_summary_creates_file_with_sections(tmp_path):
    summaries = {
        "gc": {
            "data_type": "GC",
            "num_issuers": 3,
            "num_factors": 2,
            "num_instruments": 5,
            "1_GCP": {"rows": 5, "unique_names": 3},
        },
        "portfolio": {
            "num_portfolios": 1,
            "num_holdings_per_portfolio": {"PortA": 4},
        },
        "agency_mbs": None,
    }
    path = write_summary_file(str(tmp_path), "20250630", summaries)
    assert path == os.path.join(str(tmp_path), "RICS_Format_Converter_Summary.txt")
    text = open(path, encoding="utf-8").read()
    assert "RICS FORMAT CONVERTER - PROCESSING SUMMARY" in text
    assert "Processing Date: 20250630" in text
    assert "GC (CORPORATE) PROCESSING" in text
    assert "PORTFOLIO PROCESSING" in text
    assert "PortA: 4 holdings" in text
    assert "PROCESSING COMPLETED SUCCESSFULLY" in text
