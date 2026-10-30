"""Generate the synthetic Tallgrass Labs dataset in demo/data.

Tallgrass Labs is an invented nine-person company that builds AI tools for
lenders and investment firms. Its clients, vendor, people, email domains
(.example), phone numbers and figures are all made up. Any resemblance to a
real company or person is coincidental.

The output is deterministic, so re-running this script produces identical
files. Run: uv run python demo/generate_demo_data.py
"""

from __future__ import annotations

import json
import shutil
import uuid
from email.message import EmailMessage
from email.utils import format_datetime
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent / "data"
NS = uuid.UUID("6f1c2a52-0000-4000-8000-000000000000")


def uid(name: str) -> str:
    return str(uuid.uuid5(NS, name))


def ts(day: str, hm: str = "10:00") -> datetime:
    return datetime.fromisoformat(f"{day}T{hm}:00+00:00")


# --------------------------------------------------------------------------
# Meeting transcripts: Fireflies JSON exports
# --------------------------------------------------------------------------

FIREFLIES = [
    {
        "file": "2026-09-08-copperline-kickoff.json",
        "title": "Copperline kickoff",
        "date": "2026-09-08T14:00:00Z",
        "duration": 48,
        "participants": ["maya@tallgrass.example", "lena@tallgrass.example",
                         "rob.castellano@copperline.example", "jen.albright@copperline.example"],
        "sentences": [
            ("Maya", "Thanks for making time. The goal today is to agree the scope of the Underwriting Copilot pilot."),
            ("Rob", "Our analysts spend about two days per small business file pulling numbers out of tax returns and bank statements. We want that under half a day."),
            ("Jen", "Credit risk needs every extracted figure to point back to the page it came from. Without that the committee will not accept it."),
            ("Lena", "That matches how we built it. Every field carries a citation to the source page."),
            ("Rob", "Which loan types do you want to start with?"),
            ("Lena", "SBA files are the most uniform, so the error rate will be easiest to measure."),
            ("Lena", "Decision: the pilot starts with SBA 7(a) loan files only, commercial real estate later."),
            ("Jen", "I can pull a sample of forty anonymized files. We strip borrower names before anything leaves our system."),
            ("Maya", "Good. Sam will stand up the Data Room Ingest pipeline on our side so the files land in a separate tenant."),
            ("Rob", "Let's review results in five weeks."),
        ],
        "action_items": "- [ ] Jen to share 40 anonymized SBA loan files by 2026-09-15\n"
                        "- [ ] Sam to set up the Data Room Ingest tenant for Copperline by 2026-09-12\n"
                        "- [ ] Lena to draft the pilot success metrics by 2026-09-11",
    },
    {
        "file": "2026-09-16-weekly-delivery-sync.json",
        "title": "Weekly delivery sync",
        "date": "2026-09-16T15:30:00Z",
        "duration": 31,
        "participants": ["lena@tallgrass.example", "dev@tallgrass.example",
                         "sam@tallgrass.example", "priya@tallgrass.example"],
        "sentences": [
            ("Lena", "Copperline files arrived yesterday. Sam, how is ingest looking?"),
            ("Sam", "Thirty-eight of forty parsed cleanly. Two are scanned faxes and need OCR tuning."),
            ("Dev", "For Covenant Monitor we still need a feed of covenant terms. Building our own scraper is weeks of work."),
            ("Dev", "Decision: we license covenant data from Ostrander Data instead of building a scraper."),
            ("Priya", "Harbor & Vine will ask about SOC 2 the moment we get serious. I'd like to start evidence collection now."),
            ("Lena", "Agreed. Let's treat SOC 2 Readiness as its own project with a weekly check-in."),
        ],
        "action_items": "- [ ] Priya to start SOC 2 evidence collection by 2026-10-01\n"
                        "- [ ] Sam to build an evaluation harness for extraction accuracy by 2026-09-25\n"
                        "- [ ] Dev to get pricing from Ostrander Data by 2026-09-24",
    },
    {
        "file": "2026-10-14-copperline-pilot-review.json",
        "title": "Copperline pilot review",
        "date": "2026-10-14T14:00:00Z",
        "duration": 55,
        "participants": ["lena@tallgrass.example", "sam@tallgrass.example",
                         "rob.castellano@copperline.example", "jen.albright@copperline.example"],
        "sentences": [
            ("Lena", "Over five weeks the copilot processed all forty SBA files."),
            ("Sam", "Field-level accuracy was 96.8 percent against Jen's hand-checked set, and every field had a page citation."),
            ("Jen", "The citations are what made the review fast. My team checked a file in about forty minutes."),
            ("Rob", "That is the number I needed. I want to try commercial real estate next."),
            ("Rob", "Decision: extend the Underwriting Copilot pilot to commercial real estate files in November."),
            ("Lena", "We'll need rent rolls and operating statements. Different layout, so expect a week of tuning."),
        ],
        "action_items": "- [ ] Jen to send 20 sample CRE files by 2026-10-28\n"
                        "- [ ] Sam to add rent roll parsing to the Underwriting Copilot by 2026-11-07\n"
                        "- [ ] Lena to send the pilot results summary to Rob by 2026-10-17",
    },
]

