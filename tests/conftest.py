from __future__ import annotations

import pandas as pd
import pytest

from sales_data_quality.config import COLUMNS
from sales_data_quality.models import LoadedDataset


@pytest.fixture
def dataset() -> LoadedDataset:
    frame = pd.DataFrame(
        [
            {
                "案件ID": " p-０００１ ",
                "顧客名": " 株式会社さくら ",
                "担当者名": "山田花子",
                "メールアドレス": " HANAKO＠SAKURA.CO.JP ",
                "案件名": "基幹システム刷新",
                "案件金額": "¥1,000,000円",
                "ステータス": "受注済",
                "担当部署": "営業一部",
                "登録日": "2026/01/15",
                "受注予定日": "2026/06/30",
                "備考": "",
            },
            {
                "案件ID": "P-0002",
                "顧客名": "株式会社みどり",
                "担当者名": "鈴木太郎",
                "メールアドレス": "invalid.example.com",
                "案件名": "クラウド移行",
                "案件金額": "300000",
                "ステータス": "商談中",
                "担当部署": "",
                "登録日": "2026-02-10",
                "受注予定日": "",
                "備考": "=SUM(A1:A2)",
            },
        ],
        columns=COLUMNS.values(),
    )
    return LoadedDataset(
        frame,
        "sample.csv",
        "csv",
        "utf-8-sig",
        None,
        (2, 3),
        tuple(frame.columns),
        100,
    )
