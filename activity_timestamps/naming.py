"""Trial IDs and output file names: YYYYMMDD_Pxx_Sxx_SCxx, e.g. 20261115_P03_S01_SC02.

P = person, S = session, SC = scenario. The trial ID must match the one the sensor recording script
prints, so the label and sensor data can be merged.
"""

import re
from datetime import date, datetime
from pathlib import Path

SCENARIOS = ["SC01", "SC02"]  # must stay identical to the sensor repo; add new scenarios here
TRIAL_ID_RE = re.compile(r"^(\d{8})_P(\d{2})_S(\d{2})_(SC\d{2})$", re.ASCII)
MAX_NUMBER = 99


def parse_number(text: str, prefix: str, what: str) -> int:
    """Parse a two-digit ID number: `3`, `03` or with prefix (`P3`, `p03`, `SC2`). Returns 1..99."""
    t = text.strip()
    if t[: len(prefix)].upper() == prefix:
        t = t[len(prefix) :]
    if not re.fullmatch(r"\d{1,2}", t, re.ASCII) or not 1 <= int(t) <= MAX_NUMBER:
        raise ValueError(f"{what} muss eine Zahl von 1 bis {MAX_NUMBER} sein (z. B. 3 oder {prefix}03), nicht {text!r}")
    return int(t)


def parse_person(text: str) -> int:
    """`3`, `03`, `P3`, `p03` -> 3."""
    return parse_number(text, "P", "Personen-ID")


def parse_session(text: str) -> int:
    """`1`, `01`, `S1`, `s01` -> 1."""
    return parse_number(text, "S", "Session")


def parse_scenario(text: str) -> str:
    """`2`, `02`, `SC2`, `sc02` -> `SC02`. Must be in SCENARIOS."""
    scenario = f"SC{parse_number(text, 'SC', 'Szenario'):02d}"
    if scenario not in SCENARIOS:
        raise ValueError(f"Unbekanntes Szenario {scenario}, erlaubt: {', '.join(SCENARIOS)}")
    return scenario


def build_trial_id(day: date, person: int | str, session: int | str, scenario: int | str) -> str:
    """The one place a trial ID is made. Parts may be given loosely (3, "3", "P03"; 1, "S01"; 2, "SC02")."""
    p = parse_person(str(person))
    s = parse_session(str(session))
    sc = parse_scenario(str(scenario))
    return f"{day:%Y%m%d}_P{p:02d}_S{s:02d}_{sc}"


def parse_trial_id(text: str) -> tuple[date, int, int, str]:
    """Split a trial ID into (date, person, session, scenario). Raises ValueError if it breaks the convention."""
    m = TRIAL_ID_RE.match(text.strip())
    if not m:
        raise ValueError(f"Ungültige Trial-ID {text!r}. Format: YYYYMMDD_Pxx_Sxx_SCxx, z. B. 20261115_P03_S01_SC02")
    day_s, person, session, scenario = m.groups()
    try:
        day = datetime.strptime(day_s, "%Y%m%d").date()
    except ValueError:
        raise ValueError(f"Ungültiges Datum {day_s!r} in Trial-ID {text!r}") from None
    return day, parse_person(person), parse_session(session), parse_scenario(scenario)


def subject_id(person: int) -> str:
    return f"P{person:02d}"


def output_paths(out_dir: Path, trial_id: str) -> tuple[Path, Path]:
    """(csv, sqlite) for a trial: <Trial-ID>_labels.csv / .sqlite."""
    stem = Path(out_dir) / f"{trial_id}_labels"
    return stem.with_suffix(".csv"), stem.with_suffix(".sqlite")


def is_taken(out_dir: Path, trial_id: str) -> bool:
    return any(p.exists() for p in output_paths(out_dir, trial_id))
