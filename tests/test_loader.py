from io import BytesIO

import pandas as pd
import pytest

from sales_data_quality.exceptions import DataQualityError
from sales_data_quality.loader import list_excel_sheets, load_csv, load_excel, load_file


def test_csv_loader_preserves_logical_source_rows():
    content = (
        "案件ID,顧客名,担当者名,メールアドレス,案件名,案件金額,ステータス,"
        "担当部署,登録日,受注予定日,備考\r\n"
        'P-1,会社,担当,a@example.com,案件,100,受注,営業,2026-01-01,,"複数行\r\n備考"\r\n'
    ).encode()
    dataset = load_csv(content, "sample.csv")
    assert dataset.source_row_numbers == (2,)
    assert dataset.dataframe.iloc[0]["備考"] == "複数行\r\n備考"


def test_csv_size_limit():
    with pytest.raises(DataQualityError, match="10 MiB"):
        load_csv(b"x" * (10 * 1024 * 1024 + 1), "large.csv")


def test_csv_row_limit():
    header = (
        "案件ID,顧客名,担当者名,メールアドレス,案件名,案件金額,ステータス,"
        "担当部署,登録日,受注予定日,備考\n"
    )
    row = "P-1,会社,担当,a@example.com,案件,100,受注,営業,2026-01-01,,\n"
    with pytest.raises(DataQualityError) as exc_info:
        load_csv((header + row * 10_001).encode(), "too-many.csv")
    assert exc_info.value.code == "ROW_LIMIT_EXCEEDED"


def test_excel_sheet_selection_and_source_rows():
    frame = pd.DataFrame(
        [
            ["P-1", "会社"],
            [None, None],
            ["P-2", "会社2"],
        ],
        columns=["案件ID", "顧客名"],
    )
    content = BytesIO()
    with pd.ExcelWriter(content, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name="案件", index=False)
        frame.iloc[:1].to_excel(writer, sheet_name="予備", index=False)
    excel_bytes = content.getvalue()

    assert list_excel_sheets(excel_bytes) == ["案件", "予備"]
    dataset = load_excel(excel_bytes, "projects.xlsx", "案件")
    assert dataset.source_row_numbers == (2, 4)
    assert dataset.blank_row_count == 1


def test_empty_and_unsupported_files_are_rejected():
    with pytest.raises(DataQualityError) as empty:
        load_csv(b"", "empty.csv")
    assert empty.value.code == "EMPTY_FILE"

    with pytest.raises(DataQualityError) as unsupported:
        load_file(b"data", "projects.xls")
    assert unsupported.value.code == "UNSUPPORTED_FILE_TYPE"
