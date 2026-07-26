from __future__ import annotations

import re
from collections import Counter
from datetime import date

import pandas as pd

from sales_data_quality.config import (
    ALLOWED_STATUSES,
    COLUMNS,
    MAX_AMOUNT,
    REQUIRED_FIELDS,
    ValidationOptions,
)
from sales_data_quality.models import Severity, ValidationIssue
from sales_data_quality.processing.cleaner import is_blank

PROJECT_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9_-]{0,49}$")


def _message(code: str, field: str) -> str:
    messages = {
        "EMPTY_REQUIRED_VALUE": f"{COLUMNS[field]}は必須です。",
        "INVALID_PROJECT_ID": "案件IDの形式が正しくありません。",
        "DUPLICATE_PROJECT_ID": "案件IDが重複しています。",
        "INVALID_EMAIL": "メールアドレスの形式が正しくありません。",
        "INVALID_AMOUNT": "案件金額を整数として解釈できません。",
        "NEGATIVE_AMOUNT": "案件金額に負数は指定できません。",
        "AMOUNT_OUT_OF_RANGE": "案件金額が許可された上限を超えています。",
        "INVALID_DATE": f"{COLUMNS[field]}の日付形式が正しくありません。",
        "FUTURE_REGISTERED_DATE": "登録日が実行基準日より未来です。",
        "UNKNOWN_STATUS": "ステータスが許可値または変換辞書に含まれていません。",
        "EXPECTED_DATE_MISSING": "このステータスでは受注予定日が必要です。",
        "PAST_EXPECTED_ORDER_DATE": "受注予定日が実行基準日より過去です。",
        "EXPECTED_DATE_BEFORE_REGISTERED_DATE": "受注予定日が登録日より前です。",
        "MISSING_DEPARTMENT": "担当部署が未入力です。",
    }
    return messages[code]


def _email_valid(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 254 or any(char.isspace() for char in value):
        return False
    if value.count("@") != 1:
        return False
    local, domain = value.split("@")
    return bool(local and domain and "." in domain)


def validate(
    normalized: pd.DataFrame,
    cleaned: pd.DataFrame,
    options: ValidationOptions,
    execution_date: date,
) -> tuple[pd.DataFrame, tuple[ValidationIssue, ...]]:
    issues: list[ValidationIssue] = []
    ids = [value for value in cleaned["project_id"] if not is_blank(value)]
    duplicates = {value for value, count in Counter(ids).items() if count > 1}

    def add(index: int, field: str, severity: Severity, code: str) -> None:
        issues.append(
            ValidationIssue(
                int(cleaned.at[index, "source_row_number"]),
                field,
                severity,
                code,
                normalized.at[index, field],
                cleaned.at[index, field],
                _message(code, field),
            )
        )

    for index, row in cleaned.iterrows():
        for field in REQUIRED_FIELDS:
            if is_blank(row[field]):
                add(index, field, Severity.ERROR, "EMPTY_REQUIRED_VALUE")

        project_id = row["project_id"]
        if not is_blank(project_id) and (
            not isinstance(project_id, str) or not PROJECT_ID_PATTERN.fullmatch(project_id)
        ):
            add(index, "project_id", Severity.ERROR, "INVALID_PROJECT_ID")
        if not is_blank(project_id) and project_id in duplicates:
            add(index, "project_id", Severity.ERROR, "DUPLICATE_PROJECT_ID")

        if not is_blank(row["email"]) and not _email_valid(row["email"]):
            add(index, "email", Severity.ERROR, "INVALID_EMAIL")

        amount = row["amount"]
        if not is_blank(amount):
            if isinstance(amount, bool) or not isinstance(amount, int):
                add(index, "amount", Severity.ERROR, "INVALID_AMOUNT")
            elif amount < 0:
                add(index, "amount", Severity.ERROR, "NEGATIVE_AMOUNT")
            elif amount > MAX_AMOUNT:
                add(index, "amount", Severity.ERROR, "AMOUNT_OUT_OF_RANGE")

        dates_valid: dict[str, bool] = {}
        for field in ("registered_date", "expected_order_date"):
            value = row[field]
            dates_valid[field] = is_blank(value) or isinstance(value, date)
            if not is_blank(value) and not isinstance(value, date):
                add(index, field, Severity.ERROR, "INVALID_DATE")

        status = row["status"]
        status_valid = not is_blank(status) and status in ALLOWED_STATUSES
        if not is_blank(status) and not status_valid:
            add(index, "status", Severity.ERROR, "UNKNOWN_STATUS")

        registered = row["registered_date"]
        expected = row["expected_order_date"]
        if isinstance(registered, date) and registered > execution_date:
            add(index, "registered_date", Severity.ERROR, "FUTURE_REGISTERED_DATE")
        if status_valid and status in {"商談中", "見積提出"} and is_blank(expected):
            add(index, "expected_order_date", Severity.ERROR, "EXPECTED_DATE_MISSING")
        if isinstance(expected, date):
            if options.warn_past_expected_order_date and expected < execution_date:
                add(index, "expected_order_date", Severity.WARNING, "PAST_EXPECTED_ORDER_DATE")
            if (
                options.warn_expected_date_before_registered_date
                and isinstance(registered, date)
                and expected < registered
            ):
                add(
                    index,
                    "expected_order_date",
                    Severity.WARNING,
                    "EXPECTED_DATE_BEFORE_REGISTERED_DATE",
                )
        if options.warn_missing_department and is_blank(row["department"]):
            add(index, "department", Severity.WARNING, "MISSING_DEPARTMENT")

    result = cleaned.copy(deep=True)
    by_row: dict[int, list[ValidationIssue]] = {}
    for issue in issues:
        by_row.setdefault(issue.source_row_number, []).append(issue)
    for index, row in result.iterrows():
        row_issues = by_row.get(int(row["source_row_number"]), [])
        errors = sum(issue.severity is Severity.ERROR for issue in row_issues)
        warnings = sum(issue.severity is Severity.WARNING for issue in row_issues)
        result.at[index, "error_count"] = errors
        result.at[index, "warning_count"] = warnings
        result.at[index, "check_result"] = (
            "ERROR" if errors else "WARNING" if warnings else "NORMAL"
        )
        result.at[index, "issue_summary"] = "\n".join(issue.message for issue in row_issues)
    return result, tuple(issues)
