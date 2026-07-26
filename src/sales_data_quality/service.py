from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from datetime import date, datetime

import pandas as pd

from sales_data_quality.config import (
    COLUMNS,
    DISPLAY_TO_INTERNAL,
    INTERNAL_COLUMNS,
    RESERVED_NAMES,
    CleaningOptions,
    ValidationOptions,
)
from sales_data_quality.exceptions import DataQualityError
from sales_data_quality.models import LoadedDataset, PreflightResult, ProcessingResult
from sales_data_quality.processing.aggregator import aggregate
from sales_data_quality.processing.cleaner import clean
from sales_data_quality.processing.validator import validate


def _normalize_header(value: object) -> str:
    return str(value).removeprefix("\ufeff").strip(" \u3000")


class DataQualityService:
    def _normalize(self, dataset: LoadedDataset) -> tuple[pd.DataFrame, tuple[str, ...]]:
        headers = [_normalize_header(column) for column in dataset.dataframe.columns]
        if any(not header for header in headers):
            raise DataQualityError("EMPTY_COLUMN_NAME", "空の列名があります。")
        if len(headers) != len(set(headers)):
            raise DataQualityError("DUPLICATE_COLUMN", "重複する列名があります。")
        conflicts = sorted(set(headers) & RESERVED_NAMES)
        if conflicts:
            raise DataQualityError(
                "RESERVED_COLUMN_CONFLICT", f"予約済み列名があります: {', '.join(conflicts)}"
            )
        missing = [name for name in DISPLAY_TO_INTERNAL if name not in headers]
        if missing:
            raise DataQualityError(
                "MISSING_REQUIRED_COLUMNS", f"必要な列がありません: {', '.join(missing)}"
            )
        renamed = dataset.dataframe.copy(deep=True)
        renamed.columns = headers
        renamed.rename(columns=DISPLAY_TO_INTERNAL, inplace=True)
        extras = tuple(column for column in renamed.columns if column not in COLUMNS)
        order = [*COLUMNS, *extras]
        renamed = renamed[order]
        renamed["source_row_number"] = list(dataset.source_row_numbers)
        for column in INTERNAL_COLUMNS[1:]:
            renamed[column] = "" if column in {"check_result", "issue_summary"} else 0
        return renamed, extras

    def inspect_schema(self, dataset: LoadedDataset) -> PreflightResult:
        headers = tuple(_normalize_header(column) for column in dataset.dataframe.columns)
        missing = tuple(name for name in DISPLAY_TO_INTERNAL if name not in headers)
        extras = tuple(name for name in headers if name not in DISPLAY_TO_INTERNAL)
        conflicts = tuple(name for name in headers if name in RESERVED_NAMES)
        return PreflightResult(
            headers,
            missing,
            extras,
            conflicts,
            len(dataset.dataframe),
            dataset.blank_row_count,
        )

    def process(
        self,
        dataset: LoadedDataset,
        validation_options: ValidationOptions | None = None,
        cleaning_options: CleaningOptions | None = None,
        execution_date: date | None = None,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> ProcessingResult:
        validation_options = validation_options or ValidationOptions()
        cleaning_options = cleaning_options or CleaningOptions()
        execution_date = execution_date or date.today()
        started = datetime.now()

        def progress(label: str, value: float) -> None:
            if progress_callback:
                progress_callback(label, value)

        progress("列を確認しています", 0.1)
        normalized, extras = self._normalize(dataset)
        progress("データを整形しています", 0.35)
        cleaned, corrections = clean(normalized, cleaning_options)
        progress("入力内容を検証しています", 0.6)
        checked, issues = validate(normalized, cleaned, validation_options, execution_date)
        progress("集計しています", 0.8)
        metrics, summaries = aggregate(checked, issues)
        ended = datetime.now()
        log = {
            "source_filename": dataset.source_filename,
            "started_at": started.isoformat(timespec="seconds"),
            "ended_at": ended.isoformat(timespec="seconds"),
            "execution_date": execution_date.isoformat(),
            "input_rows": len(dataset.dataframe),
            "blank_rows": dataset.blank_row_count,
            "processed_rows": len(checked),
            "extra_columns": list(extras),
            "cleaning_options": asdict(cleaning_options),
            "validation_options": asdict(validation_options),
            "correction_count": len(corrections),
            "error_rows": metrics.error_rows,
            "warning_rows": metrics.warning_rows,
            "error_issue_count": metrics.error_issue_count,
            "warning_issue_count": metrics.warning_issue_count,
            "aggregation_rows": metrics.aggregation_rows,
            "excluded_rows": metrics.excluded_rows,
        }
        progress("完了", 1.0)
        return ProcessingResult(normalized, checked, issues, corrections, metrics, summaries, log)
