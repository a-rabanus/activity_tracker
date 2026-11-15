"""Trial IDs and output file names: YYYYMMDD_Pxx_EVT-scenarioXX_Txx, e.g. 20261113_P01_EVT-scenario01_T01."""

import re
from datetime import date, datetime
from pathlib import Path

EXPERIMENT = "EVT"
SCENARIO_RE = re.compile(r"scenario\d{2}", re.ASCII)  # available scenarios = scenarios/scenarioXX.csv
TRIAL_ID_RE = re.compile(r"(\d{8})_P(\d{2})_" + EXPERIMENT + r"-(scenario\d{2})_T(\d{2})", re.ASCII)
MAX_NUMBER = 99


def parse_number(text: str, prefix: str, what: str) -> int:
    """Parse a person or trial number: `1`, `01` or with prefix (`P01`, `t1`). Returns 1..99."""
    t = text.strip()
    if t[:1].upper() == prefix:
        t = t[1:]
    if not re.fullmatch(r"\d{1,2}", t, re.ASCII) or not 1 <= int(t) <= MAX_NUMBER:
        raise ValueError(f"{what} muss eine Zahl von 1 bis {MAX_NUMBER} sein (z. B. 1 oder {prefix}01), nicht {text!r}")
    return int(t)


def build_trial_id(day: date, person: int, scenario: str, trial: int) -> str:
    if not SCENARIO_RE.fullmatch(scenario):
        raise ValueError(f"Ungültiges Szenario {scenario!r}, Format: scenarioXX (z. B. scenario01)")
    for value, what in ((person, "Personen-ID"), (trial, "Trial-Nummer")):
        if not 1 <= value <= MAX_NUMBER:
            raise ValueError(f"{what} muss zwischen 1 und {MAX_NUMBER} liegen")
    return f"{day:%Y%m%d}_P{person:02d}_{EXPERIMENT}-{scenario}_T{trial:02d}"


def parse_trial_id(text: str) -> tuple[date, int, str, int]:
    """Split a trial ID into (date, person, scenario, trial). Raises ValueError if it breaks the convention."""
    m = TRIAL_ID_RE.fullmatch(text.strip())
    if not m:
        raise ValueError(
            f"Ungültige Trial-ID {text!r}. Format: YYYYMMDD_Pxx_{EXPERIMENT}-scenarioXX_Txx, "
            f"z. B. 20261113_P01_{EXPERIMENT}-scenario01_T01"
        )
    day_s, person, scenario, trial = m.groups()
    try:
        day = datetime.strptime(day_s, "%Y%m%d").date()
    except ValueError:
        raise ValueError(f"Ungültiges Datum {day_s!r} in Trial-ID {text!r}") from None
    build_trial_id(day, int(person), scenario, int(trial))  # range checks
    return day, int(person), scenario, int(trial)


def subject_id(person: int) -> str:
    return f"P{person:02d}"


def output_paths(out_dir: Path, trial_id: str) -> tuple[Path, Path]:
    """(csv, sqlite) for a trial."""
    stem = Path(out_dir) / f"{trial_id}_labels"
    return stem.with_suffix(".csv"), stem.with_suffix(".sqlite")


def is_taken(out_dir: Path, trial_id: str) -> bool:
    return any(p.exists() for p in output_paths(out_dir, trial_id))


def next_free_trial(out_dir: Path, day: date, person: int, scenario: str, after: int = 0) -> int | None:
    """Smallest trial number above `after` whose files don't exist yet, or None."""
    for trial in range(after + 1, MAX_NUMBER + 1):
        if not is_taken(out_dir, build_trial_id(day, person, scenario, trial)):
            return trial
    return None
