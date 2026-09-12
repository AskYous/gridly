"""User preferences that outlive a single run."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

def path() -> Path:
    """Where the settings live.

    Worked out each time rather than once at import, so that pointing
    XDG_CONFIG_HOME somewhere else actually takes effect.
    """
    return (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        / "gridly"
        / "config.json"
    )


def load() -> dict[str, Any]:
    """Read the config, treating a missing or corrupt file as empty."""
    try:
        data = json.loads(path().read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save(**values: Any) -> None:
    """Merge values into the config. Failure to write is not worth crashing over."""
    data = load() | values
    try:
        target = path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=2) + "\n")
    except OSError:
        pass


RECENT_LIMIT = 15


def remember(path: Path) -> None:
    """Put a sheet at the top of the recent list."""
    resolved = str(Path(path).expanduser().resolve())
    keep = [p for p in load().get("recent", []) if p != resolved]
    save(recent=[resolved] + keep[: RECENT_LIMIT - 1])


def recent() -> list[Path]:
    """Recently opened sheets, newest first, skipping any that have gone."""
    seen = load().get("recent", [])
    if not isinstance(seen, list):
        return []
    return [Path(p) for p in seen if isinstance(p, str) and Path(p).is_file()]
