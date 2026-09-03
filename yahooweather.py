"""
yahoo天気を表示する

[configファイル]
~/.config/yahooweather/yahooweather.conf

"""

import logging
import sys
import os
import re
import argparse
import tomllib
from typing import Any
from pathlib import Path
from dataclasses import dataclass
from zoneinfo import ZoneInfo
from rich.console import Console
from rich.table import Table
from rich import box
from bs4 import BeautifulSoup
from requests_cache import CachedSession
import selector

CONFIG_DIR = Path.home() / ".config" / "yahooweather"
CONFIG_FILE = CONFIG_DIR / "yahooweather.conf"
CACHE_FILE = CONFIG_DIR / "cache"

logger = logging.getLogger(__name__)


@dataclass(frozen=False)
class Config:
    """Config"""

    url: str = ""
    name: str = ""


def get_html(config: Config, force=False):
    """HTML取得"""
    # スクレイピング対象の URL にリクエストを送り HTML を取得する
    url = config.url
    # res = requests.get(url)
    # キャッシュセッションの作成（SQLiteを使用）

    session = CachedSession(CACHE_FILE, expire_after=60 * 60 * 3)  # 3時間キャッシュ

    res = session.request("GET", url, force_refresh=force)

    if res.from_cache:
        logger.debug("キャッシュ")
        jst = ZoneInfo("Asia/Tokyo")
        logger.debug(res.created_at.astimezone(jst))
    else:
        logger.debug("新規取得")

    return res.text


def sonota(tr):
    """その他項目"""
    row = []
    for td in tr.find_all("td"):
        text = td.get_text()
        text = " ".join(text.split())
        row.append(text)
    return row


def tenki(tr):
    """天気"""
    row = []
    for td in tr.find_all("td"):
        text = td.get_text()
        text = " ".join(text.split())
        text = text.replace("℃", "度")

        emoji = ""
        if "晴" in text:
            emoji = emoji + "🌞"
        if "雨" in text:
            emoji = emoji + "☔"
        if "曇" in text:
            emoji = emoji + "☁"

        if "大雨" in text or "強雨" in text or "暴風雨" in text:
            text = f"[bold underline italic on dark_magenta]{text}[/]"
        elif "雨" in text:
            text = f"[bold on blue]{text}[/]"

        text = text + emoji

        row.append(text)
    return row


def kousuiryo(tr):
    """降水量"""
    row = []
    for i, td in enumerate(tr.find_all("td")):
        text = td.get_text()
        text = " ".join(text.split())

        if i != 0:
            value = float(text)
            if value >= 10.0:
                text = f"[bold deep_pink3]{text}[/]"
            elif value >= 3.0:
                text = f"[light_salmon1]{text}[/]"
            elif value > 0.0:
                # text = f"\033[34m{text}\033[0m"
                text = f"[turquoise2]{text}[/]"
        row.append(text)
    return row


def fusoku(tr):
    """風速"""
    row = []
    for i, td in enumerate(tr.find_all("td")):
        text = td.get_text()
        text = " ".join(text.split())

        if i != 0:
            match = re.search(r"(\d+(?:\.\d+)?)$", text)
            if match:
                value = float(match.group(1))
                if value >= 3:
                    # text = f"\033[32m{text}\033[0m"
                    text = f"[green]{text}[/]"

        row.append(text)
    return row


def kion(tr):
    """気温"""
    row = []
    for i, td in enumerate(tr.find_all("td")):
        text = td.get_text()
        text = " ".join(text.split())
        text = text.replace("℃", "度")

        if i != 0:
            match = re.search(r"(\d+(?:\.\d+)?)$", text)
            if match:
                value = float(match.group(1))
                if value >= 35:
                    text = f"[red]{text}[/]"
                elif value >= 30:
                    text = f"[yellow]{text}[/]"

        row.append(text)
    return row


def kion_week(tr):
    """気温（週間）"""
    row = []
    for i, td in enumerate(tr.find_all("td")):
        text = td.get_text()
        text = " ".join(text.split())
        text = text.replace("℃", "度")

        if i != 0:
            match = re.search(r"(\d+) (\d+)", text)
            if match:
                value1 = int(match.group(1))
                value2 = int(match.group(2))
                text1 = f"{value1}"
                text2 = f"{value2}"
                if value1 >= 35:
                    text1 = f"[red]{value1}[/]"
                elif value1 >= 30:
                    text1 = f"[yellow]{value1}[/]"
                text = f"{text1} {text2}"

        row.append(text)
    return row


