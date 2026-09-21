"""Τμήμα Εφόρου Εταιρειών και Διανοητικής Ιδιοκτησίας – Κλάδος Εταιρειών
(companies.gov.cy). Its news page is a plain list:

    <article class="item-box">
      <time datetime="2026-09-04">04 ΣΕΠ 2026</time>
      <h2><a href="/gr/βάση-πληροφοριών/νέα/…">Title</a></h2>
      <summary>…</summary>
    </article>

The Registrar does not post to gov.cy, so this site is the only feed for
company-law practice notices (annual returns, UBO register, fees, e-filing).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .greekdates import parse_date
from .http import Http
from .model import Item
from .window import Window

log = logging.getLogger("cylaw_digest.registrar")

BASE = "https://www.companies.gov.cy"
NEWS = BASE + "/gr/βάση-πληροφοριών/νέα"


def parse_news(html: str, base: str = BASE) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out = []
    for art in soup.select("article.item-box, article"):
        t = art.find("time")
        h = art.find(["h2", "h3"])
        a = h.find("a", href=True) if h else None
        if not (t and a):
            continue
        date = None
        if t.get("datetime"):
            try:
                date = dt.date.fromisoformat(t["datetime"][:10])
            except ValueError:
                date = parse_date(t.get_text(" ", strip=True))
        else:
            date = parse_date(t.get_text(" ", strip=True))
        summary = art.find("summary")
        out.append({
            "date": date, "title": a.get_text(" ", strip=True), "url": urljoin(base, a["href"]),
            "summary": re.sub(r"\s+", " ", summary.get_text(" ", strip=True)) if summary else "",
        })
    return out


class RegistrarCollector:
    def __init__(self, http: Http, window: Window):
        self.http = http
        self.window = window
        self.status: dict[str, object] = {}

    def collect(self) -> list[Item]:
        res = self.http.get(NEWS)
        if not res.ok:
            self.status = {"ok": False, "reason": res.reason, "url": NEWS}
            return []
        rows = parse_news(res.text)
        self.status = {"ok": True, "listed": len(rows)}
        items = []
        for r in rows:
            if not self.window.contains(r["date"]):
                continue
            body = ""
            page = self.http.get(r["url"])
            if page.ok:
                soup = BeautifulSoup(page.text, "lxml")
                main = soup.find("article") or soup.find("main") or soup.body
                body = re.sub(r"\n\s*\n+", "\n", main.get_text("\n")).strip() if main else ""
            items.append(Item(
                id=f"registrar-{hashlib.sha1(r['url'].encode('utf-8')).hexdigest()[:10]}", contour="regulator", kind="announcement",
                source="registrar", source_label="Τμήμα Εφόρου Εταιρειών και Διανοητικής Ιδιοκτησίας",
                date=r["date"], date_kind="announced", title_el=r["title"], url=r["url"],
                verbatim={"summary": r["summary"], "body": body[:8000]},
                practice_areas=["corporate"], relevance=2, relevance_hits=["registrar:source"],
            ))
        return items
