"""Application records: load and save the tracker CSV."""
from __future__ import annotations

import csv
from dataclasses import dataclass, asdict, fields
from datetime import date
from pathlib import Path

OPEN_STATUSES = {"To submit", "Applied", "Interviewing", "Closed"}
DONE_STATUSES = {"Rejected", "Hired", "Passed"}


@dataclass
class Application:
    id: int
    company: str
    role: str
    lane: str = ""
    location: str = ""
    pay: str = ""
    status: str = "To submit"
    applied_on: date | None = None
    date_is_estimate: bool = False
    last_contact_on: date | None = None
    contact_name: str = ""
    contact_channel: str = ""
    fit: str = "medium"
    notes: str = ""

    @property
    def label(self) -> str:
        return f"{self.company}: {self.role}"

    def last_touch(self) -> date | None:
        """Most recent date anything happened on this application."""
        dates = [d for d in (self.applied_on, self.last_contact_on) if d]
        return max(dates) if dates else None

    def to_row(self) -> dict:
        row = asdict(self)
        for key in ("applied_on", "last_contact_on"):
            row[key] = row[key].isoformat() if row[key] else ""
        row["date_is_estimate"] = "yes" if self.date_is_estimate else "no"
        return row


def _parse_date(value: str) -> date | None:
    value = (value or "").strip()
    return date.fromisoformat(value) if value else None


def load_applications(path: str | Path) -> list[Application]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    apps = []
    for r in rows:
        apps.append(
            Application(
                id=int(r["id"]),
                company=r["company"].strip(),
                role=r["role"].strip(),
                lane=r.get("lane", "").strip(),
                location=r.get("location", "").strip(),
                pay=r.get("pay", "").strip(),
                status=r.get("status", "To submit").strip(),
                applied_on=_parse_date(r.get("applied_on", "")),
                date_is_estimate=r.get("date_is_estimate", "").strip().lower() == "yes",
                last_contact_on=_parse_date(r.get("last_contact_on", "")),
                contact_name=r.get("contact_name", "").strip(),
                contact_channel=r.get("contact_channel", "").strip(),
                fit=(r.get("fit", "medium").strip().lower() or "medium"),
                notes=r.get("notes", "").strip(),
            )
        )
    return apps


def save_applications(apps: list[Application], path: str | Path) -> None:
    names = [f.name for f in fields(Application)]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=names)
        writer.writeheader()
        for app in apps:
            writer.writerow(app.to_row())
