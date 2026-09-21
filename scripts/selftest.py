#!/usr/bin/env python3
"""Self-test for the digest collector.

    python3 scripts/selftest.py            # offline: builds fixtures, runs the unit + end-to-end suite
    python3 scripts/selftest.py --live     # + network smoke test: can this environment reach every source,
                                           #   and does each parser still recognise the live page structure?

Run --live once in every new environment (personal Cowork, the service account,
a scheduled task) before trusting a digest from it. It prints one line per
source: OK / BLOCKED (with the reason the HTTP layer classified) / PARSE-EMPTY
(the site answered but the parser found nothing → the page structure changed,
see references/sources.md).
"""
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def offline() -> int:
    print("== offline suite (fixtures) ==")
    r = subprocess.run([sys.executable, str(ROOT / "tests" / "test_digest.py")], cwd=str(ROOT))
    return r.returncode


def live() -> int:
    from cylaw_digest import window as W
    from cylaw_digest.http import Http
    from cylaw_digest import gazette, cylaw, nomoplatform, govcy, registrar, cbc
    from cylaw_digest.pdftext import pdf_to_text
    from cylaw_digest import acts

    win = W.last_days(21)
    http = Http(raw_dir=None, delay=0.5)
    failures = 0

    def report(name: str, res, parsed: int | None, note: str = ""):
        nonlocal failures
        if not res.ok:
            print(f"BLOCKED      {name:34s} {res.reason:14s} {res.url[:90]}")
            failures += 1
        elif parsed is not None and parsed == 0:
            print(f"PARSE-EMPTY  {name:34s} status={res.status} {note}")
            failures += 1
        else:
            print(f"OK           {name:34s} parsed={parsed} {note}")

    print(f"== live smoke test ({dt.date.today()}, probe window {win.start}..{win.end}) ==")
    # Gazette listing + one issue + its PDF header
    res = http.get(gazette.VIEW.format(app=6))
    issues = gazette.parse_listing(res.text, 6) if res.ok else []
    report("gazette listing Παρ. ΙΙΙ(Ι)", res, len(issues), f"latest={issues[0].date if issues else None}")
    if issues:
        r2 = http.get(issues[0].url)
        pdf, meta = gazette.parse_issue_page(r2.text, issues[0].url) if r2.ok else ("", {})
        report("gazette issue page", r2, 1 if pdf else 0, pdf[-60:])
        if pdf:
            r3 = http.get_pdf(pdf)
            secs = acts.split_kdp_sections(pdf_to_text(r3.content, max_pages=6)) if r3.ok else []
            report("gazette PDF → Κ.Δ.Π. sections", r3, len(secs), f"first={secs[0][0] if secs else None}")
    # CyLaw index + newest law PDF
    res = http.get(cylaw.ARITH_INDEX.format(year=dt.date.today().year))
    entries = cylaw.parse_arith_index(res.text) if res.ok else []
    report("cylaw numbered index", res, len(entries), f"encoding={res.encoding}")
    if entries:
        newest = max((e for e in entries if e.part == "I"), key=lambda e: e.seq)
        r2 = http.get_pdf(newest.pdf_url)
        p = acts.parse_law_text(pdf_to_text(r2.content, max_pages=3), newest.number) if r2.ok else None
        report("cylaw per-law PDF header", r2, 1 if (p and p.gazette_date) else 0,
               f"{newest.number} → {p.gazette_date if p else None}")
    # CyLaw Κ.Δ.Π. index + newest per-act PDF
    res = http.get(cylaw.KDP_INDEX.format(year=dt.date.today().year))
    kdps = cylaw.parse_kdp_index(res.text) if res.ok else []
    report("cylaw Κ.Δ.Π. index", res, len(kdps), f"latest={kdps[-1].number if kdps else None} ({kdps[-1].date if kdps else None})")
    if kdps:
        r2 = http.get_pdf(kdps[-1].pdf_url)
        p = acts.parse_kdp_section(kdps[-1].number, pdf_to_text(r2.content, max_pages=3)) if r2.ok else None
        report("cylaw Κ.Δ.Π. per-act PDF", r2, 1 if (p and (p.title or p.instrument)) else 0, kdps[-1].pdf_url[-28:])
    # Nomoplatform API (Cloudflare check) + a bill page
    res = http.get(nomoplatform.API + "bill-status", params={"per_page": 5, "_fields": "id,name"})
    try:
        n = len(res.json()) if res.ok else 0
    except Exception:
        n = 0
    report("nomoplatform REST API", res, n)
    res = http.get(nomoplatform.API + "bills", params={"per_page": 1, "_fields": "id,link,title"})
    try:
        link = res.json()[0]["link"] if res.ok else ""
    except Exception:
        link = ""
    if link:
        r2 = http.get(link)
        tl = nomoplatform.extract_timeline(nomoplatform.html_to_text(r2.text)) if r2.ok else []
        report("nomoplatform bill page timeline", r2, len(tl), link[-60:])
    # gov.cy
    res = http.get(govcy.API, params={"per_page": 5, "categories": "182", "_fields": "id,date,title"})
    try:
        n = len(res.json()) if res.ok else 0
    except Exception:
        n = 0
    report("gov.cy announcements API", res, n)
    # Registrar, CBC
    res = http.get(registrar.NEWS)
    rows = registrar.parse_news(res.text) if res.ok else []
    report("registrar news", res, len(rows), f"latest={rows[0]['date'] if rows else None}")
    res = http.get(cbc.ANNOUNCEMENTS)
    arts = cbc.parse_announcements(res.text) if res.ok else []
    report("CBC announcements", res, len(arts), f"latest={arts[0]['date'] if arts else None}")
    print(f"== {failures} problem(s) ==")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--live-only", action="store_true")
    a = ap.parse_args()
    rc = 0
    if not a.live_only:
        rc |= offline()
    if a.live or a.live_only:
        rc |= live()
    return rc


if __name__ == "__main__":
    sys.exit(main())