def shitsudo(tr):
    """湿度"""
    row = []
    for i, td in enumerate(tr.find_all("td")):
        text = td.get_text()
        text = " ".join(text.split())

        if i != 0:
            match = re.search(r"(\d+(?:\.\d+)?)$", text)
            if match:
                value = float(match.group(1))
                if value >= 90:
                    text = f"[blue]{text}[/]"

        row.append(text)
    return row


def disp_day_table(config: Config, soup, idname):
    """日天気予報"""
    pinpoint = soup.find("div", id=idname)
    title = pinpoint.find("h3") if pinpoint else None
    title_text = ""
    if title:
        title_text = title.get_text()
        title_text = " ".join(title_text.split())

    yahoo_table = pinpoint.find("table") if pinpoint else None
    if yahoo_table is None:
        return

    title_text = f"{config.name} - {title_text}"
    table = Table(
        title=title_text,
        show_header=True,
        box=box.ROUNDED,
    )

    rows = []

    for tr in yahoo_table.find_all("tr"):
        first_td = tr.find("td")

        if "降水量" in first_td.get_text():
            row = kousuiryo(tr)
        elif "風速" in first_td.get_text():
            row = fusoku(tr)
        elif "気温" in first_td.get_text():
            row = kion(tr)
        elif "湿度" in first_td.get_text():
            row = shitsudo(tr)
        elif "天気" in first_td.get_text():
            row = tenki(tr)
        else:
            row = sonota(tr)

        rows.append(row)

    # 列数を決定
    for i in range(len(rows[0])):
        table.add_column(
            header=rows[0][i],
            justify="center",
        )

    for row in rows[1:]:
        table.add_row(*row)

    Console().print(table)


def kousuikakuritsu(tr):
    """降水確率"""
    row = []
    for i, td in enumerate(tr.find_all("td")):
        text = td.get_text()
        text = " ".join(text.split())

        if i != 0:
            value = float(text)
            if value >= 60:
                text = f"[bold magenta3]{text}[/]"
            elif value >= 30:
                # text = f"\033[34m{text}\033[0m"
                text = f"[turquoise2]{text}[/]"
        row.append(text)
    return row


def disp_week_table(config: Config, soup, idname):
    """週間天気"""
    pinpoint = soup.find("div", id=idname)
    title = pinpoint.find("h2") if pinpoint else None
    title_text = ""
    if title:
        title_text = title.get_text()
        title_text = " ".join(title_text.split())

    title_text = f"{config.name} {title_text}"

    yahoo_table = pinpoint.find("table") if pinpoint else None
    if yahoo_table is None:
        return

    table = Table(
        title=title_text,
        show_header=True,
        box=box.ROUNDED,
    )

    rows = []

    for tr in yahoo_table.find_all("tr"):
        first_td = tr.find("td")

        if "天気" in first_td.get_text():
            row = tenki(tr)
        elif "気温" in first_td.get_text():
            row = kion_week(tr)
        elif "降水確率" in first_td.get_text():
            row = kousuikakuritsu(tr)
        else:
            row = sonota(tr)

        rows.append(row)

    # 列数を決定
    for i in range(len(rows[0])):
        table.add_column(
            header=rows[0][i],
            justify="center",
        )

    for row in rows[1:]:
        table.add_row(*row)

    Console().print(table)


def read_conf():
    """configファイル読み込み"""
    with open(CONFIG_FILE, mode="rb") as f:
        toml: dict[str, Any] = tomllib.load(f)

    return Config(url=toml["yahoo"]["url"], name=toml["yahoo"]["name"])


def make_conf():
    selector.proc()


def main():
    """main"""
    # 基本的なStreamHandler(sys.stdout)の設定例
    handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(handler)

    if not os.path.isfile(CONFIG_FILE):
        make_conf()

    config = read_conf()
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-r",
        action="store_true",
        help="キャッシュを無視して新規に取りに行きます(Refresh)",
    )
    parser.add_argument("-a", action="store_true", help="今日／明日／週間全部表示(All)")
    parser.add_argument("-d", action="store_true", help="Debug")

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.d else logging.INFO)
    logging.debug("{args.r=%s", args.r)
    htmltext = get_html(config, force=args.r)
    soup = BeautifulSoup(htmltext, "html.parser")
    disp_day_table(config, soup, "yjw_pinpoint_today")
    if args.a:
        disp_day_table(config, soup, "yjw_pinpoint_tomorrow")
    if args.a:
        disp_week_table(config, soup, "yjw_week")


if __name__ == "__main__":
    main()

# end of file
