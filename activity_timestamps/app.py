"""Tkinter window for the operator: one button per event, one toggle per activity."""

import tkinter as tk
from datetime import date, datetime
from pathlib import Path
from tkinter import messagebox, ttk

from .generator import Label
from .recorder import Press, Recorder
from .relationships import ACTIONS, Relationship, load_relationships, save_relationships
from .storage import parse_reference

RUNNING_BG = "#d9534f"


def fmt_offset(seconds: float) -> str:
    sign = "-" if seconds < 0 else "+"
    h, rem = divmod(abs(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{sign}{int(h):02d}:{int(m):02d}:{s:04.1f}"


def _run_modal(root: tk.Tk, dialog: tk.Toplevel) -> None:
    dialog.wait_visibility()
    dialog.grab_set()
    root.wait_window(dialog)


def ask_session_info(root: tk.Tk, default_subject: str, default_start: str | None) -> tuple[datetime, str] | None:
    """Modal dialog for sensor start time and subject ID. Returns None if cancelled."""
    dialog = tk.Toplevel(root)
    dialog.title("New session")
    dialog.resizable(False, False)
    frame = ttk.Frame(dialog, padding=12)
    frame.pack()

    start_var = tk.StringVar(value=default_start or datetime.now().strftime("%H:%M:%S"))
    subject_var = tk.StringVar(value=default_subject)
    error_var = tk.StringVar()
    result: list[tuple[datetime, str]] = []

    ttk.Label(frame, text="""
                  Enter timestamp for measurement start
                  Enter session and subject ID.  (The subject ID is used to name the output files)
                  """
                  ).grid(
            row=0, column=0, columnspan=4, sticky="w"
        )
    ttk.Label(frame, text="Sensor start (HH:MM[:SS])").grid(row=1, column=0, sticky="w")
    start_entry = ttk.Entry(frame, textvariable=start_var, width=20)
    start_entry.grid(row=1, column=1, pady=2)
    ttk.Label(frame, text="Subject ID").grid(row=2, column=0, sticky="w")
    ttk.Entry(frame, textvariable=subject_var, width=20).grid(row=2, column=1, pady=2)
    ttk.Label(frame, textvariable=error_var, foreground="red").grid(row=2, column=0, columnspan=2)

    def ok(*_):
        subject = subject_var.get().strip()
        if not subject:
            error_var.set("subject ID is required")
            return
        try:
            reference = parse_reference(start_var.get(), date.today())
        except ValueError as e:
            error_var.set(str(e))
            return
        result.append((reference, subject))
        dialog.destroy()

    buttons = ttk.Frame(frame)
    buttons.grid(row=3, column=0, columnspan=2, pady=(8, 0))
    ttk.Button(buttons, text="Start", command=ok).pack(side="left", padx=4)
    ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left", padx=4)
    dialog.bind("<Return>", ok)
    dialog.bind("<Escape>", lambda _: dialog.destroy())

    start_entry.focus_set()
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


class App:
    def __init__(self, root: tk.Tk, recorder: Recorder, labels: list[Label], csv_path: Path):
        self.root = root
        self.recorder = recorder
        self.session = recorder.session
        self.csv_path = csv_path
        self.history: list[Press] = []  # oldest first
        self.buttons: dict[str, tk.Button] = {}

        root.title(f"Activity timestamps - {self.session.subject}")

        header = ttk.Frame(root, padding=8)
        header.pack(fill="x")
        
        ttk.Label(
            header, text=f"Subject: {self.session.subject}    Sensor start: {self.session.reference:%Y-%m-%d %H:%M:%S}"
        ).pack(side="left")
        self.clock_var = tk.StringVar()
        ttk.Label(header, textvariable=self.clock_var, font=("TkFixedFont", 16)).pack(side="right")
        if recorder.relationships:
            links = "Links: " + ", ".join(str(r) for r in recorder.relationships)
            ttk.Label(root, text=links, padding=(8, 0, 8, 8), wraplength=600).pack(fill="x")

        body = ttk.Frame(root, padding=(8, 0))
        body.pack(fill="both", expand=True)
        events = ttk.LabelFrame(body, text="Events", padding=8)
        activities = ttk.LabelFrame(body, text="Activities (click to start / stop)", padding=8)
        events.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        activities.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        body.columnconfigure((0, 1), weight=1)

        for l in labels:
            parent = events if l.type == "event" else activities
            btn = tk.Button(parent, text=l.label, command=lambda n=l.label: self.on_press(n))
            btn.pack(fill="x", pady=2, ipady=6)
            self.buttons[l.label] = btn
        self.default_bg = next(iter(self.buttons.values())).cget("bg") if self.buttons else None
        self.activity_labels = [l.label for l in labels if l.type == "activity"]

        self.log = tk.Listbox(root, height=10, font="TkFixedFont")
        self.log.pack(fill="both", expand=True, padx=8, pady=8)

        footer = ttk.Frame(root, padding=(8, 0, 8, 8))
        footer.pack(fill="x")
        ttk.Button(footer, text="Undo last", command=self.on_undo).pack(side="left")
        ttk.Button(footer, text="Export CSV", command=self.on_export).pack(side="left", padx=4)
        self.status_var = tk.StringVar(value=f"Logging to {csv_path.with_suffix('.sqlite')}")
        ttk.Label(footer, textvariable=self.status_var).pack(side="left", padx=8)

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._tick()

    def _tick(self):
        self.clock_var.set(fmt_offset(self.session.elapsed()))
        self.root.after(200, self._tick)

    def _refresh(self):
        for label in self.activity_labels:
            running = label in self.recorder.running
            self.buttons[label].config(
                text=f"[stop] {label}" if running else label,
                bg=RUNNING_BG if running else self.default_bg,
                activebackground=RUNNING_BG if running else self.default_bg,
            )
        self.log.delete(0, "end")
        for row in reversed(self.session.rows()):
            if row["type"] == "event":
                when = fmt_offset(row["start_s"])
            else:
                end = fmt_offset(row["end_s"]) if row["end_s"] is not None else "running"
                when = f"{fmt_offset(row['start_s'])} -> {end}"
            self.log.insert("end", f"{when:<28} {row['label']}")

    def on_press(self, label: str):
        self.history.append(self.recorder.press(label))
        self._refresh()

    def on_undo(self):
        if not self.history:
            return
        press = self.history[-1]
        message = f"Undo the last press ({press.label})?"
        if len(press.created) + len(press.stopped) > 1:
            message += "\nLinked activity starts/stops are undone too."
        if not messagebox.askyesno("Undo", message, parent=self.root):
            return
        self.history.pop()
        self.recorder.undo(press)
        self._refresh()

    def on_export(self):
        path = self.session.export_csv(self.csv_path)
        self.status_var.set(f"Exported {path}")

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
