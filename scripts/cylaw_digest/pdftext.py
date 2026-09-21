"""PDF → text. Prefers poppler's pdftotext (fast, keeps reading order well for
the Gazette's two-column margin notes); falls back to pypdf.

Text is returned per page, joined with form-feeds, so callers can reason about
page headers ("Ε.Ε. Παρ. ΙΙΙ(Ι) Κ.Δ.Π. 329/2026 / Αρ. 6045, 11.9.2026").
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def pdf_to_text(content: bytes, max_pages: int | None = None) -> str:
    if shutil.which("pdftotext"):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            cmd = ["pdftotext", "-enc", "UTF-8"]
            if max_pages:
                cmd += ["-l", str(max_pages)]
            cmd += [path, "-"]
            out = subprocess.run(cmd, capture_output=True, timeout=120)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.decode("utf-8", "replace")
        finally:
            Path(path).unlink(missing_ok=True)
    try:
        from pypdf import PdfReader  # type: ignore
        import io
        reader = PdfReader(io.BytesIO(content))
        pages = reader.pages if not max_pages else reader.pages[:max_pages]
        return "\f".join((p.extract_text() or "") for p in pages)
    except Exception:  # pragma: no cover
        return ""


def pages(text: str) -> list[str]:
    return [p for p in text.split("\f")]
