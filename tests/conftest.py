"""Shared setup. Imported by pytest before any test module.

Two things every test needs: a config file that is not the user's own, and a
clipboard that is not the machine's. Both used to be set up per file, which
stopped working once the tests shared a process — whichever file was imported
last won.
"""

import os
import tempfile

os.environ.setdefault("XDG_CONFIG_HOME", tempfile.mkdtemp())

import gridly.app

#: What the last copy would have put on the system clipboard.
gridly.app.last_system_clipboard = None


def _remember(text: str) -> bool:
    gridly.app.last_system_clipboard = text
    return True


gridly.app.to_system_clipboard = _remember
