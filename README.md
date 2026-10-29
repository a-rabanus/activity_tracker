# activity_timestamps (draft)

A small tkinter tool for labelling human-activity recordings while the subject wears accelerometers.

- **`generators.csv`** (`label,type`) defines the labels. `type` is `event` (one click logs a timestamp)
  or `activity` (a toggle that logs a start and a stop). One button is created per row.
- **Sensor start time** (e.g. `12:55`) is the reference. Every timestamp is stored as seconds since that
  reference (`start_s`, `end_s`), and also as wall-clock ISO time.
- Each click is committed straight to `data/<subject>_<datetime>.sqlite`. A CSV with the same name is written
  on close and by the *Export CSV* button.
- **`relationships.csv`** (`event,action,activity`, optional) links events to activities, e.g.
  `sit_down,start,sitting` and `stand_up,stop,sitting`. See below.

## Run

```bash
uv run --python 3.14 python -m activity_timestamps                              # asks for links, start time + subject
uv run --python 3.14 python -m activity_timestamps --start 12:55 --subject S01  # skips the start-time dialog
uv run --python 3.14 --with pytest python -m pytest tests -q
```

You need a Python with tkinter. uv-managed Pythons include it. For the system Python, install `python3-tk`.

## Linking events to activities

- Before a recording starts, you're asked about links. If `relationships.csv` exists next to the generator
  (or at `--relationships PATH`), the app lists its links and asks whether to use them. If you say no, or
  there's no file yet, an editor opens. Pick *event → start/stop → activity*, then *Add* or *Remove selected*.
  *Continue* saves the links to `relationships.csv` for future recordings (untick the box to skip saving).
- During the recording, pressing a linked event also starts or stops the activity, with exactly the same
  timestamp. A link is skipped if the activity is already in that state (e.g. `sit_down` while already `sitting`).
- *Undo last* reverts the whole press, including any linked starts or stops.
- Each session's `.sqlite` keeps a `relationships` table with the links used for that recording.

## Changing `generators.csv`

- The file is read once, at launch. Editing it while the window is open changes nothing until you restart.
- Every launch creates a new `.sqlite` file. Its `labels` table and the buttons are filled from the
  generator as it is at that moment, so no database is shared between sessions and nothing needs migrating.
- Old session databases and CSVs are never touched. Each keeps the labels it was recorded with.
- Renaming a label means old and new sessions use different names for the same thing, so map the old
  names when you merge CSVs. Changing a label's type, or removing a label, only affects new sessions.
- `relationships.csv` is checked against the generator at launch. If a link names a label that no longer
  exists, or that has the wrong type, you get a warning and the editor opens to set the links up again.

## CSV output

`subject,label,type,start_s,end_s,duration_s,start_time,end_time`. For events, the `end_*` and
`duration_s` columns are empty.
