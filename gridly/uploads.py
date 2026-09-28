"""Showing a sheet sent up from the browser, to look at and not to change.

For a phone, or anything else without the sheets on it: the page asks for a
file, the file comes up here, and a read-only Gridly shows it. Nothing else on
this machine is offered, and the copy is deleted a little after the session
ends — a little after, because a phone drops the connection whenever it
switches app, and coming back should not mean picking the file again.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import shlex
import shutil
import sys
import tempfile
from html import escape
from pathlib import Path
from typing import Any

import aiohttp_jinja2
import jinja2
from aiohttp import web
from textual_serve.app_service import AppService
from textual_serve.server import Server, to_int

log = logging.getLogger("textual-serve")

#: Larger than any sheet anyone types, small enough to turn junk away.
MAX_SIZE = 50 * 1024 * 1024

#: How long a copy outlives its last session.
GRACE = 30 * 60

#: The first bytes of every SQLite file, which is all a .gridly is.
SQLITE_HEADER = b"SQLite format 3\x00"


class UploadServer(Server):
    """A textual-serve server whose sessions each show one uploaded sheet."""

    def __init__(self, host: str, port: int) -> None:
        super().__init__(
            command=f"{shlex.quote(sys.executable)} -m gridly --read-only",
            host=host,
            port=port,
            title="Gridly",
        )
        self.inbox = Path(tempfile.mkdtemp(prefix="gridly-uploads-"))
        #: What each upload was called on the phone, by its token.
        self.names: dict[str, str] = {}
        #: How many sessions are showing each upload right now.
        self.watching: dict[str, int] = {}
        self._expiry: dict[str, asyncio.TimerHandle] = {}

    def sheet(self, token: str) -> Path | None:
        """Where an upload is kept, if the token names one still here."""
        if token not in self.names:
            return None  # also what stops a token reaching outside the inbox
        # Kept under the name it had, in a folder of its own, so the app shows
        # "groceries.gridly" rather than a token.
        path = self.inbox / token / self.names[token]
        return path if path.is_file() else None

    async def _make_app(self) -> web.Application:
        app = web.Application(client_max_size=MAX_SIZE)
        aiohttp_jinja2.setup(
            app, loader=jinja2.FileSystemLoader(self.templates_path)
        )
        app.add_routes(
            [
                web.get("/", self.handle_pick),
                web.post("/upload", self.handle_upload),
                web.get("/view/{token}", self.handle_view),
                web.get("/ws/{token}", self.handle_sheet_websocket),
                web.get("/download/{key}", self.handle_download),
                web.static("/static", self.statics_path, name="static"),
            ]
        )
        app.on_startup.append(self.on_startup)
        app.on_shutdown.append(self.on_shutdown)
        return app

    async def on_startup(self, app: web.Application) -> None:
        self.console.print(f"Showing uploaded sheets, read-only, on {self.public_url}")

    async def on_shutdown(self, app: web.Application) -> None:
        shutil.rmtree(self.inbox, ignore_errors=True)

    # ----------------------------------------------------------------- pages

    async def handle_pick(self, request: web.Request) -> web.Response:
        return web.Response(text=pick_page(), content_type="text/html")

    async def handle_upload(self, request: web.Request) -> web.Response:
        try:
            form = await request.post()
        except web.HTTPRequestEntityTooLarge:
            return refused("That file is too big to be a sheet.", 413)
        upload = form.get("sheet")
        if not isinstance(upload, web.FileField):
            return refused("No file came with that — pick one and try again.")
        body = upload.file.read()
        if not body.startswith(SQLITE_HEADER):
            return refused(f"{upload.filename} is not a Gridly sheet.")

        token = secrets.token_urlsafe(16)
        name = Path(upload.filename or "").name
        if name in ("", ".", ".."):
            name = "sheet.gridly"
        (self.inbox / token).mkdir()
        (self.inbox / token / name).write_bytes(body)
        self.names[token] = name
        # Gone after a while even if it is never opened.
        self._expire_later(token)
        raise web.HTTPSeeOther(f"/view/{token}")

    @aiohttp_jinja2.template("app_index.html")
    async def handle_view(self, request: web.Request) -> dict[str, Any]:
        token = request.match_info["token"]
        if self.sheet(token) is None:
            raise web.HTTPSeeOther("/")  # gone: pick it again
        # Built from the request rather than from the address this listens on,
        # which behind a proxy is not the one the browser used.
        secure = request.headers.get("X-Forwarded-Proto", request.scheme) == "https"
        return {
            "font_size": to_int(request.query.get("fontsize", "16"), 16),
            "app_websocket_url": f"{'wss' if secure else 'ws'}://{request.host}/ws/{token}",
            "config": {"static": {"url": "/static/"}},
            # Escaped by the template: the name is whatever the phone sent.
            "application": {"name": f"Gridly — {self.names[token]}"},
        }

    # --------------------------------------------------------------- session

    async def handle_sheet_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """Run a read-only Gridly on one upload, for as long as the page is open.

        textual-serve's own handler runs one command for every session; this
        is the same but for the sheet named in the address.
        """
        token = request.match_info["token"]
        websocket = web.WebSocketResponse(heartbeat=15)
        path = self.sheet(token)
        if path is None:
            await websocket.prepare(request)
            await websocket.close()
            return websocket

        self._watch(token)
        width = to_int(request.query.get("width", "80"), 80)
        height = to_int(request.query.get("height", "24"), 24)
        app_service: AppService | None = None
        try:
            await websocket.prepare(request)
            app_service = AppService(
                f"{self.command} {shlex.quote(str(path))}",
                write_bytes=websocket.send_bytes,
                write_str=websocket.send_str,
                close=websocket.close,
                download_manager=self.download_manager,
                debug=self.debug,
            )
            await app_service.start(width, height)
            try:
                await self._process_messages(websocket, app_service)
            finally:
                await app_service.stop()
        except asyncio.CancelledError:
            await websocket.close()
        except Exception as error:
            log.exception(error)
        finally:
            if app_service is not None:
                await app_service.stop()
            self._unwatch(token)
        return websocket

    # ----------------------------------------------------------- forgetting

    def _watch(self, token: str) -> None:
        self.watching[token] = self.watching.get(token, 0) + 1
        timer = self._expiry.pop(token, None)
        if timer is not None:
            timer.cancel()

    def _unwatch(self, token: str) -> None:
        self.watching[token] -= 1
        if not self.watching[token]:
            del self.watching[token]
            self._expire_later(token)

    def _expire_later(self, token: str) -> None:
        loop = asyncio.get_running_loop()
        self._expiry[token] = loop.call_later(GRACE, self.forget, token)

    def forget(self, token: str) -> None:
        """Delete an upload, unless someone has it open again."""
        self._expiry.pop(token, None)
        if token in self.watching:
            return
        self.names.pop(token, None)
        shutil.rmtree(self.inbox / token, ignore_errors=True)


def refused(why: str, status: int = 400) -> web.Response:
    return web.Response(text=pick_page(why), content_type="text/html", status=status)


def pick_page(problem: str = "") -> str:
    """The page that asks for a sheet. Picking one sends it straight away."""
    said = f'<p class="problem">{escape(problem)}</p>' if problem else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gridly</title>
<style>
  :root {{ --bg: #faf4ed; --fg: #575279; --dim: #797593; --accent: #d7827e; --bad: #b4637a; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg: #191724; --fg: #e0def4; --dim: #908caa; --accent: #ebbcba; --bad: #eb6f92; }}
  }}
  body {{ margin: 0; min-height: 100vh; display: grid; place-items: center;
         background: var(--bg); color: var(--fg);
         font: 17px/1.5 ui-monospace, "SF Mono", Menlo, monospace; }}
  main {{ padding: 24px 16px; max-width: 28rem; text-align: center; }}
  h1 {{ font-size: 1.6rem; margin: 0 0 .25rem; }}
  p {{ color: var(--dim); margin: 0 0 1.5rem; }}
  .problem {{ color: var(--bad); }}
  label {{ display: inline-block; padding: 14px 28px; border-radius: 10px;
          background: var(--accent); color: var(--bg); font-weight: 600; cursor: pointer; }}
  input {{ position: absolute; opacity: 0; width: 1px; height: 1px; }}
  form.sending label {{ opacity: .5; pointer-events: none; }}
</style>
</head>
<body>
<main>
  <h1>Gridly</h1>
  <p>Pick a .gridly file to look through. It is shown read-only, and not kept.</p>
  {said}
  <form method="post" action="/upload" enctype="multipart/form-data">
    <label>Open a sheet<input type="file" name="sheet"></label>
  </form>
</main>
<script>
  const form = document.querySelector("form");
  form.sheet.addEventListener("change", () => {{
    if (!form.sheet.files.length) return;
    form.classList.add("sending");
    form.querySelector("label").firstChild.textContent = "Opening…";
    form.submit();
  }});
</script>
</body>
</html>
"""
