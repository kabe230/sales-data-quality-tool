from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from sales_data_quality.config import COLUMNS, CleaningOptions
from sales_data_quality.exceptions import DataQualityError
from sales_data_quality.models import LoadedDataset
from sales_data_quality.service import DataQualityService

EXECUTION_DATE = date(2026, 7, 1)


def _dataset(*overrides: dict[str, object]) -> LoadedDataset:
    base = {
        "案件ID": "P-1000",
        "顧客名": "株式会社テスト",
        "担当者名": "担当者",
        "メールアドレス": "test@example.com",
        "案件名": "テスト案件",
        "案件金額": "1000",
        "ステータス": "受注",
        "担当部署": "営業部",
        "登録日": "2026-01-01",
        "受注予定日": "",
        "備考": "",
    }
    rows = [base | override for override in overrides]
    frame = pd.DataFrame(rows, columns=COLUMNS.values())
    return LoadedDataset(
        frame,
        "rules.csv",
        "csv",
        "utf-8-sig",
        None,
        tuple(range(2, len(frame) + 2)),
        tuple(frame.columns),
        100,
    )


def _process(*rows: dict[str, object], cleaning_options: CleaningOptions | None = None):
    return DataQualityService().process(
        _dataset(*rows),
        cleaning_options=cleaning_options,
        execution_date=EXECUTION_DATE,
    )


def test_all_cleaning_options_can_be_disabled_without_skipping_validation():
    options = CleaningOptions(
        trim_whitespace=False,
        normalize_line_breaks=False,
        normalize_full_width_numbers=False,
        normalize_project_id=False,
        normalize_amount=False,
        normalize_dates=False,
        normalize_email=False,
        normalize_status=False,
    )
    result = _process(
        {
            "案件ID": "p-００１",
            "メールアドレス": "TEST＠EXAMPLE.CO.JP",
            "案件金額": "¥1,000",
            "ステータス": "受注済",
            "登録日": "2026/01/01",
        },
        cleaning_options=options,
    )

    assert result.corrections == ()
    assert {issue.code for issue in result.issues} == {
        "INVALID_PROJECT_ID",
        "INVALID_EMAIL",
        "INVALID_AMOUNT",
        "INVALID_DATE",
        "UNKNOWN_STATUS",
    }


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("300000", 300000),
        ("300,000", 300000),
        ("¥300,000", 300000),
        ("￥３００,０００", 300000),
        ("300000円", 300000),
        ("+¥1,000", 1000),
        (1000, 1000),
        (1000.0, 1000),
    ],
)
def test_allowed_amount_patterns(raw, expected):
    result = _process({"案件金額": raw})
    assert result.cleaned_data.loc[0, "amount"] == expected
    assert not any(issue.code == "INVALID_AMOUNT" for issue in result.issues)


@pytest.mark.parametrize("raw", ["1円2", "12,34", "1.5", "1e3", "¥-1,000", True])
def test_invalid_amount_patterns_are_not_guessed(raw):
    result = _process({"案件金額": raw})
    assert [issue.code for issue in result.issues] == ["INVALID_AMOUNT"]


def test_amount_priority_negative_then_upper_limit():
    result = _process(
        {"案件ID": "P-NEG", "案件金額": "-1"},
        {"案件ID": "P-MAX", "案件金額": "1000000000000000"},
    )
    assert [(issue.source_row_number, issue.code) for issue in result.issues] == [
        (2, "NEGATIVE_AMOUNT"),
        (3, "AMOUNT_OUT_OF_RANGE"),
    ]


def test_date_cross_field_rules_and_conditional_requirement():
    result = _process(
        {"案件ID": "P-MISSING", "ステータス": "商談中"},
        {
            "案件ID": "P-BEFORE",
            "ステータス": "保留",
            "登録日": "2026-06-15",
            "受注予定日": "2026-06-01",
        },
    )
    assert [(issue.source_row_number, issue.code) for issue in result.issues] == [
        (2, "EXPECTED_DATE_MISSING"),
        (3, "EXPECTED_DATE_BEFORE_REGISTERED_DATE"),
        (3, "PAST_EXPECTED_ORDER_DATE"),
    ]


def test_blank_required_value_suppresses_format_issue():
    result = _process({"案件ID": "", "メールアドレス": "", "案件金額": ""})
    assert [issue.code for issue in result.issues] == [
        "EMPTY_REQUIRED_VALUE",
        "EMPTY_REQUIRED_VALUE",
        "EMPTY_REQUIRED_VALUE",
    ]


def test_invalid_duplicate_project_ids_receive_both_issues():
    result = _process(
        {"案件ID": "invalid id"},
        {"案件ID": "invalid id"},
    )
    assert [(issue.source_row_number, issue.code) for issue in result.issues] == [
        (2, "DUPLICATE_PROJECT_ID"),
        (2, "INVALID_PROJECT_ID"),
        (3, "DUPLICATE_PROJECT_ID"),
        (3, "INVALID_PROJECT_ID"),
    ]


def test_extra_columns_are_preserved_and_reserved_names_are_rejected():
    dataset = _dataset({})
    dataset.dataframe["社内分類"] = ["A"]
    result = DataQualityService().process(dataset, execution_date=EXECUTION_DATE)
    assert result.cleaned_data["社内分類"].tolist() == ["A"]

    reserved = _dataset({})
    reserved.dataframe["チェック結果"] = [""]
    with pytest.raises(DataQualityError) as exc_info:
        DataQualityService().process(reserved, execution_date=EXECUTION_DATE)
    assert exc_info.value.code == "RESERVED_COLUMN_CONFLICT"
