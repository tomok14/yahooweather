"""
location.dbに保存されている地点を選択します
"""

import sqlite3
from pathlib import Path
from wcwidth import wcswidth
from tomlkit import dumps
from tomlkit import table

BASE_URL = "https://weather.yahoo.co.jp"
CONFIG_FILE = Path.home() / ".config/yahooweather/yahooweather.conf"


def print_rows(rows, columns=3):
    """DBの地点表示"""

    items = [f"{i:2d}: {row['name']}" for i, row in enumerate(rows, start=1)]

    column_width = max(wcswidth(item) for item in items) + 4

    for i in range(0, len(items), columns):
        line = ""

        for item in items[i : i + columns]:
            line += item + " " * (column_width - wcswidth(item))

        print(line.rstrip())


def save_config(name, url):
    """
    選択された地点をyahooweather.py の
    コンフィグ(~/.config/yahooweather/yahooweather.conf) に
    書き込みます
    """
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

    config = table()
    config["name"] = name
    config["url"] = url

    document = table()
    document["yahoo"] = config

    CONFIG_FILE.write_text(
        dumps(document),
        encoding="utf-8",
    )

    print()
    print(f"設定を書き込みました: {CONFIG_FILE}")
    print(f"name = {name}")
    print(f"url = {url}")


def proc():
    """proc"""
    conn = sqlite3.connect("location.db")
    conn.row_factory = sqlite3.Row

    try:
        parent_id = None
        level = 1
        history = []

        while True:
            rows = conn.execute(
                """
                SELECT *
                FROM weather_location
                WHERE level = ?
                  AND parent_id IS ?
                ORDER BY id
                """,
                (level, parent_id),
            ).fetchall()

            if not rows:
                print("次のレベルはありません。")
                break

            print()
            print(f"=== level {level} ===")
            print_rows(rows)

            while True:
                choice = input("番号を選択してください（u: 上のレベル）: ").strip()

                if choice.lower() == "u":
                    if not history:
                        print("これ以上上のレベルには戻れません。")
                        continue

                    parent_id, level = history.pop()
                    break

                try:
                    choice_num = int(choice)
                except ValueError:
                    print("数字または「u」を入力してください。")
                    continue

                if not 1 <= choice_num <= len(rows):
                    print(f"1～{len(rows)}の番号を入力してください。")
                    continue

                row = rows[choice_num - 1]

                print(f"選択: {row['name']}")
                print(dict(row))

                # 次の階層が存在するか確認
                next_level = level + 1

                next_rows = conn.execute(
                    """
                    SELECT *
                    FROM weather_location
                    WHERE level = ?
                      AND parent_id = ?
                    """,
                    (next_level, row["id"]),
                ).fetchall()

                if not next_rows:
                    # 最終階層なのでURLを保存
                    url = row["href"]

                    if url.startswith("/"):
                        url = BASE_URL + url

                    save_config(row["name"], url)
                    return

                # 現在位置を保存して次の階層へ
                history.append((parent_id, level))

                parent_id = row["id"]
                level = next_level
                break

    finally:
        conn.close()


def main():
    """main"""
    proc()


if __name__ == "__main__":
    main()
