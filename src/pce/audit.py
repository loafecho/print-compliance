"""Append-only JSONL audit log: one line per scanned file."""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path


def append_record(path: str | Path, record: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = dict(record)
    rec.setdefault("timestamp", _dt.datetime.now(_dt.timezone.utc).isoformat())
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
