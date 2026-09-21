"""Central Bank of Cyprus – /en/announcements is one long page (every
announcement since 2023) of

    <article><span class="date">14 September 2026</span><h5>Title</h5><a href="/en/announcements/slug"/></article>

Most entries are statistics; the relevance filter keeps directives,
circulars, licensing / AML / payment-services notices, which is what matters
for banking referrals and PSP/EMI work.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .greekdates import parse_date
from .http import Http
from .model import Item
from .window import Window

log = logging.getLogger("cylaw_digest.cbc")

BASE = "https://www.centralbank.cy"
ANNOUNCEMENTS = BASE + "/en/announcements"


def parse_announcements(html: str, base: str = BASE) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out = []
    for art in soup.find_all("article"):
        d = art.find(class_="date")
        h = art.find(["h5", "h4", "h3", "h2"])
        a = art.find("a", href=True)
        if not (d and h and a):
            continue
        out.append({"date": parse_date(d.get_text(" ", strip=True)),
                    "title": re.sub(r"\s+", " ", h.get_text(" ", strip=True)),
                    "url": urljoin(base, a["href"])})
    return out


class CbcCollector:
    def __init__(self, http: Http, window: Window, fetch_bodies: bool = True):
        self.http = http
        self.window = window
        self.fetch_bodies = fetch_bodies
        self.status: dict[str, object] = {}

    def collect(self) -> list[Item]:
        res = self.http.get(ANNOUNCEMENTS)
        if not res.ok:
            self.status = {"ok": False, "reason": res.reason, "url": ANNOUNCEMENTS}
            return []
        rows = parse_announcements(res.text)
        self.status = {"ok": True, "listed": len(rows)}
        items = []
        for r in rows:
            if not self.window.contains(r["date"]):
                continue
            body = ""
            if self.fetch_bodies:
                page = self.http.get(r["url"])
                if page.ok:
                    soup = BeautifulSoup(page.text, "lxml")
                    main = soup.find("main") or soup.find(class_=re.compile("content")) or soup.body
                    body = re.sub(r"\n\s*\n+", "\n", main.get_text("\n")).strip() if main else ""
            items.append(Item(
                id=f"cbc-{r['url'].rsplit('/', 1)[-1]}", contour="regulator", kind="announcement", source="cbc",
                source_label="Central Bank of Cyprus", date=r["date"], date_kind="announced",
                title_en=r["title"], title_el="", url=r["url"], verbatim={"body": body[:6000]},
            ))
        return items
