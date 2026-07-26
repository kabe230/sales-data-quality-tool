import pytest

from sales_data_quality.exceptions import DataQualityError
from sales_data_quality.loader import load_csv


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
