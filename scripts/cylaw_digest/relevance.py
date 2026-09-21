"""Practice-area classification.

Two signals are combined:
  * keyword hits in title / verbatim text (accent- and case-insensitive Greek,
    plus English for the CBC site);
  * Nomoplatform thematic-unit taxonomy (by term id, and by term name through
    the same keyword sets, so new terms still match).

Score: 2 = strong (a strong keyword or a taxonomy term), 1 = weak (only weak
keywords), 0 = out of scope. "Noise" patterns (vacancies, statistics, events)
demote weak-only matches to 0 so that the digest is not padded with
"Statistics on interest rates" every week.

Extending the filter = editing this file. Keep the practice list aligned with
references/relevance.md, which is the human-readable copy.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .greekdates import strip_accents

AREAS = ("real_estate", "corporate", "tax", "banking", "immigration", "employment")
AREA_EN = {
    "real_estate": "Real estate & transactions",
    "corporate": "Corporate & M&A",
    "tax": "Tax",
    "banking": "Banking, payments & AML",
    "immigration": "Immigration",
    "employment": "Employment & social insurance",
}
AREA_RU = {
    "real_estate": "Недвижимость и сделки",
    "corporate": "Корпоративное право и M&A",
    "tax": "Налоги",
    "banking": "Банки, платёжные услуги, AML",
    "immigration": "Миграция",
    "employment": "Трудовое право и соцстрахование",
}

# --- keyword sets (write them accent-free, lower-case; matched on normalised text) ---
STRONG = {
    "real_estate": [
        r"ακινητ", r"κτηματολογ", r"μεταβιβασ", r"τιτλ\w* ιδιοκτησ", r"πολεοδομ", r"ενοικι", r"μισθωσ",
        r"ενυποθηκ", r"υποθηκ", r"αγοραπωλησ", r"διακατοχ", r"απαλλοτριωσ", r"τελ\w* μεταβιβασ",
        r"εγκλωβισμεν\w* αγοραστ", r"καταλυμ", r"ρυθμισεως οδων και οικοδομων", r"οικοδομ\w* αδει",
        r"στεγαστ", r"κοινοχρηστ", r"land registry", r"immovable property", r"title deed",
    ],
    "corporate": [
        r"\bεταιρει", r"εφορ\w* εταιρειων", r"συνεταιρισμ", r"πραγματικ\w* δικαιουχ", r"αφερεγγυοτ",
        r"εκκαθαρισ", r"πτωχευσ", r"εμπιστευμ", r"συγχωνευσ", r"διασυνοριακ\w* μετατροπ", r"κεφαλαιαγορ",
        r"χρηματιστηρ", r"αξιογραφ", r"επενδυτικ\w* υπηρεσ", r"ξεπλυμ", r"νομιμοποιησ\w* εσοδων",
        r"εμπορικ\w* επωνυμ", r"ελεγκτ\w* επαγγελμ", r"λογιστ\w* (?:προτυπ|επαγγελμ)", r"διοικητικ\w* συμβουλι",
        r"εμπορικ\w* δικαστηρ", r"beneficial owner", r"companies law", r"registrar of companies",
    ],
    "tax": [
        r"φορολογ", r"\bφορο", r"φ\.?π\.?α\b", r"τελωνει", r"χαρτοσημ", r"κεφαλαιουχικ\w* κερδ",
        r"εισοδημ", r"αμυντικ\w* εισφορ", r"εκτακτ\w* εισφορ", r"εφοριακ", r"\btax\b", r"\bvat\b",
        r"dac\d", r"pillar", r"διπλ\w* φορολογ", r"φορ\w* καταναλωσ", r"ειδικ\w* φορ", r"excise",
    ],
    "banking": [
        r"\bτραπεζ", r"πιστωτικ\w* ιδρυμ", r"\bδανει", r"υπηρεσι\w* πληρωμ", r"ιδρυμ\w* πληρωμ", r"ηλεκτρονικ\w* χρημ",
        r"ξεπλυμ", r"ανοιγμ\w* λογαριασμ", r"χρηματοοικονομ", r"κρυπτο", r"εκποιησ",
        r"\bbank", r"credit institution", r"payment (?:institution|service)", r"e-?money", r"\baml\b",
        r"directive", r"οδηγι", r"εγκυκλι", r"circular", r"licens", r"αδειοδοτ", r"sanction", r"κυρωσε",
    ],
    "immigration": [
        r"μεταναστ", r"αλλοδαπ", r"αδει\w* (?:παραμον|διαμον)", r"πολιτογραφ", r"υπηκοοτ", r"θεωρησ",
        r"αρχει\w* πληθυσμ", r"μονιμ\w* αδει", r"ξεν\w* εργαζομ", r"εργοδοτησ\w* αλλοδαπ", r"schengen", r"etias",
        r"υπηκο\w* τριτ\w* χωρ", r"third.country national", r"residence permit", r"immigration", r"digital nomad",
    ],
    "employment": [
        r"\bεργοδοτ", r"\bαπασχολησ", r"τερματισμ\w* απασχολ", r"κοινωνικ\w* ασφαλισ", r"κοινωνικ\w* εισφορ",
        r"κατωτατ\w* μισθ", r"ελαχιστ\w* μισθ", r"ωραρι", r"αδει\w* μετ.? απολαβ", r"γονικ\w* αδει", r"μητροτητ",
        r"πατροτητ", r"τηλεργασ", r"συλλογικ\w* συμβασ", r"μισθοδοσ", r"ταμει\w* προνοιας", r"εργασιακ\w* σχεσ",
        r"προστασι\w* μισθων", r"εργατικ\w* δικαι", r"ισ\w* αμοιβ", r"minimum wage", r"employment",
    ],
}
WEAK = {
    "real_estate": [r"οικοδομ", r"κατοικ", r"γη\b", r"ιδιοκτησ", r"ενοικ", r"αναπτυξ\w* γης", r"housing"],
    "corporate": [r"\bεπιχειρησ", r"\bεμπορ", r"\bεπενδυ", r"ανταγωνισμ", r"\bcompany", r"\bbusiness"],
    "tax": [r"εισφορ", r"τελ(?:ος|η|ων)\b"],
    "banking": [r"χρηματοδοτ", r"ασφαλιστικ", r"επιτοκ", r"interest rate", r"financial", r"payment"],
    "immigration": [r"ασυλ", r"προσφυγ", r"visa", r"migration"],
    "employment": [r"\bεργασ", r"\bεργατ", r"\bσυνταξ", r"ασφαλει\w* και υγει", r"labour", r"social insurance"],
}
# Titles that are administrative noise even if a weak keyword matches.
NOISE = [
    r"κεν\w* θεσ", r"στατιστικ", r"statistic", r"survey", r"δεικτ\w* τιμ", r"διαγωνισμ", r"προσφορ",
    r"υποτροφ", r"σεμιναρ", r"συνεδρι", r"εκδηλωσ", r"συλλυπητ", r"συγχαιρ", r"επισκεψ", r"συναντησ",
    r"προυπολογισμ", r"budget", r"vacanc", r"blog", r"insights", r"balance sheet", r"προσωρινη διακοπη",
    r"τηλεοπτικ", r"μηνυμα", r"χαιρετισμ", r"ομιλι", r"διαλεξ", r"speech", r"conference", r"workshop",
    r"συγχαρητηρ", r"\bδεικτ", r"\d\w* τριμην", r"τριμηνο", r"αφιξ\w* τουριστ", r"εγγραφ\w* μηχανοκινητ",
    r"στοιχει\w* επιτοκ", r"non-performing loans", r"aggregate .*data", r"bank holiday", r"\bdata with reference",
    r"monetary and financial statistics", r"interest rates? (?:on|for|data)",
    # periodic releases: a title ending in ": <month> 2026", ": Ιανουάριος-Αύγουστος 2026"
    r":\s*(?:ιανουαρ|φεβρουαρ|μαρτ|απριλ|μαι|ιουν|ιουλ|αυγουστ|σεπτεμβρ|οκτωβρ|νοεμβρ|δεκεμβρ)\w*(?:\s*-\s*[α-ω]+)?\s+\d{4}\s*$",
]
# Statements and meetings: we keep them only when they carry a strong legal keyword.
SOFT_NOISE = [r"δηλωσ\w* τ(?:ου|ησ) (?:υπουργ|υφυπουργ|προεδρ)", r"συναντησ", r"αναχωρει", r"επιστρεφει",
              r"^προεδρ\w* τησ δημοκρατιασ", r"παρεμβασ\w* τ(?:ου|ησ) (?:υπουργ|υφυπουργ|προεδρ)", r"συνεντευξ",
              r"^(?:ο|η) (?:υπουργ|υφυπουργ)", r"\bκ\. ?[α-ω]{2,} [α-ω]{3,}", r"συμμετοχ\w* τ(?:ου|ησ) (?:υπουργ|υφυπουργ)"]

# Nomoplatform thematic-unit ids (see references/relevance.md). Ids are a
# convenience only – names are also matched through the keyword sets.
NOMO_TERMS = {
    "real_estate": {301, 247, 701, 699, 354, 299, 397, 453, 394, 652},
    "corporate": {369, 691, 676, 447, 538, 559, 347, 599, 679, 456, 737, 688, 440, 526},
    "tax": {332, 580, 616, 641},
    "banking": {383, 382, 452, 247, 528, 744, 304},
    "immigration": {416, 643, 553, 444, 698, 434, 417, 564},
    "employment": {40, 647, 585, 491, 714, 564, 682},
}

# A title that names a legal instrument is news even when it is phrased as a statement.
INSTRUMENT = re.compile(r"\bνομ(?:οσ|ου|ο|οι|ων|ουσ|οσχεδι\w*)\b|\bδιαταγμ|\bκανονισμ|\bεγκυκλι|\bοδηγι|τροποποι|\bψηφ|\bαποφασ|\bγνωστοποιησ|\bκ\.?δ\.?π|\bπαρατασ|\bπροθεσμ|\bσχεδι|\bdirective|\bcircular|\bregulation|\blaw\b|\bact\b")

_STRONG = {a: [re.compile(p) for p in ps] for a, ps in STRONG.items()}
_WEAK = {a: [re.compile(p) for p in ps] for a, ps in WEAK.items()}
_NOISE = [re.compile(p) for p in NOISE]
_SOFT_NOISE = [re.compile(p) for p in SOFT_NOISE]


def norm(text: str) -> str:
    t = strip_accents(text or "").lower()
    t = t.replace("ς", "σ")  # final sigma
    return re.sub(r"\s+", " ", t)


@dataclass
class Relevance:
    score: int = 0
    areas: list[str] = field(default_factory=list)
    hits: list[str] = field(default_factory=list)


def classify(title: str, body: str = "", term_ids: set[int] | None = None, term_names: list[str] | None = None,
             title_weight_only: bool = False) -> Relevance:
    """Classify one item. `body` is scanned only for strong keywords (a weak keyword
    deep in a 20-page act means nothing)."""
    t = norm(title)
    b = norm(body)[:20000]
    names = norm(" | ".join(term_names or []))
    strong_areas, weak_areas, hits = set(), set(), []

    # 1) title + taxonomy names decide the practice areas
    for area, pats in _STRONG.items():
        for p in pats:
            if p.search(t) or (names and p.search(names)):
                strong_areas.add(area)
                hits.append(f"{area}:{p.pattern}")
                break
    for area, ids in NOMO_TERMS.items():
        if term_ids and ids & term_ids:
            strong_areas.add(area)
            hits.append(f"{area}:term{sorted(ids & term_ids)}")
    # 2) the body (purpose / long title / excerpt) is consulted only when the title says nothing –
    #    a passing mention of "companies" inside an immigration bill must not tag it as corporate
    if not strong_areas and b and not title_weight_only:
        for area, pats in _STRONG.items():
            for p in pats:
                if p.search(b):
                    strong_areas.add(area)
                    hits.append(f"{area}:body:{p.pattern}")
                    break
    for area, pats in _WEAK.items():
        if area in strong_areas:
            continue
        for p in pats:
            if p.search(t) or (names and p.search(names)):
                weak_areas.add(area)
                hits.append(f"{area}:~{p.pattern}")
                break

    noisy = any(p.search(t) for p in _NOISE)
    soft = any(p.search(t) for p in _SOFT_NOISE)
    instrument = bool(INSTRUMENT.search(t))
    if strong_areas:
        # hard noise (vacancies, statistics, events) wins over any keyword: "Statistics on loans" is not law.
        if noisy:
            return Relevance(0, [], hits + ["noise"])
        # a statement / trip / meeting is kept only when the title names a legal instrument
        if soft and not instrument:
            return Relevance(0, [], hits + ["soft-noise"])
        return Relevance(2 if not soft else 1, sorted(strong_areas), hits)
    if weak_areas and not noisy and not soft:
        return Relevance(1, sorted(weak_areas), hits)
    return Relevance(0, [], hits + (["noise"] if noisy or soft else []))