# --------------------------------------------------------------------------
# Meeting notes: Granola Markdown exports
# --------------------------------------------------------------------------

GRANOLA = {
    "2026-09-22-harbor-vine-intro.md": """---
title: Harbor & Vine intro
date: 2026-09-22
attendees: [Maya Okafor, Theo Marchetti, Aisha Bello]
---
# Harbor & Vine intro

## Notes
- Theo runs a mid-market private equity fund with 14 portfolio companies; lenders send monthly compliance certificates.
- Aisha's team tracks covenant headroom in spreadsheets and misses breaches until quarter end.
- They want an early warning when any portfolio company gets within 10 percent of a covenant threshold.
- Covenant Monitor is a direct fit. Maya walked through the Copperline pilot as a reference.
- Aisha asked whether we hold SOC 2. Maya said we are in progress.

## Next steps
- [ ] Maya to send a proposal for Covenant Monitor by 2026-09-29
- [ ] Aisha to share two redacted compliance certificates by 2026-09-26
""",
    "2026-09-24-ostrander-pricing-call.md": """---
title: Ostrander Data pricing call
date: 2026-09-24
attendees: [Dev Raman, Kurt Lindqvist]
---
# Ostrander Data pricing call

- Kurt walked through the covenant terms dataset: 9,000 private credit agreements, updated weekly.
- Delivery is a REST API with a nightly bulk export.
- Dev pushed for a startup price and a 12-month term with no auto-renewal.
- Decision: sign a 12-month Ostrander Data license with no auto-renewal (owner: Dev Raman)
- [ ] Kurt to send the order form by 2026-09-30
- [ ] Dev to confirm API rate limits with Kurt by 2026-10-02
""",
}

# --------------------------------------------------------------------------
# Voice notes: Wispr Flow dictation (plain text)
# --------------------------------------------------------------------------

WISPR = {
    "2026-09-22-thoughts-after-harbor-vine.txt": """Thoughts after the Harbor & Vine call
Theo and Aisha are a better fit than I expected. They do not want a dashboard, they want an alert in their inbox when a company drifts toward a covenant. That is a smaller build than Covenant Monitor as scoped. I think we ship alerts first and the dashboard later.
SOC 2 came up again. Second prospect in a month. Priya is right that we need to start now.
Ask Dev whether the Ostrander feed covers the lenders Harbor & Vine's companies borrow from.
""",
    "2026-09-30-soc2-scoping.txt": """SOC 2 scoping notes
Type 1 first, then Type 2 after a three-month observation window. Scope is the production environment for Underwriting Copilot and Covenant Monitor. Out of scope for now: the internal analytics database.
Policies to write: access control, change management, incident response, vendor management. Ostrander Data goes on the vendor list.
Auditor shortlist is three firms. I'll send it to Maya and Dev this week.
""",
}

# --------------------------------------------------------------------------
# Email threads: one .eml per thread, replies quoted
# --------------------------------------------------------------------------

