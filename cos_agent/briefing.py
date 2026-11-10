"""Offline daily briefing: same structure the Claude agent is asked to produce."""
from __future__ import annotations

from datetime import date

from .models import Application
from .triage import Action, pipeline_summary


def _line(a: Action) -> str:
    who = f" (contact: {a.app.contact_name})" if a.app.contact_name else ""
    return f"- **{a.app.label}**{who}. {a.reason}"


def render_briefing(apps: list[Application], actions: list[Action], today: date,
                    drafted_ids: set[int]) -> str:
    submit = [a for a in actions if a.kind == "submit"]
    follow = [a for a in actions if a.needs_message]
    close = [a for a in actions if a.kind == "close_out"]
    top = actions[:3]

    out = [f"# Daily briefing: {today:%A, %B %-d, %Y}", ""]
    out.append(f"{len(actions)} things need attention: {len(submit)} to submit, "
               f"{len(follow)} follow-ups, {len(close)} to close out.")
    out += ["", "## Do these first", ""]
    out += [f"{i}. **{a.app.label}**: {a.reason}" for i, a in enumerate(top, 1)]

    if submit:
        out += ["", "## Ready to submit", ""] + [_line(a) for a in submit]
    if follow:
        out += ["", "## Follow-ups (drafts in the drafts folder)", ""]
        for a in follow:
            mark = " Draft ready." if a.app.id in drafted_ids else ""
            out.append(_line(a) + mark)
    if close:
        out += ["", "## Close out or one last nudge", ""] + [_line(a) for a in close]

    out += ["", "## Pipeline", ""]
    out += [f"- {status}: {n}" for status, n in pipeline_summary(apps).items()]
    estimates = sum(1 for a in apps if a.date_is_estimate)
    if estimates:
        out += ["", f"_{estimates} application dates are estimates. Correct them in the tracker "
                    "and the follow-up timing gets sharper._"]
    return "\n".join(out) + "\n"
