"""Serving Gridly to a browser.

The app itself is unchanged: textual-serve runs it as a real process on this
machine and streams the terminal to the page. Anyone who can reach the port
gets a Gridly with the file access this machine has, so it listens only on
localhost unless told otherwise.
"""

from __future__ import annotations

import errno
import shlex
import sys
from pathlib import Path

from .app import DEFAULT_FILE

USAGE = """usage: gridly-web [FILE] [--host HOST] [--port PORT]

Serves Gridly at http://HOST:PORT. FILE defaults to ./{default}.

Listens on 127.0.0.1 by default. A browser session is a real Gridly process
with this machine's file access, so only widen that on a network you trust.
"""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "-h" in args or "--help" in args:
        print(USAGE.format(default=DEFAULT_FILE))
        return 0

    host, port = "127.0.0.1", 8000
    rest: list[str] = []
    while args:
        item = args.pop(0)
        if item == "--host" and args:
            host = args.pop(0)
        elif item == "--port" and args:
            port = int(args.pop(0))
        else:
            rest.append(item)

    sheet = Path(rest[0] if rest else DEFAULT_FILE).expanduser().resolve()
    if rest and not sheet.exists():
        print(f"No sheet at {sheet}. It will be created empty; ctrl+c if that is wrong.")

    try:
        from textual_serve.server import Server
    except ImportError:
        print("Serving needs textual-serve:  pip install 'gridly[web]'")
        return 1

    # Each browser session runs this, so the path is fixed rather than left to
    # whatever directory the server happens to be started from.
    server = Server(
        command=f"{shlex.quote(sys.executable)} -m gridly {shlex.quote(str(sheet))}",
        host=host,
        port=port,
        title=f"Gridly — {sheet.name}",
    )
    try:
        server.serve()
    except OSError as error:
        if error.errno != errno.EADDRINUSE:
            raise
        # A page of traceback to say a port is busy helps nobody.
        print(f"Port {port} is already busy. Try:  gridly-web {sheet.name} --port {port + 1}")
        return 1
    except KeyboardInterrupt:
        pass
    return 0
