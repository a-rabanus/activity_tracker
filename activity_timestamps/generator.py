"""Load the generators.csv that defines which labels (and UI buttons) exist."""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

TYPES = ("event", "activity")


@dataclass(frozen=True)
class Label:
    label: str
    type: Literal["event", "activity"]


def load_generator(path: str | Path) -> list[Label]:
    """Read `label,type` rows. File order is kept and used as button order."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = {"label", "type"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing column(s) {sorted(missing)}")

        labels: list[Label] = []
        seen: set[str] = set()
        for lineno, row in enumerate(reader, start=2):
            name = (row["label"] or "").strip()
            kind = (row["type"] or "").strip().lower()
            if not name:
                raise ValueError(f"{path}:{lineno}: empty label")
            if kind not in TYPES:
                raise ValueError(f"{path}:{lineno}: type must be one of {TYPES}, got {kind!r}")
            if name in seen:
                raise ValueError(f"{path}:{lineno}: duplicate label {name!r}")
            seen.add(name)
            labels.append(Label(name, kind))
    return labels