EMAILS = [
    {
        "file": "2026-09-12-loan-file-sample.eml",
        "subject": "Re: Loan file sample for the pilot",
        "from": ("Jen Albright", "jen.albright@copperline.example"),
        "to": [("Lena Fischer", "lena@tallgrass.example")],
        "cc": [("Rob Castellano", "rob.castellano@copperline.example"), ("Sam Whitlock", "sam@tallgrass.example")],
        "date": ts("2026-09-12", "16:20"),
        "body": """Lena,

The 40 SBA files are uploaded to the Data Room Ingest tenant. Borrower names, tax IDs and account numbers are masked. Two of them are scanned faxes, sorry about the quality.

If anything does not parse, call me on +1 555 014 2297.

Jen

On Sep 11, 2026, Lena Fischer wrote:
> Hi Jen, the ingest tenant is ready. Upload link is in the shared folder. We only need
> tax returns, bank statements and the SBA Form 1919 for each file.
""",
    },
    {
        "file": "2026-09-29-covenant-monitor-proposal.eml",
        "subject": "Re: Proposal: Covenant Monitor for Harbor & Vine",
        "from": ("Theo Marchetti", "theo@harborvine.example"),
        "to": [("Maya Okafor", "maya@tallgrass.example")],
        "cc": [("Aisha Bello", "aisha@harborvine.example")],
        "date": ts("2026-09-30", "09:05"),
        "body": """Maya,

Thanks for the proposal. Alerts-first is the right call. Aisha will be the day-to-day owner on our side.

Two questions before we sign: can the alert thresholds be set per covenant, and when do you expect the SOC 2 Type 1 report?

Theo

On Sep 29, 2026, Maya Okafor wrote:
> Theo, Aisha, attached is the proposal for Covenant Monitor. Phase one is email alerts when a
> portfolio company comes within a set margin of any covenant, built on the Ostrander Data feed.
> Phase two adds the portfolio dashboard. Fixed fee for phase one, eight weeks.
""",
    },
    {
        "file": "2026-09-30-ostrander-final-terms.eml",
        "subject": "Ostrander data license - final terms",
        "from": ("Kurt Lindqvist", "kurt@ostrander.example"),
        "to": [("Dev Raman", "dev@tallgrass.example")],
        "cc": [],
        "date": ts("2026-09-30", "18:40"),
        "body": """Dev,

Order form attached: 12-month term, no auto-renewal, API plus nightly bulk export, 60 requests per minute.

Signed copy back by Friday and I can provision keys Monday.

Kurt Lindqvist
Ostrander Data
""",
    },
    {
        "file": "2026-10-02-soc2-auditor-shortlist.eml",
        "subject": "SOC 2 auditor shortlist",
        "from": ("Priya Nair", "priya@tallgrass.example"),
        "to": [("Maya Okafor", "maya@tallgrass.example"), ("Dev Raman", "dev@tallgrass.example")],
        "cc": [],
        "date": ts("2026-10-02", "11:15"),
        "body": """Maya, Dev,

Three auditors for SOC 2 Readiness, all with startup packages. My pick is the second one: they accept evidence from our existing ticketing and do Type 1 in six weeks.

Decision needed from you two by 2026-10-09 so we can start the observation window in November.

- [ ] Maya and Dev to choose the SOC 2 auditor by 2026-10-09

Priya
""",
    },
    {
        "file": "2026-10-09-pilot-metrics-week-4.eml",
        "subject": "Pilot metrics for week 4",
        "from": ("Sam Whitlock", "sam@tallgrass.example"),
        "to": [("Lena Fischer", "lena@tallgrass.example"), ("Rob Castellano", "rob.castellano@copperline.example")],
        "cc": [("Jen Albright", "jen.albright@copperline.example")],
        "date": ts("2026-10-09", "17:00"),
        "body": """Lena, Rob,

Week 4 numbers for the Underwriting Copilot pilot:

- Files processed: 40 of 40
- Field accuracy against Jen's checked set: 96.8%
- Median analyst review time per file: 41 minutes, down from about two days
- Fields without a page citation: 0

The two fax files now parse after the OCR change. Full table in the pilot folder.

Sam
""",
    },
]

