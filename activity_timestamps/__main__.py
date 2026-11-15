"""Entry point: python -m activity_timestamps [--start 12:55] [--trial 20261113_P01_EVT-scenario01_T01]"""

import argparse
import tkinter as tk
from datetime import date
from pathlib import Path

from .app import App, ask_session_info, choose_relationships
from .generator import load_generator
from .naming import SCENARIOS, is_taken, output_paths, parse_trial_id, subject_id
from .recorder import Recorder
from .storage import Session, parse_reference


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="activity_timestamps", description=__doc__)
    parser.add_argument("--generator", type=Path, default=Path("generators.csv"), help="label,type csv")
    parser.add_argument("--relationships", type=Path, help="event,action,activity csv (default: next to generator)")
    parser.add_argument("--start", help="sensor recording start, HH:MM[:SS] or ISO datetime")
    parser.add_argument("--trial", help="trial ID YYYYMMDD_Pxx_EVT-scenarioXX_Txx, e.g. 20261113_P01_EVT-scenario01_T01")
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    args = parser.parse_args(argv)

    labels = load_generator(args.generator)
    reference = None
    if args.start:
        try:
            reference = parse_reference(args.start, date.today())
        except ValueError as e:
            parser.error(str(e))
    day, person, scenario, trial = date.today(), None, SCENARIOS[0], None
    if args.trial:
        try:
            day, person, scenario, trial = parse_trial_id(args.trial)
        except ValueError as e:
            parser.error(str(e))

    root = tk.Tk()
    root.withdraw()
    relationships = choose_relationships(
        root, labels, args.relationships or args.generator.with_name("relationships.csv")
    )
    if relationships is None:
        root.destroy()
        return
    if reference and args.trial and not is_taken(args.out_dir, args.trial):
        trial_id = args.trial
    else:
        info = ask_session_info(root, args.out_dir, day, person, scenario, trial, args.start)
        if info is None:
            root.destroy()
            return
        reference, trial_id, person = info
    root.deiconify()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path, db_path = output_paths(args.out_dir, trial_id)
    session = Session(
        db_path, labels, reference, subject_id(person), args.generator,
        relationships=relationships, trial_id=trial_id,
    )
    App(root, Recorder(session, relationships), labels, csv_path)
    root.mainloop()


if __name__ == "__main__":
    main()
