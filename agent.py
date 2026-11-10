"""The Claude-driven chief-of-staff agent.

Claude gets a small set of tools over the tracker and decides how to use them:
it reviews today's actions, drafts the follow-ups worth sending, proposes status
changes (which a human approves), and writes the daily briefing.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date

from .drafting import SIGNATURE, VOICE_GUIDE, subject_for
from .models import Application
from .triage import Action, pipeline_summary, triage

DEFAULT_MODEL = os.environ.get("COS_MODEL", "claude-sonnet-5-5")
MAX_TURNS = 25

SYSTEM_PROMPT = f"""\
You are the chief-of-staff agent for Marisa Pavan's job search. Your job is to
make sure nothing stalls and that she spends her time on the highest-value moves.

Each run:
1. Call list_actions to see today's ranked actions.
2. For each action that needs a message, look at the application if useful, then
   call save_draft with a subject and body. Draft at most {{limit}} messages,
   highest priority first.
3. For applications that have gone stale, call propose_status_change. Never
   assume a change is approved; Marisa decides.
4. Finish by calling submit_briefing with a Markdown briefing: a one-line
   summary, "Do these first" (top 3 with the reason), ready-to-submit items,
   follow-ups, close-outs, and pipeline counts. Be specific and brief.

Drafting voice:
{VOICE_GUIDE}
Sign off with:
{SIGNATURE}
"""

TOOLS = [
    {
        "name": "list_actions",
        "description": "Today's ranked actions from the tracker, highest priority first.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_application",
        "description": "Full record for one application, including notes and contact.",
        "input_schema": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]},
    },
    {
        "name": "save_draft",
        "description": "Save a follow-up email draft for Marisa to review and send.",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["id", "subject", "body"],
        },
    },
    {
        "name": "propose_status_change",
        "description": "Propose a new status for an application. Marisa approves before it is applied.",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "new_status": {"type": "string", "enum": ["Applied", "Interviewing", "Closed", "Rejected", "Passed", "Hired"]},
                "reason": {"type": "string"},
            },
            "required": ["id", "new_status", "reason"],
        },
    },
    {
        "name": "submit_briefing",
        "description": "Submit the final daily briefing in Markdown. Ends the run.",
        "input_schema": {"type": "object", "properties": {"markdown": {"type": "string"}}, "required": ["markdown"]},
    },
]


@dataclass
class RunResult:
    briefing: str = ""
    drafts: dict[int, tuple[str, str]] = field(default_factory=dict)
    proposals: list[dict] = field(default_factory=list)
    turns: int = 0


class ChiefOfStaffAgent:
    def __init__(self, apps: list[Application], today: date, client=None,
                 model: str = DEFAULT_MODEL, limit: int = 8):
        self.apps = {a.id: a for a in apps}
        self.today = today
        self.actions: list[Action] = triage(apps, today)
        self.limit = limit
        self.model = model
        if client is None:
            import anthropic  # imported lazily so offline mode needs no SDK key
            client = anthropic.Anthropic()
        self.client = client
        self.result = RunResult()

    # ---- tools -------------------------------------------------------------
    def _list_actions(self, _: dict) -> str:
        return json.dumps({
            "today": self.today.isoformat(),
            "pipeline": pipeline_summary(list(self.apps.values())),
            "actions": [
                {"id": a.app.id, "company": a.app.company, "role": a.app.role,
                 "action": a.kind, "reason": a.reason, "priority": a.score,
                 "contact": a.app.contact_name, "channel": a.app.contact_channel,
                 "needs_message": a.needs_message}
                for a in self.actions
            ],
        })

    def _get_application(self, args: dict) -> str:
        app = self.apps.get(int(args["id"]))
        return json.dumps(app.to_row()) if app else json.dumps({"error": "no such id"})

    def _save_draft(self, args: dict) -> str:
        app_id = int(args["id"])
        if app_id not in self.apps:
            return "error: no such id"
        if len(self.result.drafts) >= self.limit and app_id not in self.result.drafts:
            return f"error: draft limit of {self.limit} reached"
        self.result.drafts[app_id] = (args["subject"], args["body"])
        return "saved"

    def _propose_status_change(self, args: dict) -> str:
        if int(args["id"]) not in self.apps:
            return "error: no such id"
        self.result.proposals.append(
            {"id": int(args["id"]), "new_status": args["new_status"], "reason": args["reason"]})
        return "recorded for approval"

    def _submit_briefing(self, args: dict) -> str:
        self.result.briefing = args["markdown"]
        return "briefing received"

    def _call_tool(self, name: str, args: dict) -> str:
        handler = getattr(self, f"_{name}", None)
        if handler is None:
            return f"error: unknown tool {name}"
        try:
            return handler(args or {})
        except Exception as exc:  # report tool errors back to the model, don't crash
            return f"error: {exc}"

    # ---- loop --------------------------------------------------------------
    def run(self) -> RunResult:
        messages = [{"role": "user", "content": f"Run today's review for {self.today:%A, %B %-d, %Y}."}]
        system = SYSTEM_PROMPT.replace("{limit}", str(self.limit))
        for turn in range(MAX_TURNS):
            self.result.turns = turn + 1
            response = self.client.messages.create(
                model=self.model, max_tokens=4000, system=system, tools=TOOLS, messages=messages)
            messages.append({"role": "assistant", "content": response.content})
            tool_uses = [b for b in response.content if getattr(b, "type", "") == "tool_use"]
            if not tool_uses:
                break
            results = [{"type": "tool_result", "tool_use_id": b.id, "content": self._call_tool(b.name, b.input)}
                       for b in tool_uses]
            messages.append({"role": "user", "content": results})
            if self.result.briefing:
                break
        return self.result


def default_subject(action: Action) -> str:
    return subject_for(action)
