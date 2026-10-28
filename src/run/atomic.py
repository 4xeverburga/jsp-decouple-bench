"""src/run/atomic.py — write-then-rename, so a reader never sees a partial
artifact and two concurrent runs never interleave inside one file."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def write_text(path: Path, text: str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return path


def write_json(path: Path, payload: object) -> Path:
    return write_text(
        path, json.dumps(payload, indent=2, sort_keys=False) + "\n"
    )
