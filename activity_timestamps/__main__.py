"""Entry point: python -m activity_timestamps [--start 12:55] [--subject S01]"""

import argparse
import re
import tkinter as tk
from datetime import date, datetime
from pathlib import Path

from .app import App, ask_session_info, choose_relationships
from .generator import load_generator
from .recorder import Recorder
from .storage import Session, parse_reference


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="activity_timestamps", description=__doc__)
    parser.add_argument("--generator", type=Path, default=Path("generators.csv"), help="label,type csv")
    parser.add_argument("--relationships", type=Path, help="event,action,activity csv (default: next to generator)")
    parser.add_argument("--start", help="sensor recording start, HH:MM[:SS] or ISO datetime")
    parser.add_argument("--subject", help="subject ID, used in output file names")
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    args = parser.parse_args(argv)

    labels = load_generator(args.generator)
    reference = None
    if args.start:
        try:
            reference = parse_reference(args.start, date.today())
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
    if reference and args.subject:
        subject = args.subject
    else:
        info = ask_session_info(root, args.subject or "S01", args.start)
        if info is None:
            root.destroy()
            return
        reference, subject = info
    root.deiconify()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    safe_subject = re.sub(r"\W+", "_", subject)
    stem = args.out_dir / f"{safe_subject}_{datetime.now():%Y%m%d_%H%M%S}"
    session = Session(
        stem.with_suffix(".sqlite"), labels, reference, subject, args.generator, relationships=relationships
    )
    App(root, Recorder(session, relationships), labels, stem.with_suffix(".csv"))
    root.mainloop()


if __name__ == "__main__":
    main()
