"""Command line: python -m cos_agent [--today YYYY-MM-DD] [--mode auto|offline|claude] [--apply]"""
from __future__ import annotations

import argparse
import re
import os
from datetime import date
from pathlib import Path

from .briefing import render_briefing
from .drafting import TemplateWriter, subject_for
from .models import load_applications, save_applications
from .triage import triage


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Chief-of-staff agent for a job search.")
    p.add_argument("--data", default="data/applications.csv")
    p.add_argument("--out", default="output")
    p.add_argument("--today", default=None, help="Run as if today were this date (YYYY-MM-DD).")
    p.add_argument("--mode", choices=["auto", "offline", "claude"], default="auto",
                   help="auto uses Claude when ANTHROPIC_API_KEY is set, otherwise offline.")
    p.add_argument("--limit", type=int, default=8, help="Maximum drafts per run.")
    p.add_argument("--apply", action="store_true", help="Apply the agent's proposed status changes.")
    args = p.parse_args(argv)
    if not Path(args.data).exists() and args.data == "data/applications.csv":
        args.data = "data/sample_applications.csv"
        print("No data/applications.csv found; using the sample tracker.")

    today = date.fromisoformat(args.today) if args.today else date.today()
    apps = load_applications(args.data)
    out = Path(args.out)
    (out / "drafts").mkdir(parents=True, exist_ok=True)
    for old in (out / "drafts").glob("*.txt"):
        old.unlink()

    use_claude = args.mode == "claude" or (args.mode == "auto" and os.environ.get("ANTHROPIC_API_KEY"))
    proposals: list[dict] = []

    if use_claude:
        from .agent import ChiefOfStaffAgent
        result = ChiefOfStaffAgent(apps, today, limit=args.limit).run()
        drafts, briefing, proposals = result.drafts, result.briefing, result.proposals
        print(f"Claude agent finished in {result.turns} turns.")
    else:
        writer = TemplateWriter()
        actions = triage(apps, today)
        drafts = {}
        for a in [a for a in actions if a.needs_message][: args.limit]:
            drafts[a.app.id] = (subject_for(a), writer.draft(a))
        proposals = [{"id": a.app.id, "new_status": "Closed", "reason": a.reason}
                     for a in actions if a.kind == "close_out"]
        briefing = render_briefing(apps, actions, today, set(drafts))
        print("Offline mode (no API key): rule-based triage and template drafts.")

    by_id = {a.id: a for a in apps}
    for app_id, (subject, body) in drafts.items():
        slug = re.sub(r"[^a-z0-9]+", "-", by_id[app_id].company.lower()).strip("-")
        (out / "drafts" / f"{app_id:02d}-{slug}.txt").write_text(f"Subject: {subject}\n\n{body}\n", encoding="utf-8")

    if proposals:
        briefing += "\n## Proposed status changes (run with --apply to accept)\n\n"
        briefing += "\n".join(f"- {by_id[p['id']].label} -> {p['new_status']}: {p['reason']}" for p in proposals) + "\n"
    (out / "briefing.md").write_text(briefing, encoding="utf-8")

    if args.apply and proposals:
        for prop in proposals:
            by_id[prop["id"]].status = prop["new_status"]
        save_applications(apps, args.data)
        print(f"Applied {len(proposals)} status changes to {args.data}.")

    print(f"Briefing: {out / 'briefing.md'}  |  Drafts: {len(drafts)} in {out / 'drafts'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