# --------------------------------------------------------------------------
# Notion: recorded API responses (search + block children)
# --------------------------------------------------------------------------


def rich(text: str) -> list[dict]:
    return [{"type": "text", "plain_text": text, "text": {"content": text}}]


def block(kind: str, text: str = "", **extra) -> dict:
    data = {"rich_text": rich(text)} if kind not in {"divider"} else {}
    data.update(extra)
    return {"object": "block", "id": uid(f"block:{kind}:{text}"), "type": kind,
            "has_children": False, kind: data}


def person(name: str, email: str) -> dict:
    return {"object": "user", "id": uid(f"user:{email}"), "name": name, "type": "person",
            "person": {"email": email}}


NOTION_PAGES = [
    {
        "key": "underwriting-copilot",
        "title": "Underwriting Copilot",
        "type": "Project",
        "created": "2026-08-20T09:00:00.000Z",
        "edited": "2026-10-15T08:30:00.000Z",
        "people": [("Lena Fischer", "lena@tallgrass.example"), ("Sam Whitlock", "sam@tallgrass.example")],
        "blocks": [
            block("paragraph", "Extracts figures from loan files and cites the source page for every field. First client: Copperline Credit."),
            block("heading_2", "Status"),
            block("paragraph", "SBA pilot complete at 96.8% field accuracy. Commercial real estate extension starts in November."),
            block("heading_2", "Components"),
            block("bulleted_list_item", "Data Room Ingest: per-client tenant, OCR, document classification"),
            block("bulleted_list_item", "Extraction: Claude with structured outputs, page citations"),
            block("bulleted_list_item", "Review UI for credit analysts"),
            block("heading_2", "Open work"),
            block("to_do", "Rent roll parser (owner: Sam Whitlock)", checked=False),
            block("to_do", "Evaluation harness", checked=True),
        ],
    },
    {
        "key": "covenant-monitor",
        "title": "Covenant Monitor",
        "type": "Project",
        "created": "2026-09-01T09:00:00.000Z",
        "edited": "2026-10-01T12:00:00.000Z",
        "people": [("Dev Raman", "dev@tallgrass.example"), ("Maya Okafor", "maya@tallgrass.example")],
        "blocks": [
            block("paragraph", "Watches portfolio company covenants and alerts before a breach. Prospect: Harbor & Vine Partners."),
            block("heading_2", "Plan"),
            block("numbered_list_item", "Phase one: email alerts on covenant headroom, built on the Ostrander Data feed"),
            block("numbered_list_item", "Phase two: portfolio dashboard"),
            block("callout", "Thresholds must be configurable per covenant (asked by Theo Marchetti)."),
        ],
    },
    {
        "key": "decision-postgres",
        "title": "Decision: Postgres is the system of record for extracted fields",
        "type": "Decision",
        "created": "2026-09-18T10:00:00.000Z",
        "edited": "2026-09-18T10:45:00.000Z",
        "people": [("Dev Raman", "dev@tallgrass.example")],
        "blocks": [
            block("paragraph", "Extracted fields, citations and reviewer corrections for Underwriting Copilot are stored in Postgres, not in the document store."),
            block("heading_3", "Why"),
            block("bulleted_list_item", "Reviewer corrections need transactions and an audit trail"),
            block("bulleted_list_item", "SOC 2 Readiness is simpler with one system of record"),
            block("paragraph", "Owner: Dev Raman. Revisit if we pass 10 million fields."),
        ],
    },
    {
        "key": "engineering-onboarding",
        "title": "Engineering onboarding",
        "type": "Document",
        "created": "2026-07-01T09:00:00.000Z",
        "edited": "2026-09-05T16:00:00.000Z",
        "people": [("Dev Raman", "dev@tallgrass.example")],
        "blocks": [
            block("paragraph", "Welcome to Tallgrass Labs. Read this in your first week."),
            block("heading_2", "Week one"),
            block("to_do", "Get access to the Underwriting Copilot and Covenant Monitor repos", checked=False),
            block("to_do", "Read the SOC 2 policies once Priya Nair publishes them", checked=False),
            block("heading_2", "How we work"),
            block("paragraph", "Every client gets its own Data Room Ingest tenant. Never copy client files to laptops."),
        ],
    },
]


