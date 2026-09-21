"""Unit + end-to-end tests for the digest collector. Plain unittest, no network.

    python3 tests/test_digest.py            # builds fixtures, runs everything
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(HERE))

from cylaw_digest import acts, window as W  # noqa: E402
from cylaw_digest.greekdates import parse_date, find_all_dates  # noqa: E402
from cylaw_digest.http import Http  # noqa: E402
from cylaw_digest.relevance import classify  # noqa: E402
from cylaw_digest import cylaw, gazette, nomoplatform, registrar, cbc  # noqa: E402

FX = HERE / "fixtures"


class WindowTests(unittest.TestCase):
    def test_previous_week_from_monday(self):
        w = W.previous_week(dt.date(2026, 9, 14))
        self.assertEqual((w.start, w.end), (dt.date(2026, 9, 7), dt.date(2026, 9, 13)))

    def test_previous_week_from_midweek_and_year_boundary(self):
        w = W.previous_week(dt.date(2026, 9, 17))
        self.assertEqual((w.start, w.end), (dt.date(2026, 9, 7), dt.date(2026, 9, 13)))
        w = W.previous_week(dt.date(2027, 1, 5))
        self.assertEqual((w.start, w.end), (dt.date(2026, 12, 28), dt.date(2027, 1, 3)))

    def test_days_and_explicit(self):
        w = W.last_days(8, dt.date(2026, 9, 14))
        self.assertEqual(w.start, dt.date(2026, 9, 7))
        self.assertTrue(W.explicit("2026-09-01", "2026-09-30").contains(dt.date(2026, 9, 15)))
        with self.assertRaises(ValueError):
            W.explicit("2026-09-30", "2026-09-01")


class GreekDateTests(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(parse_date("Αριθμός 5094 Παρασκευή, 24 Ιουλίου 2026"), dt.date(2026, 7, 24))
        self.assertEqual(parse_date("Αρ. 6045, 11.9.2026"), dt.date(2026, 9, 11))
        self.assertEqual(parse_date("11/09/2026"), dt.date(2026, 9, 11))
        self.assertEqual(parse_date("04 ΣΕΠ 2026"), dt.date(2026, 9, 4))
        self.assertEqual(parse_date("14 September 2026"), dt.date(2026, 9, 14))
        self.assertEqual(parse_date("την 1η Ιανουαρίου 2027"), dt.date(2027, 1, 1))
        self.assertEqual(parse_date("09/09/26 15:26"), dt.date(2026, 9, 9))

    def test_file_number_is_not_a_date(self):
        self.assertEqual(find_all_dates("Αρ. Φακέλου 23.02.067.081-2026"), [])
        self.assertEqual(find_all_dates("Κ.Δ.Π. 173/2024"), [])


class ActParsingTests(unittest.TestCase):
    def test_law_fixture(self):
        p = acts.parse_law_text((FX / "law_125.txt").read_text(encoding="utf-8"))
        self.assertEqual(p.number, "125(I)/2026")
        self.assertEqual(p.title, "Ο περί Φορολογίας του Εισοδήματος (Τροποποιητικός) (Αρ. 3) Νόμος του 2026")
        self.assertEqual((p.gazette_no, p.gazette_date), ("5096", dt.date(2026, 9, 11)))
        self.assertTrue(p.caps_title.startswith("ΝΟΜΟΣ ΠΟΥ ΤΡΟΠΟΠΟΙΕΙ ΤΟΥΣ ΠΕΡΙ ΦΟΡΟΛΟΓΙΑΣ"))
        self.assertIn("1η Ιανουαρίου 2027", p.entry_into_force)
        self.assertTrue(p.excerpt.startswith("2. Το άρθρο 8"), p.excerpt[:80])
        self.assertNotIn("Συνοπτικός", p.excerpt)
        self.assertNotIn("του παρόντος\n", p.excerpt)   # margin note removed
        self.assertEqual(p.warnings, [])

    def test_law_120_real_layout(self):
        p = acts.parse_law_text((FX / "law_120.txt").read_text(encoding="utf-8"))
        self.assertEqual(p.number, "120(I)/2026")
        self.assertEqual(p.gazette_date, dt.date(2026, 6, 26))
        self.assertEqual(p.title, "Ο περί Φόρων Κατανάλωσης (Τροποποιητικός) (Αρ. 2) Νόμος του 2026")
        self.assertTrue(p.excerpt.startswith("2. Το Πρώτο Παράρτημα"))
        self.assertNotIn("Τυπώθηκε", p.excerpt)

    def test_annex_laws_split(self):
        segs = acts.split_laws_in_annex((FX / "annex1_5096.txt").read_text(encoding="utf-8"))
        self.assertEqual([n for n, _ in segs], ["125(I)/2026", "126(I)/2026"])
        p126 = acts.parse_law_text(segs[1][1], "126(I)/2026")
        self.assertEqual(p126.title, "Ο περί Θήρας και Προστασίας Άγριων Πτηνών (Τροποποιητικός) Νόμος του 2026")
        self.assertEqual(p126.entry_into_force, "")          # must not inherit 125's clause
        self.assertTrue(p126.excerpt.startswith("2. Το άρθρο 2"))

    def test_kdp_split_and_parse(self):
        secs = acts.split_kdp_sections((FX / "annex3_6045.txt").read_text(encoding="utf-8"))
        self.assertEqual([n for n, _ in secs], ["328/2026", "329/2026", "330/2026", "331/2026"])  # no phantom 173/2024
        parsed = {n: acts.parse_kdp_section(n, s) for n, s in secs}
        self.assertTrue(parsed["328/2026"].title.startswith("Το περί Ασφάλειας και Υγείας στην Εργασία"))
        self.assertIn("1η Οκτωβρίου 2026", parsed["328/2026"].entry_into_force)
        self.assertEqual(parsed["329/2026"].instrument, "Γνωστοποίηση δυνάμει του άρθρου 5")
        self.assertIn("short_title_not_found", parsed["329/2026"].warnings)
        self.assertTrue(parsed["331/2026"].title.startswith("Το περί Φόρου Προστιθέμενης Αξίας"))
        self.assertTrue(parsed["331/2026"].excerpt.startswith("2. Ο Πίνακας Γ"))
        self.assertNotIn("Κ.Δ.Π. 330", parsed["329/2026"].excerpt)   # no bleed into the next act


class HtmlParsingTests(unittest.TestCase):
    def test_cylaw_index_cp1253(self):
        import build_fixtures
        raw = build_fixtures.cylaw_index_html()
        text, enc = Http.decode(cylaw.ARITH_INDEX.format(year=2026), raw)
        self.assertEqual(enc, "windows-1253")
        entries = cylaw.parse_arith_index(text)
        self.assertEqual(len(entries), 10)
        e = [x for x in entries if x.seq == 125 and x.part == "I"][0]
        self.assertEqual(e.title, "Ο περί Φορολογίας του Εισοδήματος (Τροποποιητικός) (Αρ. 3) Νόμος του 2026")
        self.assertEqual(e.pdf_url, "https://www.cylaw.org/nomoi/arith/2026_1_125.pdf")
        self.assertEqual({x.part for x in entries}, {"I", "II", "III"})

    def test_cylaw_kdp_index(self):
        import build_fixtures
        raw = build_fixtures.cylaw_kdp_index_html()
        text, enc = Http.decode(cylaw.KDP_INDEX.format(year=2026), raw)
        entries = cylaw.parse_kdp_index(text)
        self.assertEqual([e.seq for e in entries], [325, 326, 327, 328, 329, 330, 331])
        e = entries[4]
        self.assertEqual((e.number, e.issue, e.page, e.annex), ("329/2026", "6045", "2088", "ΙΙΙ(1)"))
        self.assertEqual(e.date, dt.date(2026, 9, 11))
        self.assertTrue(e.title.startswith("Γνωστοποίηση δυνάμει του άρθρου 5"))
        self.assertEqual(e.pdf_url, "https://www.cylaw.org/KDP/data/2026_1_329.pdf")
        # the printed date of 328 is a typo (11/6/2026); the issue's majority date wins
        dates = cylaw.issue_dates(entries)
        self.assertEqual(dates["6045"], dt.date(2026, 9, 11))
        self.assertEqual(entries[3].date, dt.date(2026, 6, 11))

    def test_gazette_listing_real_html(self):
        html = (FX / "gazette_listing_app6.html").read_text(encoding="utf-8")
        issues = gazette.parse_listing(html, 6)
        self.assertEqual(len(issues), 15)
        self.assertEqual((issues[0].number, issues[0].date, issues[0].pages), ("6045", dt.date(2026, 9, 11), "2087-2120"))
        self.assertTrue(issues[0].url.startswith("https://www.mof.gov.cy/mof/gpo/gazette.nsf/All/4A7D42DCE00D6D38C2258E6F001E4045"))

    def test_gazette_issue_page(self):
        import build_fixtures
        html = build_fixtures.gazette_issue_page("6045", "2087-2120", "11/09/2026", "ΠΑΡΑΡΤΗΜΑ ΤΡΙΤΟ - ΜΕΡΟΣ (Ι)", "4A7D", "6045 11 9 2026 PARARTIMA 3o MEROS I.pdf").decode()
        pdf, meta = gazette.parse_issue_page(html, "https://www.mof.gov.cy/mof/gpo/gazette.nsf/All/4A7D?OpenDocument")
        self.assertEqual(pdf, "https://www.mof.gov.cy/mof/gpo/gazette.nsf/4A7D/$file/6045%2011%209%202026%20PARARTIMA%203o%20MEROS%20I.pdf")
        self.assertEqual(meta["date"], "11/09/2026")

    def test_registrar_and_cbc(self):
        cache = HERE / "offline_cache"
        rows = registrar.parse_news((cache / (Http.cache_key(registrar.NEWS) + ".bin")).read_text(encoding="utf-8"))
        self.assertEqual(rows[0]["date"], dt.date(2026, 9, 10))
        self.assertIn("Πραγματικών Δικαιούχων", rows[0]["title"])
        arts = cbc.parse_announcements((cache / (Http.cache_key(cbc.ANNOUNCEMENTS) + ".bin")).read_text(encoding="utf-8"))
        self.assertEqual(arts[0]["date"], dt.date(2026, 9, 14))
        self.assertTrue(arts[2]["url"].endswith("/payment-accounts-directive-10-09-2026"))

    def test_nomoplatform_timeline(self):
        text = "Αρ. Φακέλου\n23.02.067.081-2026\nΠορεία\n14 Ιουλίου 2026\nΚατάθεση και παραπομπή στην Επιτροπή\n10/09/2026\nΣυζήτηση στην Επιτροπή\n"
        tl = nomoplatform.extract_timeline(text)
        self.assertEqual([(e["date"], e["kind"]) for e in tl], [("2026-07-14", "submitted"), ("2026-09-10", "committee")])
        self.assertEqual(nomoplatform.extract_file_number(text), "23.02.067.081-2026")


class RelevanceTests(unittest.TestCase):
    def areas(self, title, body="", ids=None):
        r = classify(title, body, term_ids=set(ids or []))
        return r.score, r.areas

    def test_titles(self):
        self.assertEqual(self.areas("Ο περί Φορολογίας του Εισοδήματος (Τροποποιητικός) Νόμος του 2026"), (2, ["tax"]))
        self.assertEqual(self.areas("Ο περί Ρυθμίσεως Οδών και Οικοδομών (Τροποποιητικός) Νόμος του 2026", ids=[354]), (2, ["real_estate"]))
        self.assertEqual(self.areas("Ο περί Αλλοδαπών και Μεταναστεύσεως (Τροποποιητικός) Νόμος του 2026",
                                    "τροποποίηση ώστε να ρυθμιστεί η άδεια διαμονής σε υπηκόους τρίτων χωρών που εργοδοτούνται σε εταιρείες")[1], ["immigration"])
        self.assertEqual(self.areas("Amendment of the Directive on the Opening and Maintaining of Payment Accounts"), (2, ["banking"]))
        self.assertEqual(self.areas("Ο περί Εθνικού Συστήματος Βιβλιοθηκών Νόμος του 2026", "Σκοπός είναι η θέσπιση εθνικού συστήματος βιβλιοθηκών."), (0, []))
        self.assertEqual(self.areas("Το περί Ελέγχου της Ρύπανσης της Ατμόσφαιρας (Εγκαταστάσεις Επεξεργασίας Ξυλείας) Διάταγμα του 2026")[0], 0)

    def test_noise(self):
        self.assertEqual(self.areas("Κενές Θέσεις")[0], 0)
        self.assertEqual(self.areas("Statistics on Interest Rates applied by Monetary Financial Institutions")[0], 0)
        self.assertEqual(self.areas("Ο Υπουργός Εργασίας και Κοινωνικών Ασφαλίσεων αναχωρεί για τη Βιέννη")[0], 0)
        self.assertEqual(self.areas("Δήλωση του Υπουργού Οικονομικών για τον περί Φορολογίας Νόμο")[0], 1)   # statement about an instrument: weak
        self.assertEqual(self.areas("Προσωρινή διακοπή στη λειτουργία Μηχανογραφικών Συστημάτων του Τμήματος Φορολογίας")[0], 0)


class EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = Path(tempfile.mkdtemp(prefix="digest-e2e-"))
        cmd = [sys.executable, str(ROOT / "scripts" / "digest_collect.py"), "--offline", "--cache-dir", str(HERE / "offline_cache"),
               "--today", "2026-09-14", "--out", str(cls.out)]
        cls.proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        cls.run_dir = cls.out / "2026-09-07_2026-09-13"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.out, ignore_errors=True)

    def test_exit_and_files(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr[-2000:])
        for f in ("items.json", "all_items.json", "status.json", "skeleton.md"):
            self.assertTrue((self.run_dir / f).exists(), f)

    def test_status(self):
        st = json.loads((self.run_dir / "status.json").read_text(encoding="utf-8"))
        self.assertEqual(st["window"], {"start": "2026-09-07", "end": "2026-09-13"})
        for src in ("gazette", "cylaw", "cylawkdp", "nomoplatform", "govcy", "registrar", "cbc"):
            self.assertNotIn("error", st["sources"][src], src)
        self.assertEqual(st["sources"]["gazette"]["gazette_app16"]["in_window"], 1)
        self.assertEqual(st["sources"]["gazette"]["gazette_app6"]["in_window"], 2)

    def test_items(self):
        data = json.loads((self.run_dir / "items.json").read_text(encoding="utf-8"))
        ids = {i["id"] for i in data["items"]}
        by_id = {i["id"]: i for i in data["items"]}
        # laws: 125 kept (tax), 126 in other_laws, 124/120 outside window
        self.assertIn("law-125(I)/2026", ids)
        self.assertNotIn("law-126(I)/2026", ids)
        self.assertEqual([o["number"] for o in data["other_laws"]], ["Ν. 126(I)/2026"])
        self.assertNotIn("law-124(I)/2026", {i["id"] for i in data["items"] + data["other_laws"]})
        law = by_id["law-125(I)/2026"]
        self.assertEqual(law["source"], "cylaw")                       # merged: CyLaw per-law PDF is primary
        self.assertIn("gazette", law["extra"]["also_in"])
        self.assertTrue(law["extra"]["gazette_issue_url"].endswith("AAAA1111BBBB2222CCCC3333DDDD4444?OpenDocument"))
        self.assertEqual(law["date"], "2026-09-11")
        self.assertIn("1η Ιανουαρίου 2027", law["entry_into_force"])
        # Κ.Δ.Π.: 329 (social contributions), 331 (VAT) kept; 330 (environment) and 327 (road safety) dropped
        self.assertIn("kdp-329/2026", ids)
        self.assertIn("kdp-331/2026", ids)
        self.assertNotIn("kdp-330/2026", ids)
        self.assertNotIn("kdp-327/2026", ids)
        self.assertEqual(by_id["kdp-331/2026"]["practice_areas"], ["tax"])
        # Κ.Δ.Π. merged from the Gazette annex and the CyLaw index: CyLaw's per-act PDF is primary, gazette kept
        self.assertEqual(by_id["kdp-329/2026"]["source"], "cylaw")
        self.assertIn("gazette", by_id["kdp-329/2026"]["extra"]["also_in"])
        self.assertEqual(by_id["kdp-329/2026"]["url"], "https://www.cylaw.org/KDP/data/2026_1_329.pdf")
        self.assertEqual(by_id["kdp-329/2026"]["date"], "2026-09-11")
        self.assertTrue(any(w.startswith("index_date_typo") for w in by_id.get("kdp-328/2026", {}).get("warnings", [])) or "kdp-328/2026" not in by_id)
        # bills: 3 in progress with in-window events, 1 voted → adopted, library bill dropped
        self.assertEqual(by_id["bill-62570"]["contour"], "adopted")
        self.assertEqual(by_id["bill-62570"]["date_kind"], "voted")
        self.assertEqual(by_id["bill-62540"]["date"], "2026-09-10")
        self.assertEqual(by_id["bill-62540"]["date_kind"], "committee")
        self.assertEqual(sorted(by_id["bill-62540"]["practice_areas"]), ["real_estate", "tax"])
        self.assertEqual(by_id["bill-62560"]["practice_areas"], ["immigration"])
        self.assertNotIn("bill-62550", ids)
        # regulators
        self.assertIn("govcy-130013", ids)          # VAT deadline extension
        self.assertNotIn("govcy-130012", ids)       # statistics
        self.assertNotIn("govcy-130014", ids)       # minister travels
        self.assertNotIn("govcy-130011", ids)       # IT downtime
        self.assertIn("cbc-payment-accounts-directive-10-09-2026", ids)
        self.assertNotIn("cbc-cir-statistics-august-2026-09-09-2026", ids)
        self.assertTrue(any(i["source"] == "registrar" for i in data["items"]))
        # every kept item is dated inside the window
        for i in data["items"]:
            self.assertTrue("2026-09-07" <= i["date"] <= "2026-09-13", i["id"])

    def test_skeleton_sections(self):
        sk = (self.run_dir / "skeleton.md").read_text(encoding="utf-8")
        for h in ("## A1.", "## A2.", "## A3.", "## B1.", "## B2.", "## C.", "## D.", "## E."):
            self.assertIn(h, sk)
        self.assertIn("entry into force (verbatim): Ο παρών Νόμος τίθεται σε ισχύ από την 1η Ιανουαρίου 2027.", sk)
        self.assertIn("2026-09-10 committee", sk)
        self.assertNotIn("2067-", sk)


if __name__ == "__main__":
    import build_fixtures
    build_fixtures.build()
    unittest.main(verbosity=2)
