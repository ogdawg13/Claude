"""Sparar sedda annonser och prishistorik i en SQLite-fil."""
import sqlite3
import statistics
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    url TEXT PRIMARY KEY,
    site TEXT, title TEXT, price INTEGER, year INTEGER, mileage_mil INTEGER,
    first_seen REAL, last_price INTEGER, model TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS price_history (
    url TEXT, price INTEGER, seen REAL
);
"""


class DB:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)

    def add(self, l, model: str = "") -> str:
        """Returnerar 'new', 'price_drop' eller 'seen'."""
        now = time.time()
        row = self.conn.execute("SELECT last_price FROM listings WHERE url=?", (l.url,)).fetchone()
        if row is None:
            self.conn.execute(
                "INSERT INTO listings VALUES (?,?,?,?,?,?,?,?,?)",
                (l.url, l.site, l.title, l.price, l.year, l.mileage_mil, now, l.price, model),
            )
            self.conn.execute("INSERT INTO price_history VALUES (?,?,?)", (l.url, l.price, now))
            self.conn.commit()
            return "new"
        old = row[0]
        if l.price and old and l.price < old:
            self.conn.execute("UPDATE listings SET last_price=? WHERE url=?", (l.price, l.url))
            self.conn.execute("INSERT INTO price_history VALUES (?,?,?)", (l.url, l.price, now))
            self.conn.commit()
            return "price_drop"
        return "seen"

    def comparable_prices(self, year: int | None, exclude_url: str, model: str = "", year_span: int = 1) -> list[int]:
        """Priser på tidigare annonser från liknande årsmodeller."""
        q = "SELECT price FROM listings WHERE price IS NOT NULL AND url != ? AND model = ?"
        args: list = [exclude_url, model]
        if year:
            q += " AND year BETWEEN ? AND ?"
            args += [year - year_span, year + year_span]
        return [r[0] for r in self.conn.execute(q, args)]

    def median_price(self, year, exclude_url, min_samples, model: str = "") -> int | None:
        prices = self.comparable_prices(year, exclude_url, model)
        return int(statistics.median(prices)) if len(prices) >= min_samples else None
