"""Tkinter window for the operator: one button per event, one toggle per activity."""

if __name__ == "__main__" and not __package__:
    # Started directly (e.g. "Run Python File" on app.py): run the package like `python -m activity_timestamps`.
    import os
    import runpy
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))
    os.chdir(project_root)  # generators.csv, relationships.csv and data/ live here
    runpy.run_module("activity_timestamps", run_name="__main__", alter_sys=True)
    sys.exit()

import math
import time
import tkinter as tk
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from tkinter import messagebox, ttk

from .generator import Label
from .naming import SCENARIOS, build_trial_id, is_taken, parse_person, parse_session
from .recorder import Press, Recorder
from .relationships import ACTIONS, Relationship, load_relationships, save_relationships
from .scenario import SYNC, ScenarioProgress, Step, list_scenarios, load_scenario
from .storage import parse_reference

RUNNING_BG = "#d9534f"
FLIP_BG = "#f0ad4e"
CURRENT_BG = "#5cb85c"  # button of the current scenario step
NOTICE_MS = 4000  # how long the "unexpected label" notice stays
ACTIVITY_COLUMNS = 3  # activity buttons per row

SYNC_REST_S = 20  # seconds the sensor box lies still before each flip
SYNC_FLIP = "sync_flip"  # first flip: z positive -> z negative
SYNC_FLIP_BACK = "sync_flip_back"  # second flip: z negative -> z positive
SYNC_LABELS = (SYNC_FLIP, SYNC_FLIP_BACK)


