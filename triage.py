"""Triage: turn the tracker into a ranked list of actions for today.

The rules are deliberately plain so they can be read, argued with and changed:

* "To submit"   -> submit it (highest priority; ready work that is sitting still).
* "Applied"     -> wait 7 days, then follow up; nudge again 7 days later; at 30 days
                   with no reply, suggest closing it out to keep the list honest.
* "Interviewing"-> send a thank-you within a day, then check in after 5 days.
* "Closed"      -> "kept on file" roles get a friendly check-in at 60 days.
* "Rejected", "Hired", "Passed" -> nothing to do.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .models import Application

FIRST_FOLLOW_UP_DAYS = 7
STALE_DAYS = 30
ON_FILE_CHECK_IN_DAYS = 60

KIND_WEIGHT = {
    "submit": 100,
    "thank_you": 95,
    "interview_check_in": 80,
    "follow_up": 70,
    "second_follow_up": 60,
    "on_file_check_in": 40,
    "close_out": 30,
}
FIT_WEIGHT = {"high": 20, "medium": 10, "low": 0}


@dataclass
class Action:
    app: Application
    kind: str
    reason: str
    days_waiting: int | None = None

    @property
    def score(self) -> int:
        score = KIND_WEIGHT[self.kind] + FIT_WEIGHT.get(self.app.fit, 0)
        if self.app.contact_name:  # a named person makes a follow-up far more useful
            score += 10
        return score

    @property
    def needs_message(self) -> bool:
        return self.kind not in {"submit", "close_out"}


def _days_since(d: date | None, today: date) -> int | None:
    return (today - d).days if d else None


def triage_one(app: Application, today: date) -> Action | None:
    waited = _days_since(app.last_touch(), today)

    if app.status == "To submit":
        return Action(app, "submit", "Ready to send, but not sent yet.")

    if app.status == "Interviewing":
        if waited is not None and waited <= 1:
            return Action(app, "thank_you", "Interview just happened; thank-you due within a day.", waited)
        if waited is not None and waited >= 5:
            return Action(app, "interview_check_in", f"No word {waited} days after the interview.", waited)
        return None

    if app.status == "Applied":
        if waited is None:
            return Action(app, "follow_up", "No application date recorded; confirm it went through.")
        followed_up = bool(app.last_contact_on and (not app.applied_on or app.last_contact_on > app.applied_on))
        if waited >= STALE_DAYS:
            return Action(app, "close_out", f"{waited} days with no reply. Likely dead; close it out or try one last nudge.", waited)
        if waited >= FIRST_FOLLOW_UP_DAYS and not followed_up:
            return Action(app, "follow_up", f"{waited} days since applying and no follow-up yet.", waited)
        if waited >= FIRST_FOLLOW_UP_DAYS:
            return Action(app, "second_follow_up", f"{waited} days since the last follow-up. One more short nudge.", waited)
        return None

    if app.status == "Closed" and "on file" in app.notes.lower():
        if waited is not None and waited >= ON_FILE_CHECK_IN_DAYS:
            return Action(app, "on_file_check_in", f"Kept on file {waited} days ago. Friendly check-in.", waited)

    return None


def triage(apps: list[Application], today: date) -> list[Action]:
    actions = [a for a in (triage_one(app, today) for app in apps) if a]
    return sorted(actions, key=lambda a: (-a.score, a.app.company))


def pipeline_summary(apps: list[Application]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for app in apps:
        counts[app.status] = counts.get(app.status, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))
