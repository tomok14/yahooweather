"""
location.dbに保存されている地点を選択します
"""

import re
import shutil
import sqlite3
from pathlib import Path

import tomlkit
from tomlkit import aot, dumps, parse, table
from wcwidth import wcswidth

BASE_URL = "https://weather.yahoo.co.jp"
CONFIG_FILE = Path.home() / ".config/yahooweather/yahooweather.conf"
DATA_DIR = Path.home() / ".local" / "share" / "yahooweather"
LOCATION_FILE = DATA_DIR / "location.db"
PACKAGE_LOCATION_FILE = Path(__file__).parent / "data" / "location.db"


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
    追記します
    形式は複数サイト対応の [[yahoo]] (Array of Tables) です
    """
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

    new_entry = table()
    new_entry["name"] = name
    new_entry["url"] = url

    if CONFIG_FILE.is_file():
        text = CONFIG_FILE.read_text(encoding="utf-8")
        if text.strip() == "":
            document = tomlkit.document()
            sites = aot()
            sites.append(new_entry)
            document["yahoo"] = sites
        else:
            document = parse(text)
            yahoo = document.get("yahoo")
            if yahoo is None:
                sites = aot()
                sites.append(new_entry)
                document["yahoo"] = sites
            elif isinstance(yahoo, dict):
                # 旧形式 [yahoo] (単一サイト) を新形式 [[yahoo]] に移行して追記
                if yahoo.get("url") == url:
                    print(f"既に登録されています: name = {name}, url = {url}")
                    return
                old = table()
                old["name"] = yahoo.get("name", "")
                old["url"] = yahoo.get("url", "")
                sites = aot()
                sites.append(old)
                sites.append(new_entry)
                document["yahoo"] = sites
            elif isinstance(yahoo, list):
                for entry in yahoo:
                    if isinstance(entry, dict) and entry.get("url") == url:
                        print(f"既に登録されています: name = {name}, url = {url}")
                        return
                yahoo.append(new_entry)
            else:
                raise TypeError(f"不正な設定形式です: {CONFIG_FILE}")
    else:
        document = tomlkit.document()
        sites = aot()
        sites.append(new_entry)
        document["yahoo"] = sites

    text = dumps(document)
    # [[yahoo]] ブロックの前には空行を1行入れる
    text = re.sub(r"(?<!\n)\n\[\[yahoo\]\]", "\n\n[[yahoo]]", text)

    CONFIG_FILE.write_text(
        text,
        encoding="utf-8",
    )

    print()
    print(f"設定を追記しました: {CONFIG_FILE}")
    print(f"name = {name}")
    print(f"url = {url}")
    print()
    print("登録済みサイト一覧:")
    for i, entry in enumerate(document["yahoo"], start=1):
        print(f"{i}: {entry.get('name')} ({entry.get('url')})")


def init_location_db() -> None:
    """location.dbコピー"""
    if LOCATION_FILE.exists():
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PACKAGE_LOCATION_FILE, LOCATION_FILE)


def proc():
    """proc"""
    init_location_db()
    conn = sqlite3.connect(LOCATION_FILE)
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
