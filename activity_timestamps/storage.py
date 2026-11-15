"""SQLite session store. Every write is committed immediately; CSV is an export."""

import csv
import sqlite3
from collections.abc import Callable, Sequence
from datetime import date, datetime
from pathlib import Path

from .generator import Label
from .relationships import Relationship

SCHEMA = """
CREATE TABLE IF NOT EXISTS session (
    trial_id       TEXT NOT NULL,
    subject        TEXT NOT NULL,
    reference_time TEXT NOT NULL,
    generator_path TEXT,
    created_at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS labels (
    label TEXT PRIMARY KEY,
    type  TEXT NOT NULL CHECK (type IN ('event', 'activity'))
);
CREATE TABLE IF NOT EXISTS annotations (
    id         INTEGER PRIMARY KEY,
    label      TEXT NOT NULL REFERENCES labels (label),
    start_time TEXT NOT NULL,
    start_s    REAL NOT NULL,
    end_time   TEXT,
    end_s      REAL
);
CREATE TABLE IF NOT EXISTS relationships (
    event    TEXT NOT NULL REFERENCES labels (label),
    action   TEXT NOT NULL CHECK (action IN ('start', 'stop')),
    activity TEXT NOT NULL REFERENCES labels (label)
);
CREATE TABLE IF NOT EXISTS skipped_steps (
    id       INTEGER PRIMARY KEY,
    scenario TEXT NOT NULL,
    step     INTEGER NOT NULL,
    label    TEXT NOT NULL,
    time     TEXT NOT NULL,
    t_s      REAL NOT NULL
);
"""

CSV_COLUMNS = ["trial_id", "subject", "label", "type", "start_s", "end_s", "duration_s", "start_time", "end_time"]


def parse_reference(text: str, today: date) -> datetime:
    """Parse the sensor start time: `HH:MM`, `HH:MM:SS` (today) or full ISO datetime."""
    text = text.strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.combine(today, datetime.strptime(text, fmt).time())
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        raise ValueError(f"cannot parse start time {text!r}, use HH:MM[:SS] or ISO") from None


class Session:
    def __init__(
        self,
        db_path: str | Path,
        labels: list[Label],
        reference: datetime,
        subject: str,
        generator_path: str | Path | None = None,
        relationships: Sequence[Relationship] = (),
        clock: Callable[[], datetime] = datetime.now,
        trial_id: str = "",
    ):
        self.reference = reference
        self.subject = subject
        self.trial_id = trial_id
        self.clock = clock
        self.types = {l.label: l.type for l in labels}

        self.db = sqlite3.connect(db_path)
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA)
        self.db.executemany(
            "INSERT OR IGNORE INTO labels (label, type) VALUES (?, ?)",
            [(l.label, l.type) for l in labels],
        )
        self.db.execute(
            "INSERT INTO session (trial_id, subject, reference_time, generator_path, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (trial_id, subject, reference.isoformat(), str(generator_path or ""), clock().isoformat()),
        )
        self.db.executemany(
            "INSERT INTO relationships (event, action, activity) VALUES (?, ?, ?)",
            [(r.event, r.action, r.activity) for r in relationships],
        )
        self.db.commit()

    def elapsed(self) -> float:
        return self._rel(self.clock())

    def _rel(self, t: datetime) -> float:
        return round((t - self.reference).total_seconds(), 3)

    def _check(self, label: str, expected: str) -> None:
        if label not in self.types:
            raise KeyError(f"unknown label {label!r}")
        if self.types[label] != expected:
            raise ValueError(f"{label!r} is an {self.types[label]}, not an {expected}")

    def _insert(self, label: str, at: datetime | None) -> int:
        now = at or self.clock()
        cur = self.db.execute(
            "INSERT INTO annotations (label, start_time, start_s) VALUES (?, ?, ?)",
            (label, now.isoformat(), self._rel(now)),
        )
        self.db.commit()
        return cur.lastrowid

    def log_event(self, label: str, at: datetime | None = None) -> int:
        self._check(label, "event")
        return self._insert(label, at)

    def start_activity(self, label: str, at: datetime | None = None) -> int:
        self._check(label, "activity")
        return self._insert(label, at)

    def stop_activity(self, annotation_id: int, at: datetime | None = None) -> None:
        now = at or self.clock()
        cur = self.db.execute(
            "UPDATE annotations SET end_time = ?, end_s = ? WHERE id = ? AND end_time IS NULL",
            (now.isoformat(), self._rel(now), annotation_id),
        )
        if cur.rowcount != 1:
            raise KeyError(f"no running activity with id {annotation_id}")
        self.db.commit()

    def reopen(self, annotation_id: int) -> None:
        """Clear the end of a stopped activity (undo of a stop)."""
        self.db.execute("UPDATE annotations SET end_time = NULL, end_s = NULL WHERE id = ?", (annotation_id,))
        self.db.commit()

    def delete(self, annotation_id: int) -> None:
        self.db.execute("DELETE FROM annotations WHERE id = ?", (annotation_id,))
        self.db.commit()

    def get(self, annotation_id: int) -> tuple | None:
        """Return (label, start_s, end_s) for one annotation."""
        return self.db.execute(
            "SELECT label, start_s, end_s FROM annotations WHERE id = ?", (annotation_id,)
        ).fetchone()

    def log_skipped(self, scenario: str, step: int, label: str) -> int:
        now = self.clock()
        cur = self.db.execute(
            "INSERT INTO skipped_steps (scenario, step, label, time, t_s) VALUES (?, ?, ?, ?, ?)",
            (scenario, step, label, now.isoformat(), self._rel(now)),
        )
        self.db.commit()
        return cur.lastrowid

    def delete_skipped(self, skipped_id: int) -> None:
        self.db.execute("DELETE FROM skipped_steps WHERE id = ?", (skipped_id,))
        self.db.commit()

    def skipped(self) -> list[tuple[float, int, str]]:
        """(t_s, step, label) of skipped scenario steps."""
        return self.db.execute("SELECT t_s, step, label FROM skipped_steps ORDER BY t_s, id").fetchall()

    def rows(self) -> list[dict]:
        cur = self.db.execute(
            """SELECT a.label, l.type, a.start_s, a.end_s, a.start_time, a.end_time
               FROM annotations a JOIN labels l USING (label)
               ORDER BY a.start_s, a.id"""
        )
        out = []
        for label, kind, start_s, end_s, start_time, end_time in cur:
            out.append({
                "trial_id": self.trial_id,
                "subject": self.subject,
                "label": label,
                "type": kind,
                "start_s": start_s,
                "end_s": end_s,
                "duration_s": round(end_s - start_s, 3) if end_s is not None else None,
                "start_time": start_time,
                "end_time": end_time,
            })
        return out

    def export_csv(self, path: str | Path) -> Path:
        path = Path(path)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(self.rows())
        return path

    def close(self) -> None:
        self.db.close()
