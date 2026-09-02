import sqlite3

import requests
from bs4 import BeautifulSoup


conn = sqlite3.connect("weather.db")

conn.execute("""
CREATE TABLE IF NOT EXISTS weather_location (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER,
    level INTEGER NOT NULL,
    name TEXT NOT NULL,
    href TEXT NOT NULL,
    UNIQUE (parent_id, level, name),
    FOREIGN KEY (parent_id)
        REFERENCES weather_location(id)
)
""")

conn.commit()


def save_location(name, href, parent_id=None, level=1):
    conn.execute(
        """
        INSERT INTO weather_location
            (parent_id, level, name, href)
        VALUES
            (?, ?, ?, ?)
        ON CONFLICT(parent_id, level, name) DO UPDATE SET
            href = excluded.href
        """,
        (parent_id, level, name, href),
    )

    row = conn.execute(
        """
        SELECT id
        FROM weather_location
        WHERE parent_id IS ?
          AND level = ?
          AND name = ?
        """,
        (parent_id, level, name),
    ).fetchone()

    conn.commit()

    return row[0]


def proc_level4(href, parent_id):
    # e.g. https://weather.yahoo.co.jp/weather/jp/1a/1100.html
    # base = "https://weather.yahoo.co.jp"
    # url = f"{base}{href}"
    url = href

    print(f"{url=}, level=4")

    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    ul = soup.select_one("ul.yjw_clr")
    if ul is None:
        return

    for li in ul.find_all("li"):
        a = li.find("a")
        if a is None:
            continue

        # e.g. https://weather.yahoo.co.jp/weather/jp/1a/1100/1214.html
        href = a.get("href")
        if href is None:
            continue

        text = a.get_text(strip=True)

        print(f"{text=}, {href=}, level=4")

        save_location(
            text,
            href,
            parent_id=parent_id,
            level=4,
        )


def proc_level3_naha(href, parent_id):
    # e.g. https://weather.yahoo.co.jp/weather/jp/1a/1100.html
    # base = "https://weather.yahoo.co.jp"
    # url = f"{base}{href}"
    url = href

    print(f"{url=}, level=3(naha)")

    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    ul = soup.select_one("ul.yjw_clr")
    if ul is None:
        return

    for li in ul.find_all("li"):
        a = li.find("a")
        if a is None:
            continue

        # e.g. https://weather.yahoo.co.jp/weather/jp/1a/1100/1214.html
        href = a.get("href")
        if href is None:
            continue

        text = a.get_text(strip=True)

        print(f"{text=}, {href=}, level=3(naha)")

        save_location(
            text,
            href,
            parent_id=parent_id,
            level=3,
        )


def proc_level3(href, parent_id):
    # e.g. https://weather.yahoo.co.jp/weather/jp/1a/?day=1
    base = "https://weather.yahoo.co.jp"
    if "http" in href:
        url = href
        proc_level3_naha(href, parent_id)
        return

    url = f"{base}{href}"

    print(f"{url=},level=3")

    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    items = soup.find_all("li", class_="point")

    for item in items:
        a = item.find("a")
        if a is None:
            continue

        # e.g. href = https://weather.yahoo.co.jp/weather/jp/1a/1100.html
        href = a.get("href")
        if href is None:
            continue

        dt = item.find("dt", class_="name")
        name = ""
        if dt:
            name = dt.get_text(strip=True)

        location_id = save_location(
            name,
            href,
            parent_id=parent_id,
            level=3,
        )

        proc_level4(href, location_id)


def proc_level2(href, parent_id):
    # e.g. "https://weather.yahoo.co.jp/weather/jp/1.html?day=1
    base = "https://weather.yahoo.co.jp"
    url = f"{base}{href}"

    print(f"{url=}")

    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    items = soup.find_all("li", class_="point")

    for item in items:
        a = item.find("a")
        if a is None:
            continue

        # e.g. https://weather.yahoo.co.jp/weather/jp/1a/?day=1
        href = a.get("href")
        if href is None:
            continue

        dt = item.find("dt", class_="name")
        name = ""
        if dt:
            name = dt.get_text(strip=True)

        location_id = save_location(
            name,
            href,
            parent_id=parent_id,
            level=2,
        )

        proc_level3(href, location_id)


def proc_leve1():
    top = "https://weather.yahoo.co.jp/weather/"

    response = requests.get(top)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    map = soup.find("div", id="map")
    if map is None:
        raise RuntimeError("mapが見つかりません")

    for li in map.find_all("li", class_="point"):
        a = li.find("a")
        if a is None:
            continue
        href = a.get("href")
        if href is None:
            continue

        # e.g. /weather/jp/1.html?day=1
        print(f"{href=}, level=1")

        dt = li.find("dt", class_="name")
        name = ""
        if dt:
            name = dt.get_text(strip=True)

        print(f"{name=}, level=1")
        location_id = save_location(
            name,
            href,
            level=1,
        )

        proc_level2(href, location_id)


def proc():
    proc_leve1()


def main():
    try:
        proc()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
