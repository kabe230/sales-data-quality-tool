from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

import pandas as pd


class Severity(Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass(frozen=True)
class CorrectionRecord:
    source_row_number: int
    field_name: str
    code: str
    original_value: object
    cleaned_value: object
    message: str


@dataclass(frozen=True)
class ValidationIssue:
    source_row_number: int
    field_name: str
    severity: Severity
    code: str
    original_value: object
    cleaned_value: object
    message: str


@dataclass(frozen=True)
class LoadedDataset:
    dataframe: pd.DataFrame
    source_filename: str
    file_type: str
    encoding: str | None
    sheet_name: str | None
    source_row_numbers: tuple[int, ...]
    original_columns: tuple[str, ...]
    file_size_bytes: int
    blank_row_count: int = 0


@dataclass(frozen=True)
class PreflightResult:
    normalized_columns: tuple[str, ...]
    missing_required_columns: tuple[str, ...]
    extra_columns: tuple[str, ...]
    reserved_conflicts: tuple[str, ...]
    source_row_count: int
    blank_row_count: int


@dataclass(frozen=True)
class SummaryMetrics:
    total_rows: int
    normal_rows: int
    warning_rows: int
    error_rows: int
    normal_rate: float
    aggregation_rows: int
    excluded_rows: int
    aggregation_amount: int
    excluded_amount: int
    average_amount: Decimal | None
    maximum_amount: int | None
    minimum_amount: int | None
    error_issue_count: int
    warning_issue_count: int
    valid_rate: float


@dataclass(frozen=True)
class ProcessingResult:
    normalized_data: pd.DataFrame
    cleaned_data: pd.DataFrame
    issues: tuple[ValidationIssue, ...]
    corrections: tuple[CorrectionRecord, ...]
    metrics: SummaryMetrics
    summaries: dict[str, pd.DataFrame]
    processing_log: dict[str, object]
