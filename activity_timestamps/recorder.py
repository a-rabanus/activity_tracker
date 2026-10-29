"""Button semantics: events, activity toggles, linked activities and undo."""

from dataclasses import dataclass, field

from .relationships import Relationship
from .storage import Session


@dataclass
class Press:
    """What one button press changed, so it can be undone as a unit."""

    label: str
    created: list[int] = field(default_factory=list)  # annotation ids inserted
    stopped: list[int] = field(default_factory=list)  # running activities this press stopped


class Recorder:
    def __init__(self, session: Session, relationships: list[Relationship] = ()):
        self.session = session
        self.relationships = list(relationships)
        self.running: dict[str, int] = {}  # activity label -> annotation id
        self.links: dict[str, list[Relationship]] = {}
        for r in relationships:
            self.links.setdefault(r.event, []).append(r)

    def press(self, label: str) -> Press:
        now = self.session.clock()  # one timestamp for the press and everything it triggers
        press = Press(label)
        if self.session.types.get(label) == "event":
            press.created.append(self.session.log_event(label, at=now))
            for r in self.links.get(label, []):
                running = r.activity in self.running
                if (r.action == "start" and not running) or (r.action == "stop" and running):
                    self._toggle(r.activity, now, press)
        else:
            self._toggle(label, now, press)
        return press

    def _toggle(self, activity, at, press: Press) -> None:
        if activity in self.running:
            annotation_id = self.running.pop(activity)
            self.session.stop_activity(annotation_id, at=at)
            press.stopped.append(annotation_id)
        else:
            annotation_id = self.session.start_activity(activity, at=at)
            self.running[activity] = annotation_id
            press.created.append(annotation_id)

    def undo(self, press: Press) -> None:
        """Revert a press. Only valid for the most recent press (LIFO)."""
        for annotation_id in press.stopped:
            self.session.reopen(annotation_id)
            self.running[self.session.get(annotation_id)[0]] = annotation_id
        for annotation_id in press.created:
            label = self.session.get(annotation_id)[0]
            if self.running.get(label) == annotation_id:
                del self.running[label]
            self.session.delete(annotation_id)

    def stop_all(self) -> None:
        now = self.session.clock()
        for annotation_id in self.running.values():
            self.session.stop_activity(annotation_id, at=now)
        self.running.clear()
