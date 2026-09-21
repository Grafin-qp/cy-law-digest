# cy-law-digest — collector runs for the Opiniq Cyprus law digest

The GitHub Action in `.github/workflows/digest.yml` runs `scripts/digest_collect.py`
every Monday 03:30 UTC (previous Monday–Sunday week) and commits the result to
`runs/<window>/` and `runs/latest/`. Claude reads it with
`scripts/fetch_run.py --repo <owner>/cy-law-digest` and writes the digest.

Setup (once):
1. Push this folder to a new GitHub repository (public is fine — it holds public law).
2. Settings → Actions → General → Workflow permissions → "Read and write permissions" → Save.
3. Actions → cyprus-law-digest → Run workflow → window `previous` (or `days:14`).
4. Check the run log ("Collect" step prints the source status table) and `runs/latest/`.

Manual windows: `previous` | `current` | `days:N` | `YYYY-MM-DD..YYYY-MM-DD`.