def fmt_offset(seconds: float) -> str:
    sign = "-" if seconds < 0 else "+"
    h, rem = divmod(abs(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{sign}{int(h):02d}:{int(m):02d}:{s:04.1f}"


def _run_modal(root: tk.Tk, dialog: tk.Toplevel) -> None:
    dialog.wait_visibility()
    dialog.grab_set()
    root.wait_window(dialog)


def ask_session_info(
    root: tk.Tk,
    out_dir: Path,
    day: date,
    scenario_dir: Path,
    labels: list[Label],
    person: int | None = None,
    session: int | None = None,
    scenario: str | None = None,
    default_start: str | None = None,
) -> tuple[datetime, str, int, ScenarioProgress] | None:
    """Modal dialog for person ID, session, scenario and sensor start time. The trial ID is built from them.

    The scenario dropdown lists the SCENARIOS that have a scenario_dir/SCxx.csv. Returns
    (reference, trial_id, person, scenario progress), or None if cancelled.
    """
    scenarios = list_scenarios(scenario_dir)
    dialog = tk.Toplevel(root)
    dialog.title("Neue Aufnahme")
    dialog.resizable(False, False)
    frame = ttk.Frame(dialog, padding=12)
    frame.pack()

    person_var = tk.StringVar(value=f"{person:02d}" if person else "")
    session_var = tk.StringVar(value=f"{session:02d}" if session else "")
    scenario_var = tk.StringVar(value=scenario if scenario in scenarios else (scenarios or [""])[0])
    start_var = tk.StringVar(value=default_start or datetime.now().strftime("%H:%M:%S"))
    preview_var = tk.StringVar()
    error_var = tk.StringVar()
    result: list[tuple[datetime, str, int, ScenarioProgress]] = []

    ttk.Label(frame, text=f"Datum: {day:%Y%m%d} (automatisch)").grid(row=0, column=0, columnspan=2, sticky="w")
    ttk.Label(frame, text="Personen-ID (1-99)").grid(row=1, column=0, sticky="w")
    person_entry = ttk.Entry(frame, textvariable=person_var, width=22)
    person_entry.grid(row=1, column=1, pady=2)
    ttk.Label(frame, text="Session (1-99)").grid(row=2, column=0, sticky="w")
    ttk.Entry(frame, textvariable=session_var, width=22).grid(row=2, column=1, pady=2)
    ttk.Label(frame, text="Szenario").grid(row=3, column=0, sticky="w")
    ttk.Combobox(frame, textvariable=scenario_var, values=scenarios, state="readonly", width=20).grid(
        row=3, column=1, pady=2
    )
    ttk.Label(frame, text="Sensor-Start (HH:MM:SS)").grid(row=4, column=0, sticky="w")
    ttk.Entry(frame, textvariable=start_var, width=22).grid(row=4, column=1, pady=2)
    ttk.Label(frame, textvariable=preview_var, font=("TkFixedFont", 12, "bold")).grid(
        row=5, column=0, columnspan=2, sticky="w", pady=(8, 0)
    )
    ttk.Label(frame, text="Muss genau der Trial-ID des Sensor-Skripts entsprechen.", foreground="gray").grid(
        row=6, column=0, columnspan=2, sticky="w"
    )
    ttk.Label(frame, textvariable=error_var, foreground="red", wraplength=420).grid(
        row=7, column=0, columnspan=2, sticky="w"
    )

    def current() -> tuple[str, int]:
        p = parse_person(person_var.get())
        return build_trial_id(day, p, parse_session(session_var.get()), scenario_var.get()), p

    def update_preview(*_):
        try:
            trial_id, _ = current()
        except ValueError:
            preview_var.set("Trial-ID: -")
            return
        taken = "  (existiert bereits)" if is_taken(out_dir, trial_id) else ""
        preview_var.set(f"Trial-ID: {trial_id}{taken}")

    def ok(*_):
        if not scenarios:
            error_var.set(f"Keine Szenarien gefunden: {scenario_dir}/SCxx.csv für {', '.join(SCENARIOS)} anlegen.")
            return
        try:
            trial_id, p = current()
            reference = parse_reference(start_var.get(), date.today())
            name = scenario_var.get()
            steps = load_scenario(scenario_dir / f"{name}.csv", labels)
        except (ValueError, OSError) as e:
            error_var.set(str(e))
            return
        if is_taken(out_dir, trial_id):
            error_var.set(
                f"{trial_id} existiert bereits in {out_dir} und wird nicht überschrieben "
                "(pro Tag, Person, Session und Szenario genau eine Aufnahme). Eingaben prüfen oder abbrechen."
            )
            return
        result.append((reference, trial_id, p, ScenarioProgress(name, steps)))
        dialog.destroy()

    for var in (person_var, session_var, scenario_var):
        var.trace_add("write", update_preview)

    buttons = ttk.Frame(frame)
    buttons.grid(row=8, column=0, columnspan=2, pady=(8, 0))
    ttk.Button(buttons, text="Start", command=ok).pack(side="left", padx=4)
    ttk.Button(buttons, text="Abbrechen", command=dialog.destroy).pack(side="left", padx=4)
    dialog.bind("<Return>", ok)
    dialog.bind("<Escape>", lambda _: dialog.destroy())

    update_preview()
    person_entry.focus_set()
    _run_modal(root, dialog)
    return result[0] if result else None


def edit_relationships(
    root: tk.Tk, labels: list[Label], initial: list[Relationship], path: Path
) -> list[Relationship] | None:
    """Modal editor for event -> activity links. Returns None if cancelled."""
    events = [l.label for l in labels if l.type == "event"]
    activities = [l.label for l in labels if l.type == "activity"]
    links = list(initial)
    result: list[list[Relationship]] = []

    dialog = tk.Toplevel(root)
    dialog.title("Link events to activities")
    dialog.resizable(False, False)
    frame = ttk.Frame(dialog, padding=12)
    frame.pack()
    ttk.Label(frame, text="""
              OPTIONAL: link events to activities for more convenient logging.
              Press 'Continue' to move on and save the links for future sessions.
              
              When an event is logged, start or stop an activity automatically.
              """
              ).grid(
        row=0, column=0, columnspan=4, sticky="w"
    )

    event_var = tk.StringVar(value=events[0])
    action_var = tk.StringVar(value=ACTIONS[0])
    activity_var = tk.StringVar(value=activities[0])
    for col, (var, values) in enumerate([(event_var, events), (action_var, ACTIONS), (activity_var, activities)]):
        ttk.Combobox(frame, textvariable=var, values=values, state="readonly", width=14).grid(
            row=1, column=col, padx=2, pady=6
        )

    listbox = tk.Listbox(frame, height=8, selectmode="extended", font="TkFixedFont")
    listbox.grid(row=2, column=0, columnspan=4, sticky="ew")

    def refresh():
        listbox.delete(0, "end")
        for r in links:
            listbox.insert("end", str(r))

    def add():
        new = Relationship(event_var.get(), action_var.get(), activity_var.get())
        # an event either starts or stops a given activity, so a new link replaces the old one
        links[:] = [r for r in links if (r.event, r.activity) != (new.event, new.activity)] + [new]
        refresh()

    def remove():
        for i in reversed(listbox.curselection()):
            del links[i]
        refresh()

    ttk.Button(frame, text="Add", command=add).grid(row=1, column=3, padx=2)
    ttk.Button(frame, text="Remove selected", command=remove).grid(row=3, column=0, sticky="w", pady=4)
    save_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(frame, text=f"Save to {path} for future recordings", variable=save_var).grid(
        row=4, column=0, columnspan=4, sticky="w"
    )

    def ok():
        if save_var.get():
            save_relationships(path, links)
        result.append(list(links))
        dialog.destroy()

    buttons = ttk.Frame(frame)
    buttons.grid(row=5, column=0, columnspan=4, pady=(8, 0))
    ttk.Button(buttons, text="Continue", command=ok).pack(side="left", padx=4)
    ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left", padx=4)

    refresh()
    _run_modal(root, dialog)
    return result[0] if result else None


def choose_relationships(root: tk.Tk, labels: list[Label], path: Path) -> list[Relationship] | None:
    """Offer saved links from `path`, otherwise open the editor. Returns None if cancelled."""
    if not ({"event", "activity"} <= {l.type for l in labels}):
        return []  # nothing to link
    initial: list[Relationship] = []
    if path.exists():
        try:
            saved = load_relationships(path, labels)
        except ValueError as e:
            messagebox.showwarning("Relationships", f"{e}\n\nPlease set up the links again.", parent=root)
        else:
            if saved:
                summary = "\n".join(str(r) for r in saved)
                if messagebox.askyesno(
                    "Relationships found", f"Use these links from {path}?\n\n{summary}", parent=root
                ):
                    return saved
                initial = saved
    return edit_relationships(root, labels, initial, path)


class SyncPanel:
    """Guided sync: rest, flip, rest, flip back, then keep the sensors moving.

    The rests are timed; the flips are logged only when the operator clicks, so the
    timestamp is the moment of the flip.
    """

    # step -> (instruction, action button text or None if disabled, next step after the countdown)
    STEPS = {
        "idle": ("Sensoren in die Box, z nach oben", "Sync starten", None),
        "rest1": ("Ruhe, Box nicht bewegen (z+)", None, "flip"),
        "flip": ("Jetzt flippen (z+ -> z-) und dabei klicken", "FLIP jetzt", None),
        "rest2": ("Ruhe, Box nicht bewegen (z-)", None, "flip_back"),
        "flip_back": ("Jetzt zurück flippen (z- -> z+) und dabei klicken", "ZURÜCK-FLIP jetzt", None),
        "done": ("Fertig: Sensoren entnehmen und in Bewegung halten", "Sync starten", None),
    }

    def __init__(self, parent: tk.Misc, root: tk.Tk, on_flip: Callable[[str], None], enabled: bool):
        self.root = root
        self.on_flip = on_flip
        self.enabled = enabled
        self.step = "idle"
        self.deadline = 0.0
        self.after_id: str | None = None
        self.is_current = False  # sync is the current scenario step

        frame = self.frame = ttk.LabelFrame(parent, text="Sync", padding=(8, 2, 8, 6))
        frame.pack(fill="x", padx=8, pady=(0, 4))
        frame.columnconfigure(0, weight=1)
        self.instruction_var = tk.StringVar()
        self.countdown_var = tk.StringVar()
        tk.Label(
            frame, textvariable=self.instruction_var, font=("TkDefaultFont", 11, "bold"),
            wraplength=480, justify="left", anchor="w",
        ).grid(row=0, column=0, sticky="w")
        tk.Label(frame, textvariable=self.countdown_var, font=("TkFixedFont", 22, "bold"), width=5).grid(
            row=0, column=1, rowspan=2, sticky="e"
        )
        buttons = ttk.Frame(frame)
        buttons.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        self.action = tk.Button(buttons, command=self._on_action, font=("TkDefaultFont", 11, "bold"))
        self.action.pack(side="left", fill="x", expand=True, ipady=2)
        self.default_bg = self.action.cget("bg")
        self.cancel_button = tk.Button(buttons, text="Abbrechen", command=self.cancel)
        self.cancel_button.pack(side="left", padx=(6, 0), ipady=2)
        self._show("idle")
        if not enabled:
            self.instruction_var.set(f"Nicht verfügbar: {SYNC_FLIP} / {SYNC_FLIP_BACK} fehlen als event")

    @property
    def active(self) -> bool:
        return self.step not in ("idle", "done")

    def set_current(self, is_current: bool) -> None:
        """Highlight the panel while sync is the current scenario step."""
        if is_current == self.is_current:
            return
        self.is_current = is_current
        self.frame.config(text="Sync  <<< jetzt" if is_current else "Sync")
        if self.enabled and not self.active:
            self._show(self.step, self.note)

    def _show(self, step: str, note: str = "") -> None:
        self.step = step
        self.note = note
        instruction, action_text, _ = self.STEPS[step]
        self.instruction_var.set(f"{note} {instruction}" if note else instruction)
        flip = step in ("flip", "flip_back")
        bg = FLIP_BG if flip else CURRENT_BG if self.is_current and not self.active else self.default_bg
        self.action.config(
            text=action_text or "Bitte warten ...",
            state="normal" if action_text and self.enabled else "disabled",
            bg=bg,
            activebackground=bg,
        )
        self.cancel_button.config(state="normal" if self.active else "disabled")
        if step not in ("rest1", "rest2"):
            self.countdown_var.set("")

    def _on_action(self) -> None:
        if self.step in ("idle", "done"):
            self._rest("rest1")
        elif self.step == "flip":
            self.on_flip(SYNC_FLIP)
            self._rest("rest2")
        elif self.step == "flip_back":
            self.on_flip(SYNC_FLIP_BACK)
            self._show("done")

    def _rest(self, step: str) -> None:
        self.deadline = time.monotonic() + SYNC_REST_S
        self._show(step)
        self._countdown()

    def _countdown(self) -> None:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            self.after_id = None
            self.root.bell()
            self._show(self.STEPS[self.step][2])
            return
        self.countdown_var.set(f"{math.ceil(remaining)} s")
        self.after_id = self.root.after(100, self._countdown)

    def cancel(self, note: str = "Abgebrochen.") -> None:
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self._show("idle", note)


class App:
    def __init__(
        self,
        root: tk.Tk,
        recorder: Recorder,
        labels: list[Label],
        csv_path: Path,
        progress: ScenarioProgress | None = None,
    ):
        self.root = root
        self.recorder = recorder
        self.session = recorder.session
        self.csv_path = csv_path
        self.progress = progress
        # oldest first: (press, scenario step index before the press if the press completed that step)
        self.history: list[tuple[Press, int | None]] = []
        self.skipped_ids: dict[int, int] = {}  # step index -> skipped_steps row id
        self.buttons: dict[str, tk.Button] = {}
        self.notice = ""
        self.notice_after: str | None = None

        root.title(f"Activity timestamps - {self.session.trial_id}")

        header = ttk.Frame(root, padding=(8, 4))
        header.pack(fill="x")
        ttk.Label(header, text=f"{self.session.trial_id}   Start {self.session.reference:%H:%M:%S}").pack(side="left")
        self.clock_var = tk.StringVar()
        ttk.Label(header, textvariable=self.clock_var, font=("TkFixedFont", 14)).pack(side="right")

        self.step_var = tk.StringVar()
        self.upcoming_var = tk.StringVar()
        if progress:
            panel = ttk.Frame(root, padding=(8, 0, 8, 4))
            panel.pack(fill="x")
            panel.columnconfigure(0, weight=1)
            tk.Label(
                panel, textvariable=self.step_var, font=("TkDefaultFont", 14, "bold"), fg="#1d6b1d", anchor="w"
            ).grid(row=0, column=0, sticky="w")
            self.upcoming_label = tk.Label(panel, textvariable=self.upcoming_var, anchor="w")
            self.upcoming_label.grid(row=1, column=0, sticky="w")
            self.upcoming_fg = self.upcoming_label.cget("fg")
            nav = ttk.Frame(panel)
            nav.grid(row=0, column=1, rowspan=2, sticky="e")
            self.back_button = ttk.Button(nav, text="< zurück", width=9, command=self.on_step_back)
            self.back_button.pack(side="left")
            self.skip_button = ttk.Button(nav, text="überspringen >", command=self.on_skip)
            self.skip_button.pack(side="left", padx=(4, 0))

        sync_ok = all(self.session.types.get(l) == "event" for l in SYNC_LABELS)
        self.sync = SyncPanel(root, root, self.on_press, enabled=sync_ok)

        body = ttk.Frame(root, padding=(8, 0))
        body.pack(fill="x")
        events = ttk.LabelFrame(body, text="Events", padding=4)
        activities = ttk.LabelFrame(body, text="Aktivitäten (Start / Stopp)", padding=4)
        events.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        activities.grid(row=0, column=1, sticky="nsew")
        body.columnconfigure(1, weight=1)
        events.columnconfigure(0, weight=1)
        activities.columnconfigure(tuple(range(ACTIVITY_COLUMNS)), weight=1, uniform="a")

        n_activities = 0
        for l in labels:
            if l.label in SYNC_LABELS and sync_ok:
                continue  # logged through the sync panel
            btn = tk.Button(
                events if l.type == "event" else activities, text=l.label, command=lambda n=l.label: self.on_press(n)
            )
            if l.type == "event":
                btn.grid(row=len(events.grid_slaves()), column=0, sticky="ew", pady=1, ipady=3)
            else:
                row, col = divmod(n_activities, ACTIVITY_COLUMNS)
                btn.grid(row=row, column=col, sticky="ew", padx=1, pady=1, ipady=3)
                n_activities += 1
            self.buttons[l.label] = btn
        self.default_bg = next(iter(self.buttons.values())).cget("bg") if self.buttons else None

        self.log = tk.Listbox(root, height=5, font="TkFixedFont")
        self.log.pack(fill="both", expand=True, padx=8, pady=4)

        footer = ttk.Frame(root, padding=(8, 0, 8, 6))
        footer.pack(fill="x")
        ttk.Button(footer, text="Undo last", command=self.on_undo).pack(side="left")
        ttk.Button(footer, text="Export CSV", command=self.on_export).pack(side="left", padx=4)
        self.status_var = tk.StringVar(value=csv_path.with_suffix(".sqlite").name)
        ttk.Label(footer, textvariable=self.status_var, foreground="gray").pack(side="left", padx=8)

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._refresh()
        self._tick()

    def _tick(self):
        self.clock_var.set(fmt_offset(self.session.elapsed()))
        self.root.after(200, self._tick)

    def _refresh(self):
        step = self.progress.current if self.progress else None
        current_label = step.label if step else None
        for label, button in self.buttons.items():
            running = label in self.recorder.running
            current = label == current_label
            bg = RUNNING_BG if running else CURRENT_BG if current else self.default_bg
            text = f"[stop] {label}" if running else label
            button.config(text=f">>> {text} <<<" if current else text, bg=bg, activebackground=bg)
        self.sync.set_current(current_label == SYNC)
        if self.progress:
            self._refresh_scenario()

        entries: list[tuple[float, str]] = []
        for row in self.session.rows():
            if row["type"] == "event":
                when = fmt_offset(row["start_s"])
            else:
                end = fmt_offset(row["end_s"]) if row["end_s"] is not None else "running"
                when = f"{fmt_offset(row['start_s'])} -> {end}"
            entries.append((row["start_s"], f"{when:<28} {row['label']}"))
        for t_s, number, label in self.session.skipped():
            entries.append((t_s, f"{fmt_offset(t_s):<28} [übersprungen] Schritt {number}: {label}"))
        self.log.delete(0, "end")
        for _, text in sorted(entries, key=lambda e: e[0], reverse=True):
            self.log.insert("end", text)

    def _refresh_scenario(self):
        p = self.progress
        total = len(p.steps)
        if p.finished:
            self.step_var.set(f"Szenario abgeschlossen ({total}/{total} Schritte)")
            self.upcoming_var.set("")
        else:
            self.step_var.set(f"Schritt {p.index + 1}/{total}: {p.current}")
            self.upcoming_var.set(f"Als Nächstes: {p.upcoming or 'Ende'}")
        if self.notice:  # shown instead of "Als Nächstes" for a moment
            self.upcoming_var.set(self.notice)
        self.upcoming_label.config(fg="#c9302c" if self.notice else self.upcoming_fg)
        self.skip_button.config(state="disabled" if p.finished else "normal")
        self.back_button.config(state="normal" if p.index > 0 else "disabled")

    def _notice(self, text: str) -> None:
        self.notice = text
        if self.notice_after is not None:
            self.root.after_cancel(self.notice_after)
        self.notice_after = self.root.after(NOTICE_MS, self._clear_notice)

    def _clear_notice(self) -> None:
        self.notice = ""
        self.notice_after = None
        self._refresh_scenario()

    def _step_result(self, step: Step, label: str, was_running: bool) -> tuple[bool, bool]:
        """(expected, done): did the press concern the current step, and did it complete it?"""
        if step.label == SYNC:
            return label in SYNC_LABELS, label == SYNC_FLIP_BACK
        if self.session.types[step.label] == "event":
            return label == step.label, label == step.label
        changed = was_running != (step.label in self.recorder.running)  # also via a linked event
        return label == step.label or changed, was_running and step.label not in self.recorder.running

    def on_press(self, label: str):
        step = self.progress.current if self.progress else None
        was_running = step is not None and step.label in self.recorder.running
        press = self.recorder.press(label)
        completed = None
        if step is not None:
            expected, done = self._step_result(step, label, was_running)
            if done:
                completed = self.progress.index
                self.progress.advance()
            if not expected:
                self._notice(f"Hinweis: {label} geloggt, erwartet war: {step}")
        self.history.append((press, completed))
        self._refresh()

    def _rewind(self, index: int) -> None:
        """Make `index` the current step again. Skip marks from there on are removed."""
        for i in [i for i in self.skipped_ids if i >= index]:
            self.session.delete_skipped(self.skipped_ids.pop(i))
        self.progress.index = index

    def on_skip(self):
        step = self.progress.current
        if step is None:
            return
        if step.label == SYNC and self.sync.active:
            self.sync.cancel("Abgebrochen (übersprungen).")
        self.skipped_ids[self.progress.index] = self.session.log_skipped(self.progress.name, step.number, step.label)
        self.progress.advance()
        self._refresh()

    def on_step_back(self):
        if self.progress.index > 0:
            self._rewind(self.progress.index - 1)
            self._refresh()

    def on_undo(self):
        if not self.history:
            return
        press, completed = self.history[-1]
        message = f"Undo the last press ({press.label})?"
        if len(press.created) + len(press.stopped) > 1:
            message += "\nLinked activity starts/stops are undone too."
        if completed is not None:
            message += f"\nDas Szenario geht zurück auf Schritt {completed + 1}."
        if not messagebox.askyesno("Undo", message, parent=self.root):
            return
        self.history.pop()
        self.recorder.undo(press)
        if press.label in SYNC_LABELS and self.sync.active:
            self.sync.cancel("Abgebrochen (Undo), bitte neu starten.")
        if completed is not None:
            self._rewind(completed)
        self._refresh()

    def on_export(self):
        path = self.session.export_csv(self.csv_path)
        self.status_var.set(f"Exportiert: {path.name}")

    def on_close(self):
        if self.recorder.running:
            answer = messagebox.askyesnocancel(
                "Activities running",
                f"Still running: {', '.join(self.recorder.running)}.\n"
                "Yes: stop them now.  No: leave end time empty.  Cancel: keep logging.",
                parent=self.root,
            )
            if answer is None:
                return
            if answer:
                self.recorder.stop_all()
        path = self.session.export_csv(self.csv_path)
        self.session.close()
        print(f"Exported {path}")
        self.root.destroy()
