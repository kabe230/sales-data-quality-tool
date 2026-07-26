from __future__ import annotations

from datetime import date
from time import perf_counter

import pandas as pd

from sales_data_quality.config import COLUMNS
from sales_data_quality.models import LoadedDataset
from sales_data_quality.service import DataQualityService


def test_processes_10000_rows_in_practical_time():
    rows = [
        {
            "案件ID": f"P-{index:05d}",
            "顧客名": f"顧客{index % 100}",
            "担当者名": "担当者",
            "メールアドレス": f"user{index}@example.com",
            "案件名": "テスト案件",
            "案件金額": "1000",
            "ステータス": "受注",
            "担当部署": "営業部",
            "登録日": "2026-01-01",
            "受注予定日": "",
            "備考": "",
        }
        for index in range(10_000)
    ]
    frame = pd.DataFrame(rows, columns=COLUMNS.values())
    dataset = LoadedDataset(
        frame,
        "performance.csv",
        "csv",
        "utf-8-sig",
        None,
        tuple(range(2, 10_002)),
        tuple(frame.columns),
        1_000_000,
    )

    started = perf_counter()
    result = DataQualityService().process(dataset, execution_date=date(2026, 7, 1))
    elapsed = perf_counter() - started

    assert result.metrics.total_rows == 10_000
    assert result.metrics.error_rows == 0
    # Coverage instrumentation roughly doubles runtime on Windows CI.
    assert elapsed < 15
