from dataclasses import replace
from datetime import date

from sales_data_quality.config import CleaningOptions, ValidationOptions
from sales_data_quality.models import Severity
from sales_data_quality.service import DataQualityService


def test_process_cleans_validates_and_aggregates(dataset):
    result = DataQualityService().process(
        dataset,
        ValidationOptions(),
        CleaningOptions(),
        execution_date=date(2026, 7, 1),
    )

    first = result.cleaned_data.iloc[0]
    assert first["project_id"] == "P-0001"
    assert first["email"] == "hanako@sakura.co.jp"
    assert first["amount"] == 1_000_000
    assert first["status"] == "受注"
    assert first["check_result"] == "WARNING"

    second = result.cleaned_data.iloc[1]
    assert second["check_result"] == "ERROR"
    assert {issue.code for issue in result.issues if issue.source_row_number == 3} == {
        "INVALID_EMAIL",
        "EXPECTED_DATE_MISSING",
        "MISSING_DEPARTMENT",
    }
    assert result.metrics.aggregation_rows == 1
    assert result.metrics.error_rows == 1
    assert any(issue.severity is Severity.WARNING for issue in result.issues)


def test_input_dataframe_is_not_modified(dataset):
    original = dataset.dataframe.copy(deep=True)
    DataQualityService().process(dataset, execution_date=date(2026, 7, 1))
    assert dataset.dataframe.equals(original)


def test_processing_log_distinguishes_input_blank_and_processed_rows(dataset):
    dataset_with_blanks = replace(dataset, blank_row_count=2)
    result = DataQualityService().process(
        dataset_with_blanks,
        execution_date=date(2026, 7, 1),
    )

    assert result.processing_log["input_rows"] == 4
    assert result.processing_log["blank_rows"] == 2
    assert result.processing_log["processed_rows"] == 2
