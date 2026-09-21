"""The single record type every collector emits."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field, asdict
from typing import Optional

CONTOURS = ("adopted", "in_progress", "regulator")
KINDS = ("law", "kdp", "bill", "plenary", "committee", "announcement", "circular", "guidance")


@dataclass
class Item:
    id: str
    contour: str                 # adopted | in_progress | regulator
    kind: str                    # law | kdp | bill | plenary | committee | announcement | circular | guidance
    source: str                  # gazette | cylaw | nomoplatform | govcy | registrar | cbc
    source_label: str            # human label, e.g. "Επίσημη Εφημερίδα, Παρ. Ι(Ι), Αρ. 5094"
    date: Optional[dt.date]      # the event date that put the item in the window
    date_kind: str               # published | voted | submitted | committee | announced | entry_into_force | modified
    title_el: str = ""
    title_en: str = ""
    number: str = ""             # "Ν. 124(I)/2026", "Κ.Δ.Π. 329/2026", file no. for bills
    url: str = ""
    pdf_url: str = ""
    verbatim: dict = field(default_factory=dict)   # exact source wording, keyed by field name
    excerpt: str = ""            # first part of the act's substantive text, verbatim
    entry_into_force: str = ""   # verbatim clause, if found
    status: str = ""             # for bills: Εκκρεμεί / Υπερψηφίστηκε / ...
    practice_areas: list[str] = field(default_factory=list)
    relevance: int = 0           # 0 none, 1 weak, 2 strong
    relevance_hits: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        d = asdict(self)
        d["date"] = self.date.isoformat() if self.date else None
        return d

    @staticmethod
    def from_json(d: dict) -> "Item":
        d = dict(d)
        d["date"] = dt.date.fromisoformat(d["date"]) if d.get("date") else None
        return Item(**d)
