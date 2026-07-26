from __future__ import annotations

from dataclasses import dataclass

COLUMNS = {
    "project_id": "案件ID",
    "customer_name": "顧客名",
    "contact_person": "担当者名",
    "email": "メールアドレス",
    "project_name": "案件名",
    "amount": "案件金額",
    "status": "ステータス",
    "department": "担当部署",
    "registered_date": "登録日",
    "expected_order_date": "受注予定日",
    "notes": "備考",
}
DISPLAY_TO_INTERNAL = {display: internal for internal, display in COLUMNS.items()}
REQUIRED_FIELDS = (
    "project_id",
    "customer_name",
    "contact_person",
    "email",
    "project_name",
    "amount",
    "status",
    "registered_date",
)
INTERNAL_COLUMNS = (
    "source_row_number",
    "check_result",
    "error_count",
    "warning_count",
    "issue_summary",
)
INTERNAL_DISPLAY = {
    "source_row_number": "元データ行番号",
    "check_result": "チェック結果",
    "error_count": "エラー件数",
    "warning_count": "警告件数",
    "issue_summary": "指摘内容",
}
RESERVED_NAMES = set(INTERNAL_COLUMNS) | set(INTERNAL_DISPLAY.values())
ALLOWED_STATUSES = ("新規", "商談中", "見積提出", "受注", "失注", "保留")
STATUS_ALIASES = {
    "見積り提出": "見積提出",
    "見積提出済": "見積提出",
    "受注済": "受注",
    "成約": "受注",
    "失注済": "失注",
    "一時保留": "保留",
}
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_ROWS = 10_000
MAX_AMOUNT = 999_999_999_999_999


@dataclass(frozen=True)
class CleaningOptions:
    trim_whitespace: bool = True
    normalize_line_breaks: bool = True
    normalize_full_width_numbers: bool = True
    normalize_project_id: bool = True
    normalize_amount: bool = True
    normalize_dates: bool = True
    normalize_email: bool = True
    normalize_status: bool = True


@dataclass(frozen=True)
class ValidationOptions:
    warn_past_expected_order_date: bool = True
    warn_expected_date_before_registered_date: bool = True
    warn_missing_department: bool = True
