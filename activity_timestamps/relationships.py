"""Links from events to activities, e.g. sit_down starts sitting and stand_up stops it."""

import csv
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from .generator import Label

ACTIONS = ("start", "stop")
COLUMNS = ["event", "action", "activity"]


@dataclass(frozen=True)
class Relationship:
    event: str
    action: Literal["start", "stop"]
    activity: str

    def __str__(self):
        return f"{self.event} -> {self.action} {self.activity}"


def validate(relationships: list[Relationship], labels: list[Label]) -> None:
    """Raise ValueError if a link doesn't fit the generator labels."""
    types = {l.label: l.type for l in labels}
    seen: set[tuple[str, str]] = set()
    for r in relationships:
        if types.get(r.event) != "event":
            raise ValueError(f"{r}: {r.event!r} is not an event in the generator")
        if types.get(r.activity) != "activity":
            raise ValueError(f"{r}: {r.activity!r} is not an activity in the generator")
        if r.action not in ACTIONS:
            raise ValueError(f"{r}: action must be one of {ACTIONS}")
        if (r.event, r.activity) in seen:
            raise ValueError(f"{r}: {r.event!r} is linked to {r.activity!r} twice")
        seen.add((r.event, r.activity))


def load_relationships(path: str | Path, labels: list[Label]) -> list[Relationship]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = set(COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing column(s) {sorted(missing)}")
        relationships = [
            Relationship(
                (row["event"] or "").strip(),
                (row["action"] or "").strip().lower(),
                (row["activity"] or "").strip(),
            )
            for row in reader
        ]
    try:
        validate(relationships, labels)
    except ValueError as e:
        raise ValueError(f"{path}: {e}") from None
    return relationships


def save_relationships(path: str | Path, relationships: list[Relationship]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(asdict(r) for r in relationships)
