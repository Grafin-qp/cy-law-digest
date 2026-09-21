#!/usr/bin/env python3
"""Fetch a collector run that was produced elsewhere (GitHub Actions, a local
cron) so that the digest can be written in an environment without egress to
the Cyprus sites.

    python3 scripts/fetch_run.py --repo opiniq/cy-law-digest                 # runs/latest → ~/digest_out/latest
    python3 scripts/fetch_run.py --repo opiniq/cy-law-digest --run 2026-09-07_2026-09-13
    python3 scripts/fetch_run.py --dir "/path/to/synced/folder/runs/latest"  # from a connected / synced folder

GitHub is reachable from Claude's sandbox under the default "package managers
only" policy (github.com, raw.githubusercontent.com, api.github.com), which is
the whole point. A public repo needs no credentials; for a private repo set
GITHUB_TOKEN in the environment (never paste tokens into a chat).

Prints the run directory and the source status table; exit code 2 if the run's
status.json says every source was blocked (nothing to write from).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

FILES = ("status.json", "items.json", "all_items.json", "skeleton.md", "collect.log")


def fetch_github(repo: str, ref: str, run: str, dest: Path) -> Path:
    token = os.environ.get("GITHUB_TOKEN", "")
    url = os.environ.get("DIGEST_GIT_URL") or f"https://{'x-access-token:' + token + '@' if token else ''}github.com/{repo}.git"
    tmp = Path(tempfile.mkdtemp(prefix="digest-run-"))
    try:
        subprocess.run(["git", "clone", "--depth", "1", "--branch", ref, "--filter=blob:none", "--sparse", url, str(tmp)],
                       check=True, capture_output=True, text=True)
        subprocess.run(["git", "-C", str(tmp), "sparse-checkout", "set", f"runs/{run}"], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        sys.exit(f"git failed: {e.stderr.strip()[:500]}")
    src = tmp / "runs" / run
    if not src.exists():
        sys.exit(f"run '{run}' not found in {repo}@{ref} (looked for runs/{run})")
    dest.mkdir(parents=True, exist_ok=True)
    for p in src.rglob("*"):
        if p.is_file():
            target = dest / p.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
    shutil.rmtree(tmp, ignore_errors=True)
    return dest


def fetch_dir(src: Path, dest: Path) -> Path:
    if not (src / "status.json").exists():
        sys.exit(f"{src} does not look like a run directory (no status.json)")
    dest.mkdir(parents=True, exist_ok=True)
    for p in src.rglob("*"):
        if p.is_file() and "raw" not in p.relative_to(src).parts:
            target = dest / p.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--repo", help="GitHub repo 'owner/name' that the Action commits runs/ into")
    src.add_argument("--dir", help="local/synced directory holding a run (…/runs/latest)")
    ap.add_argument("--ref", default="main")
    ap.add_argument("--run", default="latest", help="runs/<name> (default: latest)")
    ap.add_argument("--dest", default="~/digest_out/remote", help="where to put the run (default: ~/digest_out/remote)")
    a = ap.parse_args()

    dest = Path(a.dest).expanduser() / a.run
    if a.repo:
        run_dir = fetch_github(a.repo, a.ref, a.run, dest)
    else:
        run_dir = fetch_dir(Path(a.dir).expanduser(), dest)

    missing = [f for f in ("status.json", "skeleton.md", "items.json") if not (run_dir / f).exists()]
    if missing:
        sys.exit(f"run is incomplete, missing: {missing}")
    st = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
    print(f"run: {run_dir}")
    print(f"window: {st['window']['start']} .. {st['window']['end']}   generated: {st.get('generated')}")
    all_blocked = True
    for k, v in st["sources"].items():
        flag = "SKIP" if v.get("skipped") else ("BLOCKED " + str(v.get("error") or v.get("reason"))) if (v.get("error") or v.get("reason")) else \
               ("ok (partial: %s)" % v["partial"] if v.get("partial") else "ok")
        if flag.startswith("ok"):
            all_blocked = False
        print(f"  {k:13s} {flag:40s} items={v.get('items', 0)}")
    print(f"→ {run_dir / 'skeleton.md'}")
    return 2 if all_blocked else 0


if __name__ == "__main__":
    sys.exit(main())
