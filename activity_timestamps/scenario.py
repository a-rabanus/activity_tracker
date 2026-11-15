"""Scenarios: ordered steps (scenarios/Sxx.csv with step,label,hint) the operator is guided through."""

import csv
from dataclasses import dataclass
from pathlib import Path

from .generator import Label
from .naming import SCENARIOS

SYNC = "sync"  # step label for the guided sync sequence
COLUMNS = ["step", "label", "hint"]


@dataclass(frozen=True)
class Step:
    number: int
    label: str
    hint: str = ""

    def __str__(self):
        return f"{self.label} – {self.hint}" if self.hint else self.label


def list_scenarios(scenario_dir: Path) -> list[str]:
    """The SCENARIOS that have a step file `scenario_dir/Sxx.csv`."""
    return [s for s in SCENARIOS if (Path(scenario_dir) / f"{s}.csv").is_file()]


def load_scenario(path: Path, labels: list[Label]) -> list[Step]:
    """Read the steps, sorted by step number. Raises ValueError if a row doesn't fit the generator."""
    known = {l.label for l in labels}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = set(COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: Spalte(n) fehlen: {sorted(missing)}")
        steps: list[Step] = []
        for lineno, row in enumerate(reader, start=2):
            number, label = (row["step"] or "").strip(), (row["label"] or "").strip()
            if not number.isdecimal():
                raise ValueError(f"{path}:{lineno}: step muss eine Zahl sein, nicht {number!r}")
            if label != SYNC and label not in known:
                raise ValueError(f"{path}:{lineno}: {label!r} ist weder 'sync' noch ein Label aus generators.csv")
            steps.append(Step(int(number), label, (row["hint"] or "").strip()))
    numbers = [s.number for s in steps]
    if len(set(numbers)) != len(numbers):
        raise ValueError(f"{path}: doppelte step-Nummern")
    if not steps:
        raise ValueError(f"{path}: keine Schritte")
    return sorted(steps, key=lambda s: s.number)


class ScenarioProgress:
    """Which step of a scenario is current. Steps are advanced, skipped or stepped back by the app."""

    def __init__(self, name: str, steps: list[Step]):
        self.name = name
        self.steps = steps
        self.index = 0

    @property
    def current(self) -> Step | None:
        return self.steps[self.index] if self.index < len(self.steps) else None

    @property
    def upcoming(self) -> Step | None:
        return self.steps[self.index + 1] if self.index + 1 < len(self.steps) else None

    @property
    def finished(self) -> bool:
        return self.index >= len(self.steps)

    def advance(self) -> None:
        self.index = min(self.index + 1, len(self.steps))
