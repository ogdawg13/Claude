"""Plockar ut annonser (länk, pris, år, miltal) ur aviseringsmejl från annonssajterna."""
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit

SITES = {"blocket.se": "Blocket", "carla.se": "Carla", "bytbil.com": "Bytbil"}

PRICE_RE = re.compile(r"(\d{1,3}(?:[  .]\d{3})+|\d{4,7})\s*(?:kr|:-|SEK)", re.I)
YEAR_RE = re.compile(r"\b(19[89]\d|20[0-4]\d)\b")
MIL_RE = re.compile(r"(\d{1,3}(?:[  .]\d{3})+|\d{1,6})\s*mil\b", re.I)
KM_RE = re.compile(r"(\d{1,3}(?:[  .]\d{3})+|\d{1,7})\s*km\b", re.I)


@dataclass
class Listing:
    site: str
    url: str
    title: str
    price: int | None
    year: int | None
    mileage_mil: int | None  # svenska mil (1 mil = 10 km)
    text: str


def _num(s: str) -> int:
    return int(re.sub(r"\D", "", s))


def site_for(url: str) -> str | None:
    host = urlsplit(url).netloc.lower()
    for domain, name in SITES.items():
        if host == domain or host.endswith("." + domain):
            return name
    return None


def clean_url(url: str) -> str:
    """Tar bort spårningsparametrar så samma annons alltid får samma adress."""
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip("/"), "", ""))


class _Chunker(HTMLParser):
    """Delar mejlet i bitar: varje bit börjar vid en länk till en annonssajt."""

    def __init__(self):
        super().__init__()
        self.chunks: list[tuple[str, list[str]]] = []  # (url, textbitar)
        self.current: tuple[str, list[str]] | None = None
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag == "a":
            href = dict(attrs).get("href") or ""
            if site_for(href):
                url = clean_url(href)
                if self.current and self.current[0] == url:
                    return  # samma annons, flera länkar (bild + rubrik)
                self.current = (url, [])
                self.chunks.append(self.current)

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if self.current and not self.skip and data.strip():
            self.current[1].append(data.strip())


def parse_html(html: str) -> list[Listing]:
    chunker = _Chunker()
    chunker.feed(html)
    listings = []
    for url, parts in chunker.chunks:
        listing = _build(url, parts)
        if listing:
            listings.append(listing)
    return listings


def parse_text(text: str) -> list[Listing]:
    """Reservväg för mejl utan HTML: delar på rader med annonslänkar."""
    chunks, current = [], None
    for line in text.splitlines():
        for m in re.finditer(r"https?://\S+", line):
            if site_for(m.group(0)):
                current = (clean_url(m.group(0).rstrip(">).,")), [])
                chunks.append(current)
        if current and line.strip():
            current[1].append(line.strip())
    return [l for l in (_build(u, p) for u, p in chunks) if l]


def _build(url: str, parts: list[str]) -> Listing | None:
    text = re.sub(r"https?://\S+", " ", " | ".join(parts))
    price = None
    if m := PRICE_RE.search(text):
        price = _num(m.group(1))
    year = int(m.group(1)) if (m := YEAR_RE.search(text)) else None
    mil = None
    if m := MIL_RE.search(text):
        mil = _num(m.group(1))
    elif m := KM_RE.search(text):
        mil = _num(m.group(1)) // 10
    title = parts[0] if parts else url
    # En länk utan vare sig pris eller år är troligen inte en annons (t.ex. "avsluta bevakning").
    if price is None and year is None:
        return None
    return Listing(site_for(url) or "?", url, title[:120], price, year, mil, text[:500])
