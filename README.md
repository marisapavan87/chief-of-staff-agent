# Chief of Staff Agent

An agent that runs the operations side of my job search, so nothing stalls and I spend my time on the moves that matter.

In one month I applied to more than 20 roles. Each one came with a follow-up to time, a contact to remember, documents to tailor, and a point where it was time to let go. Tracking that by memory meant things slipped. So I built a chief of staff for it.

**Every morning it:**

1. **Triages** my application tracker and ranks what needs doing today.
2. **Flags** follow-ups that are due, second nudges, and applications gone quiet for a month.
3. **Drafts** the follow-up emails in my voice: short, warm, one proof point, no P.S.
4. **Proposes** status changes, like closing out a dead application. I approve before anything changes.
5. **Writes** a daily briefing: what to do first, what's ready to submit, and where the pipeline stands.

## How it works

```
data/applications.csv  ->  triage (rules)  ->  Claude agent with tools  ->  output/briefing.md
                                                                          ->  output/drafts/*.txt
```

- **Triage** (`cos_agent/triage.py`) uses plain rules anyone can read and change: wait 7 days before following up, nudge once more a week after that, and suggest closing out after 30 days of silence. Ready-to-submit work always comes first. A named contact moves an item up, because a follow-up to a person beats one to an inbox.
- **The agent** (`cos_agent/agent.py`) gives Claude five tools over the tracker: `list_actions`, `get_application`, `save_draft`, `propose_status_change` and `submit_briefing`. Claude decides how to use them, drafts the messages worth sending, and writes the briefing. It can't change the tracker on its own. Status changes are proposals until I run with `--apply`.
- **Offline mode** runs the same pipeline with no API key, using rule-based triage and template drafts. That way it works anywhere and the logic can be tested without paying for API calls.

## Run it

```bash
pip install anthropic pytest

python -m cos_agent                      # offline: rules and template drafts
                                         # (uses data/sample_applications.csv until you
                                         #  add your own data/applications.csv)
ANTHROPIC_API_KEY=... python -m cos_agent  # Claude agent with tools
python -m cos_agent --today 2026-11-04   # run as of a given date
python -m cos_agent --apply              # accept proposed status changes
python -m pytest                         # 10 tests, including the agent's tool loop
```

Set `COS_SIGNATURE="Your Name\n(555) 555-5555"` to sign drafts with your own details. Your real tracker (`data/applications.csv`) and the `output/` folder are git-ignored, so contacts and drafts stay private. The repository ships with a fictional sample tracker.

## Design choices

- **The human approves anything irreversible.** The agent drafts and proposes. I send and decide.
- **Rules first, model second.** Timing and priority are deterministic and tested. The model does what models are good at: judgment on wording and summarizing.
- **Honest data.** Application dates I reconstructed after the fact are marked as estimates, and the briefing says so.
- **Failures are reported, not hidden.** A bad tool call goes back to the model as an error instead of crashing the run.

## How I built it

I'm an operator, not an engineer. I built this by directing a coding agent (Claude): I described the problem the way I'd brief a new hire, set the rules for follow-up timing and tone, reviewed every output, and pushed back where it got the logic wrong. One example: an early version sent "just a second nudge" to people I'd never followed up with. The test suite now checks for that.

It's the same thing I did for 14 years running my own business. Find where work stalls, build a system so it doesn't, and hand it off so it runs without me.

Marisa Pavan · marisaangelinapavan@gmail.com
