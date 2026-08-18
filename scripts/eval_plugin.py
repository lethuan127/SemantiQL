"""Score the shipped skill with PluginEval and gate on both layers.

    uv run python scripts/eval_plugin.py
    uv run python scripts/eval_plugin.py --runs 5 --judge-min 0.80

**Not part of `scripts/verify.sh`, deliberately.** It needs a third-party plugin installed and makes
LLM calls, so putting it in the gate would break CI and every contributor who has not installed it,
and would spend money on every commit. The constitution's rule about CI staying secret-free and
dependency-light is the reason.

**Why it samples rather than runs once.** The static layer is deterministic — it returned exactly
0.9564 on every run while this was being written. The judge layer is an LLM and it is *noisy*: on
identical content it produced judge scores from 0.667 to 0.895, and `output_quality` alone swung
from 0.40 to 0.83. A single sample is not a measurement, so this reports the median and the
spread. Gating on one run would be a coin toss — worse than no gate, because it looks like one.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "plugin" / "skills" / "semantiql"
DEFAULT_EVAL_HOME = Path.home() / ".claude/plugins/cache/claude-code-workflows/plugin-eval/0.1.1"

INSTALL_HINT = """skipped: PluginEval is not installed. Install it with

  claude plugin marketplace add wshobson/agents
  claude plugin install plugin-eval@claude-code-workflows

then re-run. Set EVAL_HOME if your installed version differs from the default path."""


def _score_once(eval_home: Path) -> tuple[float, float] | None:
    """One run, returning (static, judge) or None if the tool produced nothing usable."""
    done = subprocess.run(
        [
            "uv",
            "run",
            "--quiet",
            "--extra",
            "llm",
            "plugin-eval",
            "score",
            str(SKILL),
            "--depth",
            "standard",
            "--output",
            "json",
        ],
        cwd=eval_home,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    try:
        payload = json.loads(done.stdout)
    except json.JSONDecodeError:
        print(f"  (a run produced no JSON; exit {done.returncode})", file=sys.stderr)
        return None
    by_layer = {layer["layer"]: layer["score"] for layer in payload["layers"]}
    return by_layer.get("static", 0.0), by_layer.get("judge", 0.0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3, help="judge samples to take (default: 3)")
    parser.add_argument("--static-min", type=float, default=0.95)
    parser.add_argument("--judge-min", type=float, default=0.90)
    args = parser.parse_args()

    eval_home = Path(os.environ.get("EVAL_HOME", DEFAULT_EVAL_HOME))
    if not eval_home.is_dir():
        print(INSTALL_HINT)
        return 0

    print(f"scoring {SKILL.relative_to(REPO)}")
    print(
        print(
            f"thresholds: static >= {args.static_min}, "
            f"judge >= {args.judge_min}, over {args.runs} runs\n"
        )
    )

    results = [r for r in (_score_once(eval_home) for _ in range(args.runs)) if r]
    if not results:
        print("no results — is PluginEval installed and authenticated?", file=sys.stderr)
        return 2

    for index, (static, judge) in enumerate(results, start=1):
        print(f"  run {index}:  static {static:.4f}   judge {judge:.4f}")

    statics = [r[0] for r in results]
    judges = [r[1] for r in results]
    print(
        f"\nstatic  median {statistics.median(statics):.4f}"
        f"   range {min(statics):.4f}-{max(statics):.4f}"
    )
    print(
        f"judge   median {statistics.median(judges):.4f}"
        f"   range {min(judges):.4f}-{max(judges):.4f}"
    )

    failures = []
    if statistics.median(statics) < args.static_min:
        failures.append(f"static {statistics.median(statics):.4f} < {args.static_min}")
    if statistics.median(judges) < args.judge_min:
        failures.append(f"judge {statistics.median(judges):.4f} < {args.judge_min}")

    if failures:
        print("\nBELOW THRESHOLD: " + "; ".join(failures))
        print(
            "The judge is capped at 0.9375 while one skill covers both asking and model-building:\n"
            "`scope_calibration` scores 0.75 by rubric, in every run, because the rubric's 1.0 is\n"
            "'minimal surface area, maximum cohesion'. See plugin/README.md."
        )
        return 1

    print("\nboth layers at or above threshold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
