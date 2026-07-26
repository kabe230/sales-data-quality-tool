from __future__ import annotations

import math
import re
from datetime import date, datetime
from decimal import Decimal

import pandas as pd

from sales_data_quality.config import COLUMNS, STATUS_ALIASES, CleaningOptions
from sales_data_quality.models import CorrectionRecord

FULL_WIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
FULL_WIDTH_LETTERS = str.maketrans(
    "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
    "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ",
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
)
AMOUNT_PATTERN = re.compile(r"^([+-]?)(?:¥)?((?:\d{1,3}(?:,\d{3})+)|\d+)(?:円)?$")
PLAIN_AMOUNT_PATTERN = re.compile(r"^[+-]?\d+$")
DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日")
STRUCTURED_FIELDS = {
    "project_id",
    "email",
    "amount",
    "registered_date",
    "expected_order_date",
}
MESSAGES = {
    "NORMALIZED_PROJECT_ID": "案件IDを正規化しました。",
    "NORMALIZED_EMAIL": "メールアドレスを正規化しました。",
    "NORMALIZED_AMOUNT": "案件金額を整数へ正規化しました。",
    "NORMALIZED_DATE": "日付をISO形式へ正規化しました。",
    "NORMALIZED_STATUS": "ステータスを正規化しました。",
    "NORMALIZED_LINE_BREAK": "改行コードを統一しました。",
    "NORMALIZED_FULL_WIDTH_NUMBER": "全角数字を半角数字へ変換しました。",
    "TRIMMED_TEXT": "前後空白を除去しました。",
}


def is_blank(value: object) -> bool:
    if value is None:
        return True
    try:
        if bool(pd.isna(value)):
            return True
    except (TypeError, ValueError):
        pass
    return isinstance(value, str) and value.strip(" \u3000") == ""


def _display_equal(left: object, right: object) -> bool:
    if isinstance(right, date) and isinstance(left, str):
        return left == right.isoformat()
    return type(left) is type(right) and left == right


def _normalize_amount(value: object, enabled: bool) -> object:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, (float, Decimal)):
        if not math.isfinite(float(value)) or value != int(value):
            return value
        return int(value)
    if not isinstance(value, str):
        return value
    pattern = AMOUNT_PATTERN if enabled else PLAIN_AMOUNT_PATTERN
    match = pattern.fullmatch(value)
    if not match:
        return value
    if enabled:
        sign, digits = match.groups()
        return int(f"{sign}{digits.replace(',', '')}")
    return int(value)


def _normalize_date(value: object, enabled: bool) -> object:
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return value
    formats = DATE_FORMATS if enabled else DATE_FORMATS[:1]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return value


def _clean_cell(field: str, value: object, options: CleaningOptions) -> tuple[object, str | None]:
    if is_blank(value):
        return None, None
    if not isinstance(value, str):
        if field == "amount":
            return _normalize_amount(value, options.normalize_amount), None
        if field in {"registered_date", "expected_order_date"}:
            return _normalize_date(value, options.normalize_dates), None
        return value, None

    current = value
    changed_line = False
    changed_trim = False
    changed_digits = False
    if options.normalize_line_breaks:
        updated = current.replace("\r\n", "\n").replace("\r", "\n")
        changed_line, current = updated != current, updated
    if options.trim_whitespace:
        updated = current.strip(" \u3000")
        changed_trim, current = updated != current, updated
    if options.normalize_full_width_numbers and field in STRUCTURED_FIELDS:
        updated = current.translate(FULL_WIDTH_DIGITS)
        changed_digits, current = updated != current, updated

    specific_code = None
    if field == "project_id" and options.normalize_project_id:
        updated = current.translate(FULL_WIDTH_LETTERS).replace("－", "-").replace("＿", "_")
        updated = "".join(char.upper() if "a" <= char <= "z" else char for char in updated)
        specific_code = "NORMALIZED_PROJECT_ID" if updated != current else None
        current = updated
    elif field == "email" and options.normalize_email:
        updated = current.translate(FULL_WIDTH_LETTERS).replace("＠", "@").replace("．", ".")
        updated = "".join(char.lower() if "A" <= char <= "Z" else char for char in updated)
        specific_code = "NORMALIZED_EMAIL" if updated != current else None
        current = updated
    elif field == "amount":
        before = current
        if options.normalize_amount:
            current = current.replace("￥", "¥").replace("，", ",")
        current = _normalize_amount(current, options.normalize_amount)
        if isinstance(current, int) and str(current) != before:
            specific_code = "NORMALIZED_AMOUNT"
    elif field in {"registered_date", "expected_order_date"}:
        before = current
        current = _normalize_date(current, options.normalize_dates)
        if isinstance(current, date) and before != current.isoformat():
            specific_code = "NORMALIZED_DATE"
    elif field == "status" and options.normalize_status and current in STATUS_ALIASES:
        current = STATUS_ALIASES[current]
        specific_code = "NORMALIZED_STATUS"

    if specific_code:
        return current, specific_code
    if changed_line:
        return current, "NORMALIZED_LINE_BREAK"
    if changed_digits:
        return current, "NORMALIZED_FULL_WIDTH_NUMBER"
    if changed_trim:
        return current, "TRIMMED_TEXT"
    return current, None


def clean(
    normalized_data: pd.DataFrame, options: CleaningOptions
) -> tuple[pd.DataFrame, tuple[CorrectionRecord, ...]]:
    cleaned = normalized_data.copy(deep=True)
    # pandas 3 may infer a strict StringDtype; structured columns later receive
    # int/date values, so keep the intentionally heterogeneous business values as object.
    for field in COLUMNS:
        cleaned[field] = cleaned[field].astype(object)
    corrections: list[CorrectionRecord] = []
    for index, row in normalized_data.iterrows():
        source_row = int(row["source_row_number"])
        for field in COLUMNS:
            original = row[field]
            value, code = _clean_cell(field, original, options)
            cleaned.at[index, field] = value
            if code and not _display_equal(original, value):
                corrections.append(
                    CorrectionRecord(source_row, field, code, original, value, MESSAGES[code])
                )
    return cleaned, tuple(corrections)
