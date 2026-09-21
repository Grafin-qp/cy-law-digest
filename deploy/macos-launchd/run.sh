#!/bin/bash
# Local alternative to GitHub Actions: run the collector on the Mac every Monday
# and drop the run into a folder that Cowork can read (a folder connected to the
# session, or one synced by Obsidian Sync / iCloud / OneDrive).
#
# Usage: edit SKILL_DIR and OUT_DIR, `chmod +x run.sh`, then load the plist:
#   cp com.opiniq.lawdigest.plist ~/Library/LaunchAgents/
#   launchctl load ~/Library/LaunchAgents/com.opiniq.lawdigest.plist
# Requirements on the Mac: python3 with requests/beautifulsoup4/lxml/pypdf
# (`pip3 install requests beautifulsoup4 lxml pypdf`) and poppler (`brew install poppler`).
set -euo pipefail
SKILL_DIR="$HOME/Skills/opiniq-law-digest"
OUT_DIR="$HOME/Documents/Opiniq/law-digest/runs"

mkdir -p "$OUT_DIR"
python3 "$SKILL_DIR/scripts/digest_collect.py" --week previous --out "$OUT_DIR" -v > "$OUT_DIR/collect.log" 2>&1
RUN_DIR=$(ls -d "$OUT_DIR"/*_* | sort | tail -1)
rm -rf "$RUN_DIR/raw"
rm -rf "$OUT_DIR/latest" && cp -R "$RUN_DIR" "$OUT_DIR/latest"
cp "$OUT_DIR/collect.log" "$OUT_DIR/latest/collect.log"
echo "done: $RUN_DIR"
