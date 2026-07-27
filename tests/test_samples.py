from datetime import date
from pathlib import Path

from sales_data_quality.loader import load_csv
from sales_data_quality.service import DataQualityService

SAMPLE_DIRECTORY = Path(__file__).parents[1] / "sample_data"
EXECUTION_DATE = date(2026, 7, 27)


def test_portfolio_samples_produce_clearly_different_results():
    expected = {
        "sample_all_valid.csv": {
            "rows": (6, 6, 0, 0),
            "issue_count": 0,
            "correction_count": 0,
        },
        "sample_auto_cleanup.csv": {
            "rows": (6, 6, 0, 0),
            "issue_count": 0,
            "correction_count": 63,
        },
        "sample_quality_issues.csv": {
            "rows": (11, 1, 2, 8),
            "issue_count": 10,
            "correction_count": 0,
        },
    }

    for filename, expected_result in expected.items():
        source = SAMPLE_DIRECTORY / filename
        dataset = load_csv(source.read_bytes(), filename)
        result = DataQualityService().process(dataset, execution_date=EXECUTION_DATE)
        metrics = result.metrics

        assert (
            metrics.total_rows,
            metrics.normal_rows,
            metrics.warning_rows,
            metrics.error_rows,
        ) == expected_result["rows"]
        assert len(result.issues) == expected_result["issue_count"]
        assert len(result.corrections) == expected_result["correction_count"]
