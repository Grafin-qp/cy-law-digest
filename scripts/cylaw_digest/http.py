"""HTTP layer: one place that knows about proxies, encodings, Cloudflare and
sandbox egress policies, so the collectors can stay dumb.

Every fetch returns a FetchResult; nothing raises for a bad status. A collector
checks `res.ok` and otherwise reports `res.reason` upward, so the run log can
say precisely *why* a source produced nothing ("proxy_denied" is the sandbox
network policy; "cloudflare" is the site's bot wall; etc.).
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter

log = logging.getLogger("cylaw_digest.http")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

# Hosts whose pages declare (or rely on) a legacy Greek code page.
FORCED_ENCODING = {
    "www.cylaw.org": "windows-1253",
    "cylaw.org": "windows-1253",
}

_CF_MARKERS = ("Just a moment...", "challenge-platform", "cf-chl", "Performing security verification")


@dataclass
class FetchResult:
    url: str
    status: int = 0
    content: bytes = b""
    text: str = ""
    encoding: str = ""
    reason: str = ""          # "" when ok, else proxy_denied|cloudflare|http_error|ssl_error|timeout|connection|robots
    elapsed: float = 0.0
    from_cache: bool = False
    headers: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.reason == "" and 200 <= self.status < 300

    def json(self):
        import json
        return json.loads(self.text)


class Http:
    def __init__(self, raw_dir: Optional[Path] = None, delay: float = 0.6, timeout: float = 40.0,
                 insecure_hosts: Optional[set[str]] = None, cache_dir: Optional[Path] = None, offline: bool = False):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept-Language": "el,en;q=0.8,ru;q=0.6"})
        adapter = HTTPAdapter(max_retries=2, pool_connections=8, pool_maxsize=8)
        self.s.mount("https://", adapter)
        self.s.mount("http://", adapter)
        self.raw_dir = raw_dir
        self.delay = delay
        self.timeout = timeout
        self.insecure_hosts = insecure_hosts or set()
        self.cache_dir = cache_dir      # extra read-only cache (fixtures / previous run)
        self.offline = offline          # never touch the network
        self._last_hit: dict[str, float] = {}
        self.stats = {"requests": 0, "cached": 0, "failed": 0}

    # ---- caching --------------------------------------------------------
    @staticmethod
    def cache_key(url: str) -> str:
        h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
        host = urlparse(url).netloc.replace(":", "_")
        return f"{host}__{h}"

    def _cache_path(self, url: str, base: Path) -> Path:
        return base / (self.cache_key(url) + ".bin")

    def _read_cache(self, url: str) -> Optional[bytes]:
        for base in (self.cache_dir, self.raw_dir):
            if base is None:
                continue
            p = self._cache_path(url, base)
            if p.exists():
                return p.read_bytes()
        return None

    def _write_cache(self, url: str, content: bytes) -> None:
        if self.raw_dir is None:
            return
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self._cache_path(url, self.raw_dir).write_bytes(content)
        (self.raw_dir / "index.txt").open("a", encoding="utf-8").write(f"{self.cache_key(url)}\t{url}\n")

    # ---- decoding -------------------------------------------------------
    @staticmethod
    def decode(url: str, content: bytes, header_ct: str = "") -> tuple[str, str]:
        host = urlparse(url).netloc
        enc = FORCED_ENCODING.get(host)
        if not enc:
            m = re.search(rb"charset=[\"']?([A-Za-z0-9_\-]+)", content[:4096], re.I)
            if m:
                enc = m.group(1).decode("ascii", "ignore")
            elif "charset=" in header_ct:
                enc = header_ct.split("charset=")[-1].split(";")[0].strip()
        if not enc:
            enc = "utf-8"
        try:
            return content.decode(enc, errors="replace"), enc
        except LookupError:
            return content.decode("utf-8", errors="replace"), "utf-8"

    # ---- fetching -------------------------------------------------------
    @staticmethod
    def full_url(url: str, params: Optional[dict] = None) -> str:
        """The exact URL requests will send (param order + encoding) – also used by
        the fixture builder so offline cache keys match."""
        if not params:
            return url
        return requests.Request("GET", url, params=params).prepare().url

    def get(self, url: str, *, use_cache: bool = True, params: Optional[dict] = None) -> FetchResult:
        url = self.full_url(url, params)
        cached = self._read_cache(url) if use_cache else None
        if cached is not None:
            text, enc = self.decode(url, cached)
            self.stats["cached"] += 1
            return FetchResult(url=url, status=200, content=cached, text=text, encoding=enc, from_cache=True)
        if self.offline:
            self.stats["failed"] += 1
            return FetchResult(url=url, status=0, reason="offline_miss")

        host = urlparse(url).netloc
        wait = self.delay - (time.time() - self._last_hit.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        t0 = time.time()
        self.stats["requests"] += 1
        verify = host not in self.insecure_hosts
        try:
            r = self.s.get(url, timeout=self.timeout, verify=verify, allow_redirects=True)
        except requests.exceptions.ProxyError as e:
            self.stats["failed"] += 1
            return FetchResult(url=url, reason="proxy_denied", elapsed=time.time() - t0,
                               text=str(e)[:300])
        except requests.exceptions.SSLError as e:
            self.stats["failed"] += 1
            return FetchResult(url=url, reason="ssl_error", elapsed=time.time() - t0, text=str(e)[:300])
        except requests.exceptions.Timeout:
            self.stats["failed"] += 1
            return FetchResult(url=url, reason="timeout", elapsed=time.time() - t0)
        except requests.exceptions.ConnectionError as e:
            self.stats["failed"] += 1
            msg = str(e)
            reason = "proxy_denied" if ("403" in msg and "CONNECT" in msg.upper()) else "connection"
            return FetchResult(url=url, reason=reason, elapsed=time.time() - t0, text=msg[:300])
        finally:
            self._last_hit[host] = time.time()

        content = r.content
        ct = r.headers.get("Content-Type", "")
        text, enc = ("", "") if "pdf" in ct or url.lower().endswith(".pdf") else self.decode(url, content, ct)
        res = FetchResult(url=url, status=r.status_code, content=content, text=text, encoding=enc,
                          elapsed=time.time() - t0, headers=dict(r.headers))
        head = text[:3000] if text else content[:3000].decode("latin-1", "ignore")
        if r.status_code in (403, 503) and any(m in head for m in _CF_MARKERS):
            res.reason = "cloudflare"
        elif r.status_code == 403 and r.headers.get("cf-mitigated"):
            res.reason = "cloudflare"
        elif r.status_code >= 400:
            res.reason = "http_error"
        if res.ok:
            self._write_cache(url, content)
        else:
            self.stats["failed"] += 1
            log.warning("fetch failed %s -> %s %s", url, res.status, res.reason)
        return res

    def get_pdf(self, url: str, *, use_cache: bool = True) -> FetchResult:
        res = self.get(url, use_cache=use_cache)
        if res.ok and not res.content.startswith(b"%PDF"):
            res.reason = "not_pdf"
            head = res.content[:2000].decode("latin-1", "ignore")
            if any(m in head for m in _CF_MARKERS):
                res.reason = "cloudflare"
        return res
