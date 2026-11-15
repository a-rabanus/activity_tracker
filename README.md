# activity_timestamps (draft)

A small tkinter tool for labelling human-activity recordings while the subject wears accelerometers.

- **`generators.csv`** (`label,type`) defines the labels. `type` is `event` (one click logs a timestamp)
  or `activity` (a toggle that logs a start and a stop). One button is created per row.
- **Sensor start time** (e.g. `12:55`) is the reference. Every timestamp is stored as seconds since that
  reference (`start_s`, `end_s`), and also as wall-clock ISO time.
- Each click is committed straight to `data/<Trial-ID>_labels.sqlite`. `data/<Trial-ID>_labels.csv` is written
  on close and by the *Export CSV* button. See *Trial ID and file names* below.
- **`relationships.csv`** (`event,action,activity`, optional) links events to activities, e.g.
  `sit_down,start,sitting` and `stand_up,stop,sitting`. See below.

## Run

```bash
uv run --python 3.14 python -m activity_timestamps                    # asks for links, then the start dialog
uv run --python 3.14 python -m activity_timestamps --start 12:55 \
    --trial 20261113_P01_EVT-scenario01_T01                           # skips the start dialog
```

You need a Python with tkinter. uv-managed Pythons include it. For the system Python, install `python3-tk`.

## Start dialog

The dialog asks for the **person ID** (1-99), the **scenario** (dropdown), the **trial number** (1-99) and the
**sensor start time**. The date is today's date. The resulting trial ID is shown live before you press *Start*.
Invalid input shows a message in red and the dialog stays open. The person ID (e.g. `P01`) is stored as `subject`.

`--trial <Trial-ID>` prefills the dialog (an invalid ID stops with an error message). If `--start` is given
as well and the trial ID is not used yet, the dialog is skipped.

## Trial ID and file names

`YYYYMMDD_Pxx_EVT-scenarioXX_Txx`, e.g. `20261113_P01_EVT-scenario01_T01`

- `YYYYMMDD` date, `Pxx` person ID, `EVT` fixed, `scenarioXX` from `SCENARIOS` in
  `activity_timestamps/naming.py` (add new scenarios there), `Txx` trial number.
- Files: `data/<Trial-ID>_labels.csv` and `data/<Trial-ID>_labels.sqlite`.
- Existing files are never overwritten. If the trial ID is already used, the next free trial number is filled
  in and you confirm with *Start* again.

## Sync procedure

Do this at the start and at the end of every recording. The panel at the top of the window guides you:

1. All sensors lie in the box, z-axis up (z positive). Click **Sync starten**: 20 s rest with countdown.
2. Beep. Flip the box (z positive -> z negative) and click **FLIP jetzt** at the moment of the flip:
   logs the event `sync_flip`. Then 20 s rest with countdown.
3. Beep. Flip back (z negative -> z positive) and click **ZURÜCK-FLIP jetzt**: logs `sync_flip_back`.
4. Take the sensors out and keep them moving.

- The flips are only logged by your click, so the timestamp is the moment of the flip.
- *Sync abbrechen* stops the sequence. Flips already logged stay in the log (remove them with *Undo last*).
  Undoing a sync flip while the sequence is running also stops the sequence.
- `sync_flip` and `sync_flip_back` must be `event`s in `generators.csv`. They get no extra buttons.
- The rest time is `SYNC_REST_S` in `activity_timestamps/app.py`.

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

`trial_id,subject,label,type,start_s,end_s,duration_s,start_time,end_time`. For events, the `end_*` and
`duration_s` columns are empty.
