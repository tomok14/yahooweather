"""
yahoo天気を表示する

[configファイル]
~/.config/yahooweather/yahooweather.conf

"""

import argparse
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import tomllib
from bs4 import BeautifulSoup
from requests_cache import CachedSession
from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from . import selector

CONFIG_DIR = Path.home() / ".config" / "yahooweather"
CONFIG_FILE = CONFIG_DIR / "yahooweather.conf"
CACHE_DIR = Path.home() / ".cache" / "yahooweather"
CACHE_FILE = CACHE_DIR / "cache"

logger = logging.getLogger(__name__)


@dataclass(frozen=False)
class ConfigSite:
    """ConfigSite"""

    url: str = ""
    name: str = ""


@dataclass(frozen=False)
class Config:
    """Config"""

    sets: list[ConfigSite] = field(default_factory=lambda: [ConfigSite()])


def get_html(site: ConfigSite, force=False):
    """HTML取得"""
    # スクレイピング対象の URL にリクエストを送り HTML を取得する
    url = site.url
    # res = requests.get(url)
    # キャッシュセッションの作成（SQLiteを使用）

    session = CachedSession(CACHE_FILE, expire_after=60 * 60 * 3)  # 3時間キャッシュ

    logger.debug("session.request('GET') url=%s, force=%s", url, force)
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


def is_past_hour(hour: int) -> bool:
    """指定した時刻が現在時刻より過去か"""
    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    current_forecast_hour = (now.hour // 3) * 3
    return hour < current_forecast_hour


def remove_emoji(text: str) -> str:
    """絵文字除去"""
    return re.sub(
        r"[\U0001F300-\U0001FAFF\u2600-\u27BF]",
        "",
        text,
    )


def check_gray_column(rows, idname):
    """グレイ列チェック"""
    past_columns = []
    for header in rows[0]:
        match = re.search(r"(\d+)時", header)

        if idname == "yjw_pinpoint_today":
            if match:
                hour = int(match.group(1))
                past_columns.append(is_past_hour(hour))
            else:
                past_columns.append(False)
        else:
            past_columns.append(False)

    return past_columns


def set_header(table, rows, past_columns):
    """ヘッダセット"""
    for i, header in enumerate(rows[0]):
        style = None

        if past_columns[i]:
            style = "rgb(100,100,100)"

        kwargs = {
            "header": header,
            "justify": "center",
        }

        if style:
            kwargs["style"] = style
            kwargs["header_style"] = style

        table.add_column(**kwargs)


def set_data(table, rows, past_columns):
    """データセット"""
    for row in rows[1:]:
        new_row = []

        for i, text in enumerate(row):
            if past_columns[i]:
                # text = markup(text).plain
                text_obj = Text.from_markup(text)
                text = text_obj.plain
                text = remove_emoji(text)

            new_row.append(text)

        table.add_row(*new_row)


def disp_day_table(site: ConfigSite, soup, idname):
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

    title_text = f"{site.name} - {title_text}"
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

    # グレイ列の事前調査
    past_columns = check_gray_column(rows, idname)

    # ヘッダ
    set_header(table, rows, past_columns)

    # データ部分
    set_data(table, rows, past_columns)

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


def disp_week_table(site: ConfigSite, soup, idname):
    """週間天気"""
    pinpoint = soup.find("div", id=idname)
    title = pinpoint.find("h2") if pinpoint else None
    title_text = ""
    if title:
        title_text = title.get_text()
        title_text = " ".join(title_text.split())

    title_text = f"{site.name} {title_text}"

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

    yahoo = toml.get("yahoo")
    if yahoo is None:
        return Config()
    if isinstance(yahoo, dict):
        # 旧形式 [yahoo] (単一サイト) との互換性
        yahoo_list = [yahoo]
    elif isinstance(yahoo, list):
        # 新形式 [[yahoo]] (複数サイト)
        yahoo_list = yahoo
    else:
        raise TypeError(f"不正な設定形式です: {CONFIG_FILE}")

    sets = [
        ConfigSite(
            url=item.get("url", ""),
            name=item.get("name", ""),
        )
        for item in yahoo_list
    ]
    if not sets:
        return Config()
    return Config(sets=sets)


def list_sites(config: Config):
    """設定されているサイト一覧表示"""
    for i, site in enumerate(config.sets, start=1):
        print(f"{i}: {site.name} ({site.url})")


def make_conf():
    """confファイル生成"""
    selector.proc()


def is_gogo():
    """午後かどうかを判定する"""
    return datetime.now(ZoneInfo("Asia/Tokyo")).hour >= 12


def main():
    """main"""
    # 基本的なStreamHandler(sys.stdout)の設定例
    handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(handler)

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-r",
        action="store_true",
        help="キャッシュを無視して新規に取りに行きます(Refresh)",
    )
    parser.add_argument("-a", action="store_true", help="今日／明日／週間全部表示(All)")
    parser.add_argument("-d", action="store_true", help="Debug")
    parser.add_argument("-c", action="store_true", help="Config")
    parser.add_argument(
        "-n",
        "--number",
        type=int,
        default=1,
        metavar="N",
        help="何番目のサイトを表示するか指定します(番号は -l で確認, default: 1)",
    )
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="設定されているサイトの一覧を表示します(List)",
    )

    args = parser.parse_args()

    if args.c:
        make_conf()
        return

    if not os.path.isfile(CONFIG_FILE):
        make_conf()

    config = read_conf()

    logging.basicConfig(level=logging.DEBUG if args.d else logging.INFO)
    logger.debug("args.r=%s", args.r)
    logger.debug("args.n=%s", args.number)

    if args.list:
        list_sites(config)
        return

    if not 1 <= args.number <= len(config.sets):
        parser.error(
            f"サイト番号は 1〜{len(config.sets)} の範囲で指定してください "
            f"(一覧は -l で確認できます): {args.number}"
        )

    site = config.sets[args.number - 1]
    htmltext = get_html(site, force=args.r)
    soup = BeautifulSoup(htmltext, "html.parser")
    disp_day_table(site, soup, "yjw_pinpoint_today")
    if args.a or is_gogo():
        disp_day_table(site, soup, "yjw_pinpoint_tomorrow")
    if args.a:
        disp_week_table(site, soup, "yjw_week")


if __name__ == "__main__":
    main()

# end of file
