"""Lets the package run as `python -m semantiql`.

Exists so `serve --print-config` can name an interpreter it is certain about. `sys.executable`
is always an absolute path to the running interpreter, whereas a console script's location
depends on how the project was installed and whether the client's PATH matches the shell's —
and Claude Desktop launches the server with neither the user's shell nor their PATH.
"""

from semantiql.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
