"""Follow-up drafts in Marisa's voice.

Two writers share one interface:
* TemplateWriter works offline, with no API key. Short, warm, no P.S.
* Claude (see agent.py) writes richer drafts when ANTHROPIC_API_KEY is set.
"""
from __future__ import annotations

from .triage import Action

import os

SIGNATURE = os.environ.get("COS_SIGNATURE", "Marisa Pavan").replace("\\n", "\n")

VOICE_GUIDE = """\
Write as Marisa Pavan: a founder who built and ran a premium membership business
for 14 years, then sold it. Warm, direct and short. Sell her gently with one
concrete proof point, never a list. No exclamation marks, no P.S., no clichés
like "I hope this email finds you well". Under 120 words. Plain text."""


def _greeting(action: Action) -> str:
    name = action.app.contact_name.split("/")[0].strip()
    first = name.split()[0] if name else ""
    return f"Hi {first}," if first else f"Hello {action.app.company} team,"


def subject_for(action: Action) -> str:
    return f"{action.app.role}: Marisa Pavan"


class TemplateWriter:
    """Deterministic drafts. Good enough to send after a quick read."""

    def draft(self, action: Action) -> str:
        app, g = action.app, _greeting(action)
        who = "your client" if "recruiter" in app.notes.lower() else app.company
        if action.kind == "thank_you":
            body = (f"Thank you for your time today on the {app.role} role. "
                    "I left even more excited about the work, and I'd be glad to "
                    "send anything else that would help.")
        elif action.kind in {"follow_up", "interview_check_in"}:
            body = (f"I applied for the {app.role} role and wanted to check in. "
                    "I spent 14 years building and running a premium membership "
                    "business, kept 87% of our members, and handed it to a general "
                    "manager when I sold in 2025. I'd welcome a conversation about "
                    f"how that could help {who}.")
        elif action.kind == "second_follow_up":
            body = (f"A short note to keep my application for the {app.role} role "
                    "on your radar. I'm still very interested, and happy to work "
                    "around your timeline.")
        elif action.kind == "on_file_check_in":
            body = (f"You kindly kept my resume on file for the {app.role} role. "
                    "I wanted to check in in case anything has opened up. I'm still "
                    f"very interested in {app.company}.")
        else:
            return ""
        return f"{g}\n\n{body}\n\nWarm regards,\n\n{SIGNATURE}"
