from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).parents[1]
SAMPLE_DIRECTORY = ROOT / "sample_data"
BASE_COLUMNS = [
    "案件ID",
    "顧客名",
    "担当者名",
    "メールアドレス",
    "案件名",
    "案件金額",
    "ステータス",
    "担当部署",
    "登録日",
    "受注予定日",
    "備考",
]
STATUSES = ["新規", "商談中", "見積提出", "受注", "失注", "保留"]
STATUS_ALIASES = {
    "新規": " 新規 ",
    "商談中": " 商談中 ",
    "見積提出": "見積り提出",
    "受注": "受注済",
    "失注": "失注済",
    "保留": "一時保留",
}
CUSTOMERS = [
    "株式会社青空",
    "株式会社みどり",
    "株式会社さくら",
    "株式会社白波",
    "株式会社橙",
    "株式会社紫",
    "株式会社銀河",
    "株式会社未来",
    "株式会社若葉",
    "株式会社北斗",
]
CONTACTS = ["佐藤太郎", "鈴木花子", "高橋健", "伊藤美咲", "田中一郎"]
PROJECTS = [
    "販売管理システム",
    "クラウド移行",
    "顧客分析基盤",
    "ECサイト改修",
    "モバイル対応",
    "データ連携",
    "在庫管理",
    "API開発",
]
DEPARTMENTS = ["営業一部", "営業二部", "開発営業部", "ソリューション営業部"]
CHANNELS = ["Web問い合わせ", "既存顧客", "展示会", "紹介"]
FULL_WIDTH_DIGITS = str.maketrans("0123456789", "０１２３４５６７８９")


def write_csv(
    filename: str,
    rows: list[dict[str, str]],
    *,
    extra_columns: list[str] | None = None,
    blank_rows: int = 0,
) -> None:
    columns = [*BASE_COLUMNS, *(extra_columns or [])]
    path = SAMPLE_DIRECTORY / filename
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        for _ in range(blank_rows):
            writer.writerow({})


def base_row(prefix: str, number: int) -> dict[str, str]:
    status = STATUSES[(number - 1) % len(STATUSES)]
    registered_month_index = (number - 1) % 18
    registered_year = 2025 + registered_month_index // 12
    registered_month = registered_month_index % 12 + 1
    registered_day = (number - 1) % 20 + 1
    expected = ""
    if status in {"商談中", "見積提出", "保留"}:
        expected_month = (number - 1) % 12 + 1
        expected = f"2099-{expected_month:02d}-28"
    return {
        "案件ID": f"{prefix}-{number:04d}",
        "顧客名": CUSTOMERS[(number - 1) % len(CUSTOMERS)],
        "担当者名": CONTACTS[(number - 1) % len(CONTACTS)],
        "メールアドレス": f"sales{number:03d}@example.co.jp",
        "案件名": f"{PROJECTS[(number - 1) % len(PROJECTS)]} {number:03d}",
        "案件金額": str(250_000 + number * 37_500),
        "ステータス": status,
        "担当部署": DEPARTMENTS[(number - 1) % len(DEPARTMENTS)],
        "登録日": f"{registered_year}-{registered_month:02d}-{registered_day:02d}",
        "受注予定日": expected,
        "備考": f"サンプル案件 {number:03d}",
    }


def make_all_valid_rows() -> list[dict[str, str]]:
    return [base_row("N", number) for number in range(1, 101)]


def make_auto_cleanup_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for number in range(1, 101):
        clean = base_row("C", number)
        status = clean["ステータス"]
        expected = clean["受注予定日"]
        project_digits = f"{number:04d}".translate(FULL_WIDTH_DIGITS)
        amount_digits = f"{int(clean['案件金額']):,}".translate(FULL_WIDTH_DIGITS)
        registered = clean["登録日"]
        raw_email = (
            f"sales{number:03d}".translate(FULL_WIDTH_DIGITS) + "@example.co.jp"
            if number % 10 == 1
            else f" SALES{number:03d}＠EXAMPLE.CO.JP "
        )
        row = {
            "案件ID": f" c－{project_digits} ",
            "顧客名": f" {clean['顧客名']} ",
            "担当者名": f" {clean['担当者名']} ",
            "メールアドレス": raw_email,
            "案件名": f" {clean['案件名']} ",
            "案件金額": f"￥{amount_digits}円",
            "ステータス": STATUS_ALIASES[status],
            "担当部署": f" {clean['担当部署']} ",
            "登録日": (
                registered.replace("-", "/")
                if number % 2
                else f"{registered[:4]}年{int(registered[5:7])}月{int(registered[8:])}日"
            ),
            "受注予定日": expected.replace("-", "/") if expected else "",
            "備考": (
                " 提案内容\r\n次回確認 " if number % 10 == 0 else f" 表記ゆれサンプル {number:03d} "
            ),
            "流入経路": CHANNELS[(number - 1) % len(CHANNELS)],
        }

        if 91 <= number <= 95:
            row["担当部署"] = ""
        elif number == 96:
            row["顧客名"] = ""
        elif number == 97:
            row["メールアドレス"] = "sales.example.co.jp"
        elif number == 98:
            row["案件金額"] = "１円２"
        elif number == 99:
            row["ステータス"] = "対応中"
        elif number == 100:
            row["ステータス"] = " 商談中 "
            row["受注予定日"] = ""
        rows.append(row)
    return rows


def make_quality_issue_rows() -> list[dict[str, str]]:
    rows = [base_row("Q", number) for number in range(1, 101)]

    rows[45]["担当部署"] = ""
    rows[46]["担当部署"] = ""
    for index in (47, 48):
        rows[index]["ステータス"] = "保留"
        rows[index]["登録日"] = "2019-01-01"
        rows[index]["受注予定日"] = "2020-01-01"
    rows[49]["ステータス"] = "保留"
    rows[49]["登録日"] = "2026-06-30"
    rows[49]["受注予定日"] = "2026-06-01"

    for number in range(51, 101):
        row = rows[number - 1]
        row["ステータス"] = "受注"
        row["受注予定日"] = ""
        issue_kind = (number - 51) % 10
        if issue_kind == 0:
            row["顧客名"] = ""
        elif issue_kind == 1:
            row["案件ID"] = f"不正 ID {number}"
        elif issue_kind == 2:
            row["メールアドレス"] = "invalid.example.co.jp"
        elif issue_kind == 3:
            row["案件金額"] = "1円2"
        elif issue_kind == 4:
            row["案件金額"] = "-1000"
        elif issue_kind == 5:
            row["案件金額"] = "1000000000000000"
        elif issue_kind == 6:
            row["登録日"] = "2026-13-01"
        elif issue_kind == 7:
            row["登録日"] = "2099-01-01"
        elif issue_kind == 8:
            row["ステータス"] = "対応中"
        else:
            row["ステータス"] = "商談中"
            row["受注予定日"] = ""

    rows[98]["案件ID"] = "Q-DUPLICATE"
    rows[99]["案件ID"] = "Q-DUPLICATE"
    return rows


def main() -> None:
    write_csv("sample_all_valid.csv", make_all_valid_rows())
    write_csv(
        "sample_auto_cleanup.csv",
        make_auto_cleanup_rows(),
        extra_columns=["流入経路"],
        blank_rows=2,
    )
    write_csv("sample_quality_issues.csv", make_quality_issue_rows())


if __name__ == "__main__":
    main()
