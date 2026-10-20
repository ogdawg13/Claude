"""Läser aviseringsmejl, bedömer annonserna och skickar egna aviseringar."""
import email
import imaplib
import logging
import os
import sys
import time
import tomllib
from email.message import Message

from . import notify
from .db import DB
from .parser import SITES, Listing, parse_html, parse_text

log = logging.getLogger("bilbevakning")


def load_config(path: str) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def body_parts(msg: Message) -> tuple[str, str]:
    html = text = ""
    for part in msg.walk():
        ctype = part.get_content_type()
        if ctype in ("text/html", "text/plain"):
            payload = part.get_payload(decode=True) or b""
            decoded = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
            if ctype == "text/html":
                html += decoded
            else:
                text += decoded
    return html, text


def fetch_listings(cfg: dict, password: str) -> list[Listing]:
    """Hämtar olästa aviseringsmejl från sajterna och markerar dem som lästa."""
    out: list[Listing] = []
    box = imaplib.IMAP4_SSL(cfg["mail"]["imap_host"])
    box.login(cfg["mail"]["user"], password)
    box.select(cfg["mail"].get("folder", "INBOX"))
    for domain in SITES:
        _, data = box.search(None, "UNSEEN", "FROM", f'"{domain}"')
        for num in data[0].split():
            _, raw = box.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(raw[0][1])
            html, text = body_parts(msg)
            found = parse_html(html) if html else parse_text(text)
            log.info("Mejl från %s: %d annonser", domain, len(found))
            out.extend(found)
            box.store(num, "+FLAGS", "\\Seen")
    box.logout()
    return out


def matches(l: Listing, f: dict) -> bool:
    if l.price and f.get("max_price") and l.price > f["max_price"]:
        return False
    if l.year and f.get("min_year") and l.year < f["min_year"]:
        return False
    if l.mileage_mil and f.get("max_mil") and l.mileage_mil > f["max_mil"]:
        return False
    words = [w.lower() for w in f.get("keywords", [])]
    if words and not any(w in l.text.lower() or w in l.title.lower() for w in words):
        return False
    return True


def model_of(l: Listing, f: dict) -> str:
    """Första sökordet som träffar används som modellgrupp för prisjämförelse."""
    haystack = (l.title + " " + l.text).lower()
    return next((w for w in f.get("keywords", []) if w.lower() in haystack), "")


def describe(l: Listing, median: int | None) -> tuple[str, str, bool]:
    """Returnerar (titel, text, brådskande)."""
    price = f"{l.price:,} kr".replace(",", " ") if l.price else "pris saknas"
    bits = [price, str(l.year or "?"), f"{l.mileage_mil} mil" if l.mileage_mil else "? mil"]
    urgent, extra = False, ""
    if median and l.price:
        diff = (median - l.price) / median
        extra = f"\nJämförpris ca {median:,} kr ({diff:+.0%} mot marknaden)".replace(",", " ")
    return f"{l.site}: {l.title}", " · ".join(bits) + extra, urgent


def handle(cfg: dict, db: DB, l: Listing, secrets: dict):
    model = model_of(l, cfg["filter"])
    status = db.add(l, model)
    if status == "seen" or not matches(l, cfg["filter"]):
        return
    median = db.median_price(l.year, l.url, cfg["deal"]["min_samples"], model)
    title, text, _ = describe(l, median)
    deal = bool(median and l.price and l.price <= median * (1 - cfg["deal"]["threshold"]))
    if status == "price_drop":
        title = "PRISSÄNKT - " + title
    if deal:
        title = "BRA PRIS - " + title
    log.info("Avisering: %s", title)
    n = cfg["notify"]
    if n.get("ntfy_topic"):
        notify.ntfy(n.get("ntfy_server", "https://ntfy.sh"), n["ntfy_topic"], title, text, l.url, deal)
    if n.get("email_to") and secrets["mail_password"]:
        notify.mail({**cfg["mail"], "to": n["email_to"]}, secrets["mail_password"], title, text, l.url)


def run_once(cfg: dict, db: DB, secrets: dict):
    for l in fetch_listings(cfg, secrets["mail_password"]):
        handle(cfg, db, l, secrets)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    path = sys.argv[1] if len(sys.argv) > 1 else "config.toml"
    cfg = load_config(path)
    secrets = {"mail_password": os.environ.get("BILBEVAKNING_MAIL_PASSWORD", "")}
    if not secrets["mail_password"]:
        sys.exit("Sätt miljövariabeln BILBEVAKNING_MAIL_PASSWORD (applösenord för mejlkontot).")
    db = DB(cfg.get("database", "bilar.db"))
    interval = cfg.get("poll_seconds", 60)
    while True:
        try:
            run_once(cfg, db, secrets)
        except Exception:
            log.exception("Något gick fel, försöker igen om en stund")
        if "--once" in sys.argv:
            break
        time.sleep(interval)


if __name__ == "__main__":
    main()