def notion_search() -> dict:
    results = []
    for p in sorted(NOTION_PAGES, key=lambda p: p["edited"], reverse=True):
        results.append({
            "object": "page",
            "id": uid(f"page:{p['key']}"),
            "created_time": p["created"],
            "last_edited_time": p["edited"],
            "archived": False,
            "url": f"https://www.notion.so/tallgrass-demo/{p['key']}",
            "properties": {
                "Name": {"id": "title", "type": "title", "title": rich(p["title"])},
                "Type": {"id": "type", "type": "select", "select": {"name": p["type"]}},
                "Owners": {"id": "own", "type": "people", "people": [person(n, e) for n, e in p["people"]]},
            },
        })
    return {"object": "list", "results": results, "has_more": False, "next_cursor": None}


# --------------------------------------------------------------------------
# Claude Code sessions: ~/.claude/projects/<project>/<session>.jsonl
# --------------------------------------------------------------------------

SESSIONS = [
    {
        "project": "-Users-demo-code-underwriting-copilot",
        "cwd": "/Users/demo/code/underwriting-copilot",
        "branch": "feat/form-1919",
        "start": "2026-09-19T13:02:00Z",
        "summary": "Add a parser for SBA Form 1919 fields",
        "turns": [
            ("user", "Add a parser for SBA Form 1919 to the Underwriting Copilot extraction step. Copperline Credit needs the ownership table and the loan purpose fields, each with a page citation."),
            ("assistant", "I'll add a `form_1919.py` extractor next to the existing tax return extractor, reuse the citation model, and add fixtures from the anonymized sample. Plan:\n1. Define the schema for owners and loan purpose.\n2. Call Claude with structured outputs against the page images.\n3. Attach page numbers to each field.\n4. Add tests."),
            ("user", "Good. Keep the masked fields masked, don't try to recover them."),
            ("assistant", "Understood. Masked values stay as the literal mask string and are flagged `masked: true` so reviewers see why they are empty. Tests pass: 14 new, 0 failing."),
        ],
    },
    {
        "project": "-Users-demo-code-covenant-monitor",
        "cwd": "/Users/demo/code/covenant-monitor",
        "branch": "main",
        "start": "2026-10-05T10:15:00Z",
        "summary": "Write the Ostrander covenant feed client",
        "turns": [
            ("user", "Write a client for the Ostrander Data covenant API for Covenant Monitor. 60 requests per minute limit, nightly bulk export as a fallback."),
            ("assistant", "I'll write `ostrander_client.py` with a token-bucket limiter at 60/min, paginated fetch of covenant terms, and a bulk-export loader that reads the nightly file when the API is unavailable. Credentials come from the environment."),
            ("user", "Add retries with backoff on 429."),
            ("assistant", "Added exponential backoff with jitter on 429 and 5xx, max five attempts. Also added a test that simulates a 429 burst."),
        ],
    },
    {
        "project": "-Users-demo-code-ops",
        "cwd": "/Users/demo/code/ops",
        "branch": "main",
        "start": "2026-10-13T08:40:00Z",
        "summary": "Draft the Copperline pilot review agenda",
        "turns": [
            ("user", "Draft an agenda for tomorrow's Copperline pilot review with Rob Castellano and Jen Albright. Use Sam's week 4 metrics."),
            ("assistant", "Agenda:\n1. Results: 40 of 40 files, 96.8% field accuracy, 41 minute median review.\n2. What made review faster: page citations.\n3. Failure cases: the two fax files and the OCR fix.\n4. Next scope: commercial real estate.\n5. Commercial terms for the extension."),
        ],
    },
]


