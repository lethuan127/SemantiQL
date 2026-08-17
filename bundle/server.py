"""Entry point for the Claude Desktop bundle (spec 014).

Deliberately three lines of logic. Everything that could be wrong — which model, which adapter,
which credentials — is decided by `semantiql.cli`, which the ordinary test suite covers. Putting
that branching here instead would put it in the one file no test exercises, because only a real
bundle install runs it.

Configuration arrives as environment variables. The host substitutes the answers from its install
dialog into them, so `SEMANTIQL_MODEL` holds whatever the user picked in the file browser.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from semantiql.cli import main  # noqa: E402  — after the path insert, by necessity

if __name__ == "__main__":
    raise SystemExit(main(["serve"]))
