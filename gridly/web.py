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

USAGE = """usage: gridly-web [FILE] [--host HOST] [--port PORT]
       gridly-web --uploads [--host HOST] [--port PORT]

Serves Gridly at http://HOST:PORT. With no FILE, a browser session offers the
sheets opened lately, the same as running gridly with no file.

Listens on 127.0.0.1 by default. A browser session is a real Gridly process
with this machine's file access, so only widen that on a network you trust.

--uploads serves a page that asks for a sheet instead, and shows the one sent
read-only. Nothing on this machine is offered, and the copy is deleted a while
after the page is closed. Meant for a phone; put a password in front of it.
"""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "-h" in args or "--help" in args:
        print(USAGE)
        return 0

    host, port = "127.0.0.1", 8000
    uploads = False
    rest: list[str] = []
    while args:
        item = args.pop(0)
        if item == "--host" and args:
            host = args.pop(0)
        elif item == "--port" and args:
            port = int(args.pop(0))
        elif item == "--uploads":
            uploads = True
        else:
            rest.append(item)

    if uploads and rest:
        print("--uploads shows whatever the browser sends, so name no file.")
        return 1

    # With no file named, hand the app nothing and let it offer the sheets
    # opened lately, exactly as it does in a terminal.
    sheet = Path(rest[0]).expanduser().resolve() if rest else None
    if sheet is not None and not sheet.exists():
        print(f"No sheet at {sheet}. It will be created empty; ctrl+c if that is wrong.")

    try:
        from textual_serve.server import Server
    except ImportError:
        print("Serving needs textual-serve:  pip install 'gridly[web]'")
        return 1

    if uploads:
        from .uploads import UploadServer

        server = UploadServer(host=host, port=port)
    else:
        # Each browser session runs this. The path is resolved first, so a
        # session opens the sheet meant rather than whatever sits beside the
        # server's working directory.
        command = f"{shlex.quote(sys.executable)} -m gridly"
        if sheet is not None:
            command += f" {shlex.quote(str(sheet))}"
        server = Server(
            command=command,
            host=host,
            port=port,
            title=f"Gridly — {sheet.name}" if sheet else "Gridly",
        )
    try:
        server.serve()
    except OSError as error:
        if error.errno != errno.EADDRINUSE:
            raise
        # A page of traceback to say a port is busy helps nobody.
        named = f" {sheet.name}" if sheet else ""
        print(f"Port {port} is already busy. Try:  gridly-web{named} --port {port + 1}")
        return 1
    except KeyboardInterrupt:
        pass
    return 0
