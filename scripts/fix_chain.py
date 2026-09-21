#!/usr/bin/env python3
"""Complete an incomplete TLS certificate chain without disabling verification.

www.mof.gov.cy (Επίσημη Εφημερίδα) serves its leaf certificate without the intermediate
CA certificate. Browsers repair this silently by following the leaf's AIA "CA Issuers"
URL; Python's `requests` does not, so the collector sees `ssl_error`. This script does
what the browser does: fetches the leaf, follows AIA to the intermediate(s), appends them
to certifi's bundle and verifies the host against the result — verification stays on.

    python3 scripts/fix_chain.py www.mof.gov.cy --out ~/digest_out/ca-bundle.pem
    export REQUESTS_CA_BUNDLE=~/digest_out/ca-bundle.pem      # requests picks it up

Prints the bundle path and exits 0 when the verified connection succeeds; exits 1 (nothing
printed on stdout) when the chain cannot be completed — e.g. the root itself is not a
public CA. In that case the workflow falls back to `--insecure-hosts` for that host only.
Needs `cryptography` and `certifi` (both pip-installable; certifi comes with requests).
"""
from __future__ import annotations

import argparse
import socket
import ssl
import sys
import urllib.request
from pathlib import Path


def fetch_leaf(host: str, port: int = 443, timeout: int = 20) -> bytes:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with socket.create_connection((host, port), timeout=timeout) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as tls:
            der = tls.getpeercert(binary_form=True)
    if not der:
        raise RuntimeError("no certificate received")
    return der


def aia_issuer_urls(cert) -> list[str]:
    from cryptography import x509
    from cryptography.x509.oid import AuthorityInformationAccessOID as OID
    try:
        aia = cert.extensions.get_extension_for_class(x509.AuthorityInformationAccess).value
    except x509.ExtensionNotFound:
        return []
    return [d.access_location.value for d in aia
            if d.access_method == OID.CA_ISSUERS and hasattr(d.access_location, "value")]


def load_any(data: bytes):
    from cryptography import x509
    if b"-----BEGIN" in data:
        return x509.load_pem_x509_certificate(data)
    return x509.load_der_x509_certificate(data)


def chase(host: str, max_depth: int = 4, log=print) -> list:
    """Return the intermediate certificates reachable from the host's leaf via AIA."""
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization  # noqa: F401  (import check)
    leaf = x509.load_der_x509_certificate(fetch_leaf(host))
    log(f"leaf: {leaf.subject.rfc4514_string()} | issuer: {leaf.issuer.rfc4514_string()}")
    chain, cur = [], leaf
    for _ in range(max_depth):
        if cur.issuer == cur.subject:
            break                                   # self-signed root reached
        urls = aia_issuer_urls(cur)
        if not urls:
            log("no AIA CA Issuers URL on " + cur.subject.rfc4514_string())
            break
        nxt = None
        for u in urls:
            try:
                with urllib.request.urlopen(u, timeout=20) as r:
                    nxt = load_any(r.read())
                log(f"fetched issuer from {u}: {nxt.subject.rfc4514_string()}")
                break
            except Exception as e:                  # noqa: BLE001
                log(f"AIA fetch failed {u}: {e}")
        if nxt is None:
            break
        chain.append(nxt)
        cur = nxt
    return chain


def write_bundle(intermediates: list, out: Path) -> Path:
    import certifi
    from cryptography.hazmat.primitives import serialization
    base = Path(certifi.where()).read_bytes()
    extra = b"".join(c.public_bytes(serialization.Encoding.PEM) for c in intermediates)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base + b"\n" + extra)
    return out


def verify(host: str, bundle: Path, timeout: int = 20) -> bool:
    ctx = ssl.create_default_context(cafile=str(bundle))
    try:
        with socket.create_connection((host, 443), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host):
                return True
    except ssl.SSLError as e:
        print(f"still failing with the completed chain: {e}", file=sys.stderr)
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hosts", nargs="+")
    ap.add_argument("--out", required=True, help="where to write the completed CA bundle (PEM)")
    a = ap.parse_args()
    log = lambda m: print(m, file=sys.stderr)  # noqa: E731
    inters = []
    for h in a.hosts:
        try:
            inters += chase(h, log=log)
        except Exception as e:                      # noqa: BLE001
            log(f"{h}: cannot fetch/parse the chain: {e}")
    if not inters:
        log("no intermediate certificates obtained")
        return 1
    bundle = write_bundle(inters, Path(a.out).expanduser())
    ok = all(verify(h, bundle) for h in a.hosts)
    if not ok:
        return 1
    print(bundle)
    return 0


if __name__ == "__main__":
    sys.exit(main())
