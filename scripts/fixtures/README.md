# Fixture and harness scripts

**Committed on purpose.** These used to live in `.test-workspace/`, which is git-ignored, so a fresh
clone had none of them — while each one's docstring claimed the script was the artefact and the data
was output (spec 022). Code lives here; output still lands in `.test-workspace/`.

Setup for the tools these need is in
[`../../docs/12-development-environment.md`](../../docs/12-development-environment.md).

| Script | What it does |
|---|---|
| `build.py` | builds a 5-row DuckDB fixture and **asserts its own documented totals** |
| `seed.sql` | the same fixture on Postgres, with `ASSERT`s so a mis-seed is loud |
| `fetch.py` | 2.96M real NYC taxi trips, plus a computed answer key |
| `fetch_retail.py` | 1,067,371 real UK retail invoice lines (CC BY 4.0), plus an answer key |
| `fetch_salt.py` | SAP SALT ERP data — blocked on dataset access; reads its token from `.env` itself |
| `judge.py` | grades a discovery-run transcript: **rules in code, rubric by LLM** |
| `run-debug.sh` | launches a run with debug logging into `.test-workspace/logs/` |

Order, from nothing:

```bash
docker compose up -d --wait                        # from the repo root
uv run python scripts/fixtures/fetch_retail.py     # the fixture the evals are written against
./scripts/fixtures/run-debug.sh                    # then paste a prompt in the tmux session
uv run python scripts/fixtures/judge.py .test-workspace/logs/<stamp>-stream.jsonl
```

**Answer keys are the examiner's copy.** They land in `.test-workspace/examiner/`, and they must stay
out of any directory a run under evaluation can read — otherwise the exercise stops being "does it ask
a human what these columns mean" and becomes reading comprehension.
