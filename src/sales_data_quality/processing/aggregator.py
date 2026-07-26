from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

from sales_data_quality.config import ALLOWED_STATUSES
from sales_data_quality.models import Severity, SummaryMetrics, ValidationIssue


def _average(total: int, count: int) -> Decimal | None:
    if not count:
        return None
    return (Decimal(total) / Decimal(count)).quantize(Decimal("0.01"), ROUND_HALF_UP)


def aggregate(
    data: pd.DataFrame, issues: tuple[ValidationIssue, ...]
) -> tuple[SummaryMetrics, dict[str, pd.DataFrame]]:
    valid = data[data["check_result"] != "ERROR"].copy()
    excluded = data[data["check_result"] == "ERROR"]
    amounts = [int(value) for value in valid["amount"] if isinstance(value, int)]
    excluded_amounts = [int(value) for value in excluded["amount"] if isinstance(value, int)]
    total = len(data)
    normal = int((data["check_result"] == "NORMAL").sum())
    warning = int((data["check_result"] == "WARNING").sum())
    error = int((data["check_result"] == "ERROR").sum())
    metrics = SummaryMetrics(
        total,
        normal,
        warning,
        error,
        normal / total * 100 if total else 0.0,
        len(valid),
        len(excluded),
        sum(amounts),
        sum(excluded_amounts),
        _average(sum(amounts), len(amounts)),
        max(amounts) if amounts else None,
        min(amounts) if amounts else None,
        sum(issue.severity is Severity.ERROR for issue in issues),
        sum(issue.severity is Severity.WARNING for issue in issues),
        len(valid) / total * 100 if total else 0.0,
    )

    def grouped(frame: pd.DataFrame, key: str, include_extrema: bool = False) -> pd.DataFrame:
        columns = [key, "project_count", "total_amount", "average_amount"]
        if include_extrema:
            columns += ["maximum_amount", "minimum_amount"]
        if frame.empty:
            return pd.DataFrame(columns=columns)
        result = (
            frame.groupby(key, dropna=False)["amount"]
            .agg(
                project_count="size", total_amount="sum", maximum_amount="max", minimum_amount="min"
            )
            .reset_index()
        )
        result["average_amount"] = result.apply(
            lambda row: _average(int(row["total_amount"]), int(row["project_count"])), axis=1
        )
        return result[columns]

    status_rows = []
    for status in ALLOWED_STATUSES:
        frame = valid[valid["status"] == status]
        count = len(frame)
        total_amount = int(frame["amount"].sum()) if count else 0
        status_rows.append(
            {
                "status": status,
                "project_count": count,
                "total_amount": total_amount,
                "average_amount": _average(total_amount, count),
            }
        )
    status_summary = pd.DataFrame(status_rows)

    customer = grouped(valid, "customer_name", True).sort_values("customer_name", kind="stable")
    department_source = valid.copy()
    department_source["department"] = department_source["department"].fillna("未設定")
    department = grouped(department_source, "department")
    if not department.empty:
        department["_last"] = department["department"].eq("未設定")
        department = department.sort_values(["_last", "department"]).drop(columns="_last")

    registered_source = valid.copy()
    registered_source["registered_month"] = registered_source["registered_date"].map(
        lambda value: value.strftime("%Y-%m") if hasattr(value, "strftime") else None
    )
    registered = grouped(
        registered_source[registered_source["registered_month"].notna()], "registered_month"
    ).sort_values("registered_month")

    forecast = valid[
        valid["status"].isin({"新規", "商談中", "見積提出", "保留"})
        & valid["expected_order_date"].notna()
    ].copy()
    forecast["expected_order_month"] = forecast["expected_order_date"].map(
        lambda value: value.strftime("%Y-%m") if hasattr(value, "strftime") else None
    )
    expected = grouped(forecast, "expected_order_month").drop(columns="average_amount")
    expected = expected.rename(columns={"project_count": "project_count"})
    if not expected.empty:
        expected = expected.sort_values("expected_order_month")

    breakdown_rows = []
    counts: dict[tuple[str, str], list[int]] = {}
    for issue in issues:
        counts.setdefault((issue.severity.value, issue.code), []).append(issue.source_row_number)
    for (severity, code), rows in counts.items():
        breakdown_rows.append(
            {
                "severity": severity,
                "code": code,
                "issue_count": len(rows),
                "affected_row_count": len(set(rows)),
            }
        )
    issue_breakdown = pd.DataFrame(
        breakdown_rows,
        columns=["severity", "code", "issue_count", "affected_row_count"],
    )
    if not issue_breakdown.empty:
        issue_breakdown["_order"] = issue_breakdown["severity"].map({"ERROR": 0, "WARNING": 1})
        issue_breakdown = issue_breakdown.sort_values(["_order", "code"]).drop(columns="_order")

    return metrics, {
        "status": status_summary.reset_index(drop=True),
        "customer": customer.reset_index(drop=True),
        "department": department.reset_index(drop=True),
        "registered_month": registered.reset_index(drop=True),
        "expected_order_month": expected.reset_index(drop=True),
        "issue_breakdown": issue_breakdown.reset_index(drop=True),
    }