def session_lines(s: dict) -> list[str]:
    sid = uid(f"session:{s['summary']}")
    t0 = datetime.fromisoformat(s["start"].replace("Z", "+00:00"))
    lines = [json.dumps({"type": "summary", "summary": s["summary"], "leafUuid": uid(sid + "leaf")})]
    parent = None
    for i, (role, text) in enumerate(s["turns"]):
        msg_id = uid(f"{sid}:{i}")
        stamp = t0.replace(minute=(t0.minute + i * 3) % 60).isoformat().replace("+00:00", "Z")
        content = text if role == "user" else [{"type": "text", "text": text}]
        lines.append(json.dumps({
            "type": role, "uuid": msg_id, "parentUuid": parent, "sessionId": sid,
            "timestamp": stamp, "cwd": s["cwd"], "gitBranch": s["branch"], "isSidechain": False,
            "message": {"role": role, "content": content},
        }))
        parent = msg_id
    return lines


# --------------------------------------------------------------------------
# Plain folder: internal docs
# --------------------------------------------------------------------------

DOCS = {
    "q4-priorities.md": """---
title: Q4 priorities
date: 2026-10-01
type: document
---
# Q4 priorities

Written by Maya Okafor for the whole team.

1. Convert the Copperline Credit pilot into an annual contract and start commercial real estate.
2. Sign Harbor & Vine Partners for Covenant Monitor phase one.
3. Finish SOC 2 Readiness Type 1 by the end of December.

Decision: no new client pilots until SOC 2 Type 1 is done (owner: Maya Okafor)
""",
    "how-we-work.md": """---
title: How we work
date: 2026-08-15
type: document
---
# How we work

Tallgrass Labs is nine people. We write decisions down in Notion, record client meetings, and keep a Claude Code session log per repo.

- Client data stays in the client's Data Room Ingest tenant.
- Every extracted number cites its source page.
- Lena Fischer owns delivery; Dev Raman owns the platform; Priya Nair owns security and vendors.
""",
}


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    meetings = OUT / "meetings"
    meetings.mkdir(parents=True)
    for m in FIREFLIES:
        (meetings / m["file"]).write_text(json.dumps({
            "title": m["title"], "date": m["date"], "duration": m["duration"],
            "participants": m["participants"],
            "sentences": [{"speaker_name": who, "text": text} for who, text in m["sentences"]],
            "summary": {"action_items": m["action_items"]},
        }, indent=2) + "\n")
    for name, text in GRANOLA.items():
        (meetings / name).write_text(text)
    for name, text in WISPR.items():
        (meetings / name).write_text(text)

    mail = OUT / "mail"
    mail.mkdir()
    for e in EMAILS:
        msg = EmailMessage()
        msg["Subject"] = e["subject"]
        msg["From"] = f"{e['from'][0]} <{e['from'][1]}>"
        msg["To"] = ", ".join(f"{n} <{a}>" for n, a in e["to"])
        if e["cc"]:
            msg["Cc"] = ", ".join(f"{n} <{a}>" for n, a in e["cc"])
        msg["Date"] = format_datetime(e["date"])
        msg["Message-ID"] = f"<{uid(e['file'])}@demo.example>"
        msg.set_content(e["body"])
        (mail / e["file"]).write_bytes(bytes(msg))

    notion = OUT / "notion"
    (notion / "blocks").mkdir(parents=True)
    (notion / "search.json").write_text(json.dumps(notion_search(), indent=2) + "\n")
    for p in NOTION_PAGES:
        (notion / "blocks" / f"{uid('page:' + p['key'])}.json").write_text(
            json.dumps({"object": "list", "results": p["blocks"], "has_more": False}, indent=2) + "\n")

    for s in SESSIONS:
        d = OUT / "claude-projects" / s["project"]
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{uid('session:' + s['summary'])}.jsonl").write_text("\n".join(session_lines(s)) + "\n")

    docs = OUT / "docs"
    docs.mkdir()
    for name, text in DOCS.items():
        (docs / name).write_text(text)

    print(f"Wrote synthetic data to {OUT}")


if __name__ == "__main__":
    main()
