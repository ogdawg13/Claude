import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from unittest import mock
from bilbevakning.parser import parse_html, parse_text, clean_url
from bilbevakning.db import DB
from bilbevakning import main

HTML = """<html><body>
<a href="https://www.blocket.se/annons/abc123?utm_source=mail"><img src=x></a>
<a href="https://www.blocket.se/annons/abc123?utm_source=mail">Tesla Model 3 Long Range</a>
<p>189 900 kr</p><p>2021 · 4 500 mil</p>
<a href="https://www.bytbil.com/bil/xyz">Kia Niro EV</a><p>2020 | 62 000 km | 205 000 kr</p>
<a href="https://www.blocket.se/avsluta">Avsluta bevakning</a>
</body></html>"""

class T(unittest.TestCase):
    def test_parse_html(self):
        ls = parse_html(HTML)
        self.assertEqual(len(ls), 2)
        a, b = ls
        self.assertEqual((a.site, a.price, a.year, a.mileage_mil), ("Blocket", 189900, 2021, 4500))
        self.assertEqual(a.url, "https://www.blocket.se/annons/abc123")
        self.assertEqual((b.site, b.price, b.year, b.mileage_mil), ("Bytbil", 205000, 2020, 6200))

    def test_parse_text(self):
        ls = parse_text("Kia EV6\nhttps://www.carla.se/bil/1?x=1\n250 000 kr 2022 3 000 mil\n")
        self.assertEqual(len(ls), 1)
        self.assertEqual((ls[0].price, ls[0].year), (250000, 2022))

    def test_deal_detection(self):
        db = DB(":memory:")
        cfg = {"filter": {"keywords": ["Tesla"], "max_price": 400000},
               "deal": {"threshold": 0.12, "min_samples": 5},
               "notify": {"ntfy_topic": "t"}, "mail": {}}
        def mk(i, price):
            return parse_html(f'<a href="https://www.blocket.se/a/{i}">Tesla Model 3</a><p>{price} kr 2021 3 000 mil</p>')[0]
        sent = []
        with mock.patch.object(main.notify, "ntfy", lambda *a: sent.append(a)):
            for i in range(5):
                main.handle(cfg, db, mk(i, 300000), {"mail_password": ""})
            main.handle(cfg, db, mk(99, 240000), {"mail_password": ""})
        self.assertTrue(sent[-1][2].startswith("BRA PRIS"))
        self.assertFalse(any(s[2].startswith("BRA PRIS") for s in sent[:-1]))

if __name__ == "__main__":
    unittest.main()
