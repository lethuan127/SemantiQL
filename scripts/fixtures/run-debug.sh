#!/usr/bin/env bash
# Launch a discovery run with full debug logging into logs/.
#
#   ./run-debug.sh                 interactive, in tmux (session: sqdbg)
#   ./run-debug.sh -p              headless, one shot
#
# Two logs per run, because they answer different questions:
#   logs/<stamp>-debug.log    Claude's own debug channel — API calls, hooks, tool routing
#   logs/<stamp>-stream.jsonl every tool call and result, which is what shows *which commands
#                             the agent actually ran* (this is how the psql-instead-of-SemantiQL
#                             finding was established, after the fact, from a transcript)
set -euo pipefail

# The repository root, then the ignored workspace inside it. This script lives in scripts/fixtures/
# now; its logs must still land in .test-workspace/, which is the only place they are git-ignored.
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
HERE="$REPO/.test-workspace"
mkdir -p "$HERE/logs"
STAMP="$(date +%Y%m%d-%H%M%S)"
DEBUG_LOG="$HERE/logs/$STAMP-debug.log"
STREAM_LOG="$HERE/logs/$STAMP-stream.jsonl"

export SEMANTIQL_HOME="${SEMANTIQL_HOME:-$REPO}"
export PGHOST=${PGHOST:-127.0.0.1} PGPORT=${PGPORT:-55432}
export PGUSER=${PGUSER:-postgres} PGPASSWORD=${PGPASSWORD:-postgres}
export PGDATABASE=${PGDATABASE:-semantiql_nyc}

TOOLS=(Bash Read Write Edit Glob Grep Skill)

if [[ "${1:-}" == "-p" ]]; then
  echo "headless run → $STREAM_LOG"
  claude -p "$(cat "$HERE/run/prompt.txt")" \
    --allowedTools "${TOOLS[@]}" \
    --debug-file "$DEBUG_LOG" \
    --output-format stream-json --verbose > "$STREAM_LOG"
else
  tmux kill-session -t sqdbg 2>/dev/null || true
  tmux new-session -d -s sqdbg -x 210 -y 50 -c "$HERE"
  for v in SEMANTIQL_HOME PGHOST PGPORT PGUSER PGPASSWORD PGDATABASE; do
    tmux send-keys -t sqdbg "export $v=${!v}" Enter
  done
  tmux send-keys -t sqdbg "clear" Enter
  tmux send-keys -t sqdbg "claude --debug --debug-file '$DEBUG_LOG' --allowedTools ${TOOLS[*]}" Enter
  echo "session: tmux attach -t sqdbg"
  echo "debug:   $DEBUG_LOG"
  echo "prompt:  $HERE/run/prompt.txt"
fi
