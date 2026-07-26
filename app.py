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
        display[column] = display[column].map(
            lambda value: (
                ""
                if value is None
                else value.isoformat()
                if isinstance(value, date)
                else str(value)
            )
        )
    return display


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

    if st.button("チェックを実行", type="primary", width="stretch"):
        try:
            dataset = load_file(content, uploaded.name, encoding=encoding, sheet_name=sheet_name)
            service = DataQualityService()
            preflight = service.inspect_schema(dataset)
            if preflight.missing_required_columns:
                st.warning("不足列: " + "、".join(preflight.missing_required_columns))
            progress = st.progress(0, text="準備中")
            result = service.process(
                dataset,
                ValidationOptions(warn_past, warn_before, warn_department),
                CleaningOptions(
                    trim, line_breaks, full_width, project_id, amount, dates, email, status
                ),
                execution_date=date.today(),
                progress_callback=lambda label, value: progress.progress(value, text=label),
            )
            st.session_state["result"] = result
            progress.empty()
        except DataQualityError as exc:
            st.error(f"{exc.code}: {exc}")
        except Exception:
            logger.exception("処理に失敗しました")
            st.error("処理中に予期しないエラーが発生しました。")

result = st.session_state.get("result")
if result:
    metrics = result.metrics
    columns = st.columns(5)
    columns[0].metric("総行数", metrics.total_rows)
    columns[1].metric("正常", metrics.normal_rows)
    columns[2].metric("警告", metrics.warning_rows)
    columns[3].metric("エラー", metrics.error_rows)
    columns[4].metric("有効率", f"{metrics.valid_rate:.1f}%")

    tab_data, tab_issues, tab_corrections, tab_summary = st.tabs(
        ["整形済みデータ", "指摘一覧", "修正履歴", "集計"]
    )
    display_names = {**COLUMNS, **INTERNAL_DISPLAY}
    with tab_data:
        st.dataframe(
            streamlit_safe_frame(result.cleaned_data.rename(columns=display_names)),
            width="stretch",
        )
    with tab_issues:
        issues = pd.DataFrame(
            [
                {
                    "元データ行番号": issue.source_row_number,
                    "重要度": issue.severity.value,
                    "指摘コード": issue.code,
                    "項目": COLUMNS[issue.field_name],
                    "内容": issue.message,
                }
                for issue in result.issues
            ]
        )
        st.dataframe(streamlit_safe_frame(issues), width="stretch", hide_index=True)
    with tab_corrections:
        corrections = pd.DataFrame(
            [
                {
                    "元データ行番号": item.source_row_number,
                    "修正コード": item.code,
                    "項目": COLUMNS[item.field_name],
                    "修正前": item.original_value,
                    "修正後": item.cleaned_value,
                }
                for item in result.corrections
            ]
        )
        st.dataframe(streamlit_safe_frame(corrections), width="stretch", hide_index=True)
    with tab_summary:
        summary_key = st.selectbox(
            "集計軸",
            ["status", "customer", "department", "registered_month", "expected_order_month"],
            format_func={
                "status": "ステータス別",
                "customer": "顧客別",
                "department": "担当部署別",
                "registered_month": "登録月別",
                "expected_order_month": "受注予定月別",
            }.get,
        )
        st.dataframe(
            streamlit_safe_frame(result.summaries[summary_key]),
            width="stretch",
            hide_index=True,
        )

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
