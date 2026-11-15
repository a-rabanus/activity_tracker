"""Entry point: python -m activity_timestamps [--start 12:55] [--trial 20261115_P03_S01_SC02]"""

import argparse
import tkinter as tk
from datetime import date
from pathlib import Path

from tkinter import messagebox

from .app import App, ask_session_info, choose_relationships
from .generator import load_generator
from .naming import build_trial_id, is_taken, output_paths, parse_trial_id, subject_id
from .recorder import Recorder
from .scenario import ScenarioProgress, list_scenarios, load_scenario
from .storage import Session, parse_reference


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="activity_timestamps", description=__doc__)
    parser.add_argument("--generator", type=Path, default=Path("generators.csv"), help="label,type csv")
    parser.add_argument("--relationships", type=Path, help="event,action,activity csv (default: next to generator)")
    parser.add_argument("--start", help="sensor recording start, HH:MM[:SS] or ISO datetime")
    parser.add_argument("--trial", help="trial ID YYYYMMDD_Pxx_Sxx_SCxx as printed by the sensor script, e.g. 20261115_P03_S01_SC02")
    parser.add_argument("--scenarios", type=Path, help="folder with SCxx.csv step files (default: next to generator)")
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    args = parser.parse_args(argv)

    labels = load_generator(args.generator)
    scenario_dir = args.scenarios or args.generator.with_name("scenarios")
    reference = None
    if args.start:
        try:
            reference = parse_reference(args.start, date.today())
        except ValueError as e:
            parser.error(str(e))
    day, person, session, scenario = date.today(), None, None, None
    if args.trial:
        try:
            day, person, session, scenario = parse_trial_id(args.trial)
        except ValueError as e:
            parser.error(str(e))
        if is_taken(args.out_dir, build_trial_id(day, person, session, scenario)):
            parser.error(
                f"{build_trial_id(day, person, session, scenario)} existiert bereits in {args.out_dir} und wird nicht "
                "überschrieben (pro Tag, Person, Session und Szenario genau eine Aufnahme)"
            )
        if scenario not in list_scenarios(scenario_dir):
            parser.error(f"Szenario {scenario!r} aus --trial gibt es nicht: {scenario_dir / scenario}.csv fehlt")

    root = tk.Tk()
    root.withdraw()
    relationships = choose_relationships(
        root, labels, args.relationships or args.generator.with_name("relationships.csv")
    )
    if relationships is None:
        root.destroy()
        return
    if reference and args.trial:
        trial_id = build_trial_id(day, person, session, scenario)
        try:
            progress = ScenarioProgress(scenario, load_scenario(scenario_dir / f"{scenario}.csv", labels))
        except (ValueError, OSError) as e:
            messagebox.showerror("Szenario", str(e), parent=root)
            root.destroy()
            return
    else:
        info = ask_session_info(
            root, args.out_dir, day, scenario_dir, labels, person, session, scenario, args.start
        )
        if info is None:
            root.destroy()
            return
        reference, trial_id, person, progress = info
    root.deiconify()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path, db_path = output_paths(args.out_dir, trial_id)
    session = Session(
        db_path, labels, reference, subject_id(person), args.generator,
        relationships=relationships, trial_id=trial_id,
    )
    App(root, Recorder(session, relationships), labels, csv_path, progress)
    root.mainloop()


if __name__ == "__main__":
    main()
