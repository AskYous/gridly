"""The upload server: what it takes, what it turns away, and when it forgets."""

import asyncio
import re

import pytest
from aiohttp import FormData, WSMsgType
from aiohttp.test_utils import TestClient, TestServer

from gridly.store import Sheet
from gridly.uploads import UploadServer


@pytest.fixture
def sheet_bytes(tmp_path):
    path = tmp_path / "groceries.gridly"
    sheet = Sheet(path)
    sheet.set_cell(sheet.rows()[0].id, sheet.columns()[0].id, "Milk")
    sheet.close()
    return path.read_bytes()


def send(body: bytes, name: str = "groceries.gridly") -> FormData:
    form = FormData()
    form.add_field("sheet", body, filename=name)
    return form


async def serving(check):
    """Run `check(client, server)` against a live upload server."""
    server = UploadServer(host="127.0.0.1", port=0)
    client = TestClient(TestServer(await server._make_app()))
    await client.start_server()
    try:
        await check(client, server)
    finally:
        await client.close()


async def upload(client, body, name="groceries.gridly") -> str:
    """Send a sheet, and return the token it was given."""
    response = await client.post("/upload", data=send(body, name), allow_redirects=False)
    assert response.status == 303
    return re.fullmatch(r"/view/([\w-]+)", response.headers["Location"]).group(1)


def test_the_front_page_asks_for_a_file():
    async def check(client, server):
        response = await client.get("/")
        page = await response.text()
        assert response.status == 200
        assert 'type="file"' in page and 'action="/upload"' in page

    asyncio.run(serving(check))


def test_a_sheet_is_kept_and_shown_by_its_own_address(sheet_bytes):
    async def check(client, server):
        token = await upload(client, sheet_bytes)
        assert server.sheet(token).read_bytes() == sheet_bytes
        page = await (await client.get(f"/view/{token}")).text()
        assert f"/ws/{token}" in page
        assert "groceries.gridly" in page

    asyncio.run(serving(check))


def test_behind_https_the_socket_is_secure_too(sheet_bytes):
    """CapRover ends HTTPS and passes plain HTTP on; the page must still say wss."""
    async def check(client, server):
        token = await upload(client, sheet_bytes)
        response = await client.get(
            f"/view/{token}", headers={"X-Forwarded-Proto": "https"}
        )
        assert f"wss://" in await response.text()

    asyncio.run(serving(check))


def test_something_that_is_not_a_sheet_is_turned_away():
    async def check(client, server):
        response = await client.post("/upload", data=send(b"just some words", "notes.txt"))
        assert response.status == 400
        assert "not a Gridly sheet" in await response.text()
        assert not list(server.inbox.iterdir())

    asyncio.run(serving(check))


def test_a_post_without_a_file_is_turned_away():
    async def check(client, server):
        response = await client.post("/upload", data={"sheet": "text"})
        assert response.status == 400

    asyncio.run(serving(check))


def test_an_unknown_or_crafted_address_goes_back_to_the_picker():
    async def check(client, server):
        for token in ["nope", "..%2F..%2Fetc%2Fpasswd", "%2E%2E"]:
            # Redirected, or normalised to the front page before it gets here.
            response = await client.get(f"/view/{token}")
            assert 'type="file"' in await response.text()
        assert server.sheet("../../etc/passwd") is None

    asyncio.run(serving(check))


def test_the_uploaded_name_cannot_reach_outside_the_inbox(sheet_bytes):
    async def check(client, server):
        token = await upload(client, sheet_bytes, name="../../escape.gridly")
        assert server.sheet(token).parent.parent == server.inbox
        assert "/" not in server.names[token]

    asyncio.run(serving(check))


def test_the_name_shown_cannot_add_to_the_page(sheet_bytes):
    async def check(client, server):
        token = await upload(client, sheet_bytes)
        # Set directly: the test client encodes a name, but a browser need not.
        kept = server.sheet(token)
        server.names[token] = "<b>x.gridly"
        kept.rename(kept.with_name("<b>x.gridly"))
        page = await (await client.get(f"/view/{token}")).text()
        assert "<b>x" not in page and "&lt;b&gt;x" in page

    asyncio.run(serving(check))


def test_a_session_shows_the_sheet_and_the_copy_goes_after(sheet_bytes):
    async def check(client, server):
        token = await upload(client, sheet_bytes)
        seen = b""
        async with client.ws_connect(f"/ws/{token}?width=80&height=24") as socket:
            assert server.watching == {token: 1}
            # Until the grid is drawn, or give up after a while.
            for _ in range(200):
                message = await asyncio.wait_for(socket.receive(), 20)
                if message.type != WSMsgType.BINARY:
                    continue
                seen += message.data
                if b"Milk" in seen:
                    break
        assert b"Milk" in seen and b"read-only" in seen
        assert b"groceries.gridly" in seen, "shown by its own name, not the token"

        for _ in range(100):  # the server notices the socket close
            if not server.watching:
                break
            await asyncio.sleep(0.05)
        assert not server.watching
        # Kept for a while, in case the phone comes back...
        assert server.sheet(token) is not None
        # ...and gone once that runs out.
        server.forget(token)
        assert server.sheet(token) is None
        assert not list(server.inbox.iterdir())
        response = await client.get(f"/view/{token}", allow_redirects=False)
        assert response.headers["Location"] == "/"

    asyncio.run(serving(check))


def test_a_copy_being_looked_at_is_not_deleted(sheet_bytes):
    async def check(client, server):
        token = await upload(client, sheet_bytes)
        server._watch(token)
        server.forget(token)
        assert server.sheet(token) is not None
        server._unwatch(token)

    asyncio.run(serving(check))
