from datetime import date
from pathlib import Path
from types import SimpleNamespace

from cos_agent.agent import ChiefOfStaffAgent
from cos_agent.models import Application, load_applications
from cos_agent.triage import triage, triage_one

TODAY = date(2026, 11, 4)
DATA = Path(__file__).parent.parent / "data" / "applications.csv"


def app(**kw):
    base = dict(id=1, company="Acme", role="Ops Manager", status="Applied")
    base.update(kw)
    return Application(**base)


def test_waits_a_week_before_following_up():
    assert triage_one(app(applied_on=date(2026, 11, 1)), TODAY) is None
    assert triage_one(app(applied_on=date(2026, 10, 28)), TODAY).kind == "follow_up"


def test_second_nudge_only_after_a_first_one():
    assert triage_one(app(applied_on=date(2026, 10, 20)), TODAY).kind == "follow_up"
    followed = app(applied_on=date(2026, 10, 10), last_contact_on=date(2026, 10, 20))
    assert triage_one(followed, TODAY).kind == "second_follow_up"


def test_close_out_after_a_month():
    assert triage_one(app(applied_on=date(2026, 10, 1)), TODAY).kind == "close_out"


def test_recent_contact_resets_the_clock():
    a = app(applied_on=date(2026, 10, 1), last_contact_on=date(2026, 11, 2))
    assert triage_one(a, TODAY) is None


def test_ready_work_comes_first():
    actions = triage([app(id=1, applied_on=date(2026, 10, 25)), app(id=2, status="To submit")], TODAY)
    assert actions[0].kind == "submit"


def test_finished_applications_need_nothing():
    for status in ("Rejected", "Hired", "Passed"):
        assert triage_one(app(status=status, applied_on=date(2026, 9, 1)), TODAY) is None


def test_real_tracker_loads_and_triages():
    apps = load_applications(DATA)
    assert len(apps) >= 20
    assert triage(apps, TODAY)


# ---- the Claude tool loop, with a scripted stand-in for the API ---------------

def block(name, input, id):
    return SimpleNamespace(type="tool_use", name=name, input=input, id=id)


class FakeClient:
    """Plays back a fixed sequence of tool calls, the way Claude would."""

    def __init__(self, script):
        self.script, self.calls = list(script), []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        content = self.script.pop(0) if self.script else [SimpleNamespace(type="text", text="done")]
        return SimpleNamespace(content=content)


def test_agent_uses_tools_and_returns_briefing():
    apps = [app(id=7, applied_on=date(2026, 10, 25), contact_name="Sandy Jacobson")]
    client = FakeClient([
        [block("list_actions", {}, "t1")],
        [block("save_draft", {"id": 7, "subject": "Hi", "body": "Hi Sandy"}, "t2"),
         block("propose_status_change", {"id": 7, "new_status": "Closed", "reason": "stale"}, "t3")],
        [block("submit_briefing", {"markdown": "# Briefing"}, "t4")],
    ])
    result = ChiefOfStaffAgent(apps, TODAY, client=client).run()
    assert result.briefing == "# Briefing"
    assert result.drafts[7][1] == "Hi Sandy"
    assert result.proposals[0]["new_status"] == "Closed"
    # the tool result for list_actions was sent back to the model
    sent = client.calls[1]["messages"][-1]["content"][0]
    assert sent["tool_use_id"] == "t1" and "Acme" in sent["content"]


def test_agent_reports_bad_tool_input_instead_of_crashing():
    client = FakeClient([[block("get_application", {"id": 999}, "t1")],
                         [block("submit_briefing", {"markdown": "ok"}, "t2")]])
    result = ChiefOfStaffAgent([app()], TODAY, client=client).run()
    assert result.briefing == "ok"
    assert "no such id" in client.calls[1]["messages"][-1]["content"][0]["content"]


def test_draft_limit_is_enforced():
    apps = [app(id=i, applied_on=date(2026, 10, 25)) for i in range(1, 4)]
    client = FakeClient([[block("save_draft", {"id": i, "subject": "s", "body": "b"}, f"t{i}") for i in range(1, 4)],
                         [block("submit_briefing", {"markdown": "ok"}, "t9")]])
    result = ChiefOfStaffAgent(apps, TODAY, client=client, limit=2).run()
    assert len(result.drafts) == 2
