"""Skickar aviseringar: mobilnotis via ntfy och mejl via SMTP."""
import json
import smtplib
import urllib.request
from email.message import EmailMessage


def ntfy(server: str, topic: str, title: str, message: str, url: str, urgent: bool):
    body = {"topic": topic, "title": title, "message": message, "click": url,
            "priority": 5 if urgent else 3, "tags": ["rotating_light" if urgent else "car"]}
    req = urllib.request.Request(server, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=15).read()


def mail(cfg: dict, password: str, title: str, message: str, url: str):
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = title, cfg["user"], cfg["to"]
    msg.set_content(f"{message}\n\n{url}")
    with smtplib.SMTP_SSL(cfg["smtp_host"], 465, timeout=20) as s:
        s.login(cfg["user"], password)
        s.send_message(msg)
