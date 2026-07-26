from __future__ import annotations

import logging
from datetime import date

import pandas as pd
import streamlit as st

from sales_data_quality.config import COLUMNS, INTERNAL_DISPLAY, CleaningOptions, ValidationOptions
from sales_data_quality.exceptions import DataQualityError
from sales_data_quality.exporter import to_csv_bytes, to_excel_bytes
from sales_data_quality.loader import list_excel_sheets, load_file
from sales_data_quality.service import DataQualityService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sales_data_quality")


def streamlit_safe_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Arrowで扱えない混在型列だけを表示用文字列へ変換する。"""
    display = frame.copy(deep=True)
    for column in display.select_dtypes(include="object").columns:
        display[column] = display[column].map(display_value)
    return display


def display_value(value: object) -> str:
    if value is None:
        return ""
    try:
        if bool(pd.isna(value)):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


st.set_page_config(page_title="営業案件データ品質チェック", page_icon="✓", layout="wide")
st.title("営業案件データ品質チェック")
st.caption("CSV / Excelを安全に整形・検証し、集計レポートを作成します。")

with st.sidebar:
    st.header("処理設定")
    trim = st.checkbox("前後空白を除去", True)
    line_breaks = st.checkbox("改行コードを統一", True)
    full_width = st.checkbox("全角数字を半角化", True)
    project_id = st.checkbox("案件IDを正規化", True)
    email = st.checkbox("メールを正規化", True)
    amount = st.checkbox("金額を正規化", True)
    dates = st.checkbox("日付を正規化", True)
    status = st.checkbox("ステータスを正規化", True)
    st.divider()
    warn_past = st.checkbox("過去の受注予定日を警告", True)
    warn_before = st.checkbox("登録日前の受注予定日を警告", True)
    warn_department = st.checkbox("担当部署の未入力を警告", True)

uploaded = st.file_uploader("案件データを選択", type=["csv", "xlsx"])
dataset = None
preflight = None
load_error = None
if uploaded:
    content = uploaded.getvalue()
    encoding = "auto"
    sheet_name = None
    if uploaded.name.lower().endswith(".csv"):
        encoding = st.selectbox(
            "CSV文字コード",
            ["auto", "utf-8", "cp932"],
            format_func=lambda x: {
                "auto": "自動判定",
                "utf-8": "UTF-8",
                "cp932": "Shift-JIS",
            }[x],
        )
    else:
        try:
            sheet_name = st.selectbox("対象シート", list_excel_sheets(content))
        except DataQualityError as exc:
            st.error(f"{exc.code}: {exc}")
            st.stop()

    try:
        dataset = load_file(content, uploaded.name, encoding=encoding, sheet_name=sheet_name)
        preflight = DataQualityService().inspect_schema(dataset)
    except DataQualityError as exc:
        load_error = exc

    st.subheader("事前確認")
    if load_error:
        st.error(f"{load_error.code}: {load_error}")
    elif dataset and preflight:
        preflight_columns = st.columns(4)
        preflight_columns[0].metric("ファイルサイズ", f"{dataset.file_size_bytes / 1024:.1f} KiB")
        preflight_columns[1].metric("処理対象行数", preflight.source_row_count)
        preflight_columns[2].metric("空行除外数", preflight.blank_row_count)
        preflight_columns[3].metric("追加列数", len(preflight.extra_columns))
        if preflight.extra_columns:
            st.info("保持する追加列: " + "、".join(preflight.extra_columns))
        if preflight.missing_required_columns:
            st.error("不足列: " + "、".join(preflight.missing_required_columns))
        if preflight.reserved_conflicts:
            st.error("予約列との衝突: " + "、".join(preflight.reserved_conflicts))
        if not preflight.missing_required_columns and not preflight.reserved_conflicts:
            st.success("処理を続行できます。")

    blocked = bool(
        load_error
        or dataset is None
        or preflight is None
        or preflight.missing_required_columns
        or preflight.reserved_conflicts
    )
    if st.button("チェックを実行", type="primary", width="stretch", disabled=blocked):
        try:
            progress = st.progress(0, text="準備中")
            result = DataQualityService().process(
                dataset,
                ValidationOptions(warn_past, warn_before, warn_department),
                CleaningOptions(
                    trim, line_breaks, full_width, project_id, amount, dates, email, status
                ),
                execution_date=date.today(),
                progress_callback=lambda label, value: progress.progress(value, text=label),
            )
            st.session_state["result"] = result
            st.session_state["result_filename"] = dataset.source_filename
            progress.empty()
        except DataQualityError as exc:
            st.error(f"{exc.code}: {exc}")
        except Exception:
            logger.exception("処理に失敗しました")
            st.error("処理中に予期しないエラーが発生しました。")

result = st.session_state.get("result")
if uploaded and st.session_state.get("result_filename") != uploaded.name:
    result = None
if result:
    metrics = result.metrics
    columns = st.columns(5)
    columns[0].metric("総行数", metrics.total_rows)
    columns[1].metric("正常", metrics.normal_rows)
    columns[2].metric("警告", metrics.warning_rows)
    columns[3].metric("エラー", metrics.error_rows)
    columns[4].metric("有効率", f"{metrics.valid_rate:.1f}%")

    tab_overview, tab_data, tab_issues, tab_corrections, tab_summary, tab_log = st.tabs(
        ["概要", "整形済みデータ", "指摘一覧", "修正履歴", "集計", "処理ログ"]
    )
    display_names = {**COLUMNS, **INTERNAL_DISPLAY}
    with tab_overview:
        overview = pd.DataFrame(
            [
                ("総行数", metrics.total_rows),
                ("正常行数", metrics.normal_rows),
                ("警告行数", metrics.warning_rows),
                ("エラー行数", metrics.error_rows),
                ("正常率", f"{metrics.normal_rate:.1f}%"),
                ("有効率", f"{metrics.valid_rate:.1f}%"),
                ("集計対象行数", metrics.aggregation_rows),
                ("除外行数", metrics.excluded_rows),
                ("集計対象金額", metrics.aggregation_amount),
                ("除外金額", metrics.excluded_amount),
                ("平均金額", metrics.average_amount),
                ("最大金額", metrics.maximum_amount),
                ("最小金額", metrics.minimum_amount),
                ("エラー指摘数", metrics.error_issue_count),
                ("警告指摘数", metrics.warning_issue_count),
            ],
            columns=["指標", "値"],
        )
        st.dataframe(streamlit_safe_frame(overview), width="stretch", hide_index=True)
    with tab_data:
        st.dataframe(
            streamlit_safe_frame(result.cleaned_data.rename(columns=display_names)),
            width="stretch",
        )
    with tab_issues:
        issue_columns = [
            "元データ行番号",
            "重要度",
            "指摘コード",
            "項目",
            "修正前の値",
            "整形後の値",
            "内容",
        ]
        issues = pd.DataFrame(
            [
                {
                    "元データ行番号": issue.source_row_number,
                    "重要度": issue.severity.value,
                    "指摘コード": issue.code,
                    "項目": COLUMNS[issue.field_name],
                    "修正前の値": issue.original_value,
                    "整形後の値": issue.cleaned_value,
                    "内容": issue.message,
                }
                for issue in result.issues
            ],
            columns=issue_columns,
        )
        st.dataframe(streamlit_safe_frame(issues), width="stretch", hide_index=True)
    with tab_corrections:
        correction_columns = [
            "元データ行番号",
            "修正コード",
            "項目",
            "修正前",
            "修正後",
            "内容",
        ]
        corrections = pd.DataFrame(
            [
                {
                    "元データ行番号": item.source_row_number,
                    "修正コード": item.code,
                    "項目": COLUMNS[item.field_name],
                    "修正前": item.original_value,
                    "修正後": item.cleaned_value,
                    "内容": item.message,
                }
                for item in result.corrections
            ],
            columns=correction_columns,
        )
        st.dataframe(streamlit_safe_frame(corrections), width="stretch", hide_index=True)
    with tab_summary:
        summary_key = st.selectbox(
            "集計軸",
            [
                "status",
                "customer",
                "department",
                "registered_month",
                "expected_order_month",
                "issue_breakdown",
            ],
            format_func={
                "status": "ステータス別",
                "customer": "顧客別",
                "department": "担当部署別",
                "registered_month": "登録月別",
                "expected_order_month": "受注予定月別",
                "issue_breakdown": "指摘内訳",
            }.get,
        )
        st.dataframe(
            streamlit_safe_frame(result.summaries[summary_key]),
            width="stretch",
            hide_index=True,
        )
    with tab_log:
        st.json(result.processing_log)

    csv_col, excel_col = st.columns(2)
    csv_col.download_button(
        "整形済みCSVをダウンロード",
        to_csv_bytes(result),
        "cleaned_sales_data.csv",
        "text/csv",
        width="stretch",
    )
    excel_col.download_button(
        "Excelレポートをダウンロード",
        to_excel_bytes(result),
        "sales_data_quality_report.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )
