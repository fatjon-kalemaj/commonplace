"""The sync pipeline: fetch -> normalize -> (redact) -> analyze -> index -> render -> write."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

from .. import connectors
from ..config import Config
from ..models import Analysis, Kind, Record
from ..state import SyncState
from .analyze import Analyzer
from .templates import Templates
from .writer import VaultWriter, WriteResult

FOLDERS = {
    "meeting": "Meetings", "email_thread": "Emails", "document": "Documents",
    "task": "Tasks", "session": "Sessions", "note": "Notes",
    "person": "People", "company": "Companies", "project": "Projects",
    "decision": "Decisions", "daily": "Daily",
}
ENTITY_KINDS = {"person", "company", "project", "decision"}
DATED_KINDS = {"meeting", "email_thread", "session", "note"}
BAD_CHARS = re.compile(r'[\[\]#^|\\/:*?"<>]')


@dataclass
class Report:
    fetched: int = 0
    analyzed: int = 0
    skipped_unchanged: int = 0
    failed: list[str] = field(default_factory=list)
    writes: list[WriteResult] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for w in self.writes:
            out[w.status] = out.get(w.status, 0) + 1
        return out


def note_name(text: str) -> str:
    text = BAD_CHARS.sub("", text).strip().strip(".")
    return re.sub(r"\s+", " ", text)[:120] or "Untitled"


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def link(name: str | None) -> str | None:
    return f"[[{name}]]" if name else None


class Index:
    """Entity index kept in state.entities. Every contribution is keyed by the
    record id that produced it, so re-analyzing a record replaces its
    contributions instead of adding duplicates."""

    def __init__(self, entities: dict[str, dict[str, Any]], config: Config) -> None:
        self.e = entities
        self.config = config
        self.touched: set[str] = set()
        self._alias: dict[str, str] = {}
        for p in config.known.people:
            for n in [p.name, *p.aliases, *([p.email] if p.email else [])]:
                self._alias[n.lower()] = p.name
        for kind, table in (("company", config.known.companies), ("project", config.known.projects)):
            for name, aliases in table.items():
                for n in [name, *aliases]:
                    self._alias[f"{kind}:{n.lower()}"] = name
        for ent in entities.values():
            if ent["kind"] == "person" and ent.get("email"):
                self._alias.setdefault(ent["email"].lower(), ent["name"])

    def canonical(self, kind: str, name: str, email: str | None = None) -> str:
        if kind == "person":
            for k in (email or "", name):
                if k and k.lower() in self._alias:
                    return self._alias[k.lower()]
            return name.strip()
        return self._alias.get(f"{kind}:{name.lower()}", name.strip())

    def entity(self, kind: str, name: str) -> dict[str, Any]:
        name = note_name(name)
        key = f"{kind}:{slug(name)}"
        ent = self.e.setdefault(key, {"kind": kind, "name": name, "mentions": {}, "links": {},
                                      "tasks": {}, "decisions": {}})
        self.touched.add(key)
        return ent

    def forget(self, rid: str) -> None:
        for key, ent in self.e.items():
            changed = False
            for bucket in ("mentions", "links", "tasks", "decisions"):
                if rid in ent.get(bucket, {}):
                    del ent[bucket][rid]
                    changed = True
            if ent.get("overview_from") == rid:
                ent.pop("overview", None)
                ent.pop("overview_from", None)
                changed = True
            if changed:
                self.touched.add(key)

    def add(self, rid: str, rec: dict[str, Any], a: Analysis) -> None:
        mention = {"note": rec["note"], "date": rec["date"], "kind": a.kind.value}
        people = []
        for ref in a.people:
            name = self.canonical("person", ref.name, ref.email)
            ent = self.entity("person", name)
            known = next((p for p in self.config.known.people if p.name == name), None)
            for attr in ("email", "company", "role"):
                value = getattr(known, attr, None) if known else None
                value = value or getattr(ref, attr)
                if value and attr == "company":
                    value = self.canonical("company", value)
                if value and not ent.get(attr):
                    ent[attr] = value
            ent["mentions"][rid] = mention
            people.append(ent["name"])
        companies = [self.entity("company", self.canonical("company", c))["name"] for c in a.companies]
        for p in people:
            comp = self.e[f"person:{slug(p)}"].get("company")
            if comp and note_name(comp) not in companies:
                companies.append(self.entity("company", comp)["name"])
        projects = [self.entity("project", self.canonical("project", p))["name"] for p in a.projects]
        for c in companies:
            ent = self.entity("company", c)
            ent["mentions"][rid] = mention
            ent["links"][rid] = {"people": [p for p in people if self.e[f"person:{slug(p)}"].get("company") == c],
                                 "projects": projects}
        for p in projects:
            ent = self.entity("project", p)
            ent["mentions"][rid] = mention
            ent["links"][rid] = {"people": people, "companies": companies}
        for i, t in enumerate(a.tasks):
            owner = self.canonical("person", t.owner) if t.owner else None
            if owner:
                owner = self.entity("person", owner)["name"]
            task = {"text": t.text, "owner": owner, "due": t.due, "note": rec["note"]}
            targets = [f"person:{slug(owner)}"] if owner else []
            targets += [f"project:{slug(p)}" for p in projects]
            if t.due:
                targets.append(f"daily:{t.due}")
                self.entity("daily", t.due)
            for key in targets:
                if key in self.e:
                    self.e[key]["tasks"].setdefault(rid, []).append(task)
                    self.touched.add(key)
        decisions = []
        for d in a.decisions:
            owner = self.canonical("person", d.owner) if d.owner else None
            ent = self.entity("decision", d.title)
            ent.update({"date": rec["date"], "owner": owner, "source_note": rec["note"],
                        "projects": projects})
            ent["overview"] = d.rationale or f"Recorded in [[{rec['note']}]]."
            ent["overview_from"] = rid
            ent["mentions"][rid] = mention
            decisions.append(ent["name"])
            for key in ([f"person:{slug(owner)}"] if owner else []) + [f"project:{slug(p)}" for p in projects]:
                if key in self.e:
                    self.e[key]["decisions"][rid] = sorted(set(self.e[key]["decisions"].get(rid, []) + [ent["name"]]))
                    self.touched.add(key)
        if rec["date"]:
            self.entity("daily", rec["date"])["mentions"][rid] = mention
        rec["people"], rec["companies"], rec["projects"], rec["decisions"] = people, companies, projects, decisions


def bullet(items: list[str], empty: str = "_None._") -> str:
    return "\n".join(f"- {i}" for i in items) if items else empty


def task_line(t: dict[str, Any], with_source: bool = True) -> str:
    bits = [f"- [ ] {t['text']}"]
    if t.get("owner"):
        bits.append(f"[[{t['owner']}]]")
    if t.get("due"):
        bits.append(f"(due {t['due']})")
    if with_source:
        bits.append(f"(from [[{t['note']}]])")
    return " ".join(bits)


def callout(title: str, body: str) -> str:
    if not body.strip():
        return ""
    quoted = "\n".join("> " + line if line else ">" for line in body.strip().splitlines())
    return f"> [!quote]- {title}\n{quoted}"


class Pipeline:
    def __init__(self, config: Config, analyzer: Analyzer, dry_run: bool = False,
                 log: Callable[[str], None] = print, templates: Templates | None = None) -> None:
        self.config = config
        self.analyzer = analyzer
        self.dry_run = dry_run
        self.log = log
        self.templates = templates or Templates()
        self.state = SyncState.load(config.vault)
        self.index = Index(self.state.entities, config)
        self.writer = VaultWriter(config.vault, self.state.notes, dry_run=dry_run)

    # -- collect -------------------------------------------------------------
    def collect(self, only: list[str] | None = None, limit: int | None = None
                ) -> tuple[list[Record], dict[str, str | None]]:
        records: list[Record] = []
        cursors: dict[str, str | None] = {}
        for name, opts in self.config.connectors.items():
            if not opts.get("enabled", True) or (only and name not in only):
                continue
            conn = connectors.build(name, opts)
            recs, cursor = conn.records(self.state.cursors.get(name))
            self.log(f"  {name}: {len(recs)} new or changed records")
            records += recs
            cursors[name] = cursor
        records.sort(key=lambda r: r.created_at)
        if limit is not None:
            records = records[:limit]
        return records, cursors

    # -- run -----------------------------------------------------------------
    def run(self, records: list[Record], cursors: dict[str, str | None]) -> Report:
        report = Report(fetched=len(records))
        bodies: dict[str, Record] = {}
        for r in records:
            if len(r.body) > self.config.max_record_chars:
                report.failed.append(f"{r.id}: {len(r.body)} chars exceeds max_record_chars")
                continue
            h = r.content_hash()
            prev = self.state.records.get(r.id)
            if prev and prev.get("hash") == h:
                report.skipped_unchanged += 1
                continue
            if self.config.redactor.for_vault:
                r = r.model_copy(update={"body": self.config.redactor.redact(r.body),
                                         "title": self.config.redactor.redact(r.title)})
            try:
                analysis = self.analyzer.analyze(r, self.config.known)
            except Exception as exc:  # one bad record must not stop the sync
                report.failed.append(f"{r.id}: {exc}")
                continue
            report.analyzed += 1
            rec = self._record_entry(r, analysis, prev, h)
            self.index.forget(r.id)
            self.index.add(r.id, rec, analysis)
            if analysis.kind.value in ENTITY_KINDS:
                ent = self.index.entity(analysis.kind.value, self.index.canonical(analysis.kind.value, analysis.title))
                body = r.body.strip()
                ent["overview"] = body if analysis.summary.strip() in body else f"{analysis.summary}\n\n{body}"
                ent["overview_from"] = r.id
                if analysis.kind == Kind.decision:
                    ent.update({"date": rec["date"], "source_note": None, "projects": rec["projects"]})
            self.state.records[r.id] = rec
            bodies[r.id] = r

        for rid, r in bodies.items():
            rec = self.state.records[rid]
            if rec["kind"] in ENTITY_KINDS:
                continue
            fm, body = self.templates.render(rec["kind"], self._record_ctx(rec, r))
            report.writes.append(self.writer.write(rec["path"], rid, fm, body))
        for key in sorted(self.index.touched):
            ent = self.state.entities.get(key)
            if ent is None:
                continue
            fm, body = self.templates.render(ent["kind"], self._entity_ctx(ent))
            path = f"{FOLDERS[ent['kind']]}/{ent['name']}.md"
            report.writes.append(self.writer.write(path, key, fm, body))

        if not self.dry_run:
            for name, cursor in cursors.items():
                if cursor:
                    self.state.cursors[name] = cursor
            self.state.save()
        return report

    def _record_entry(self, r: Record, a: Analysis, prev: dict[str, Any] | None, h: str) -> dict[str, Any]:
        kind = a.kind.value
        day = r.created_at.date().isoformat()
        if prev and prev.get("kind") == kind and prev.get("path"):
            path, note = prev["path"], prev["note"]
        else:
            base = note_name(f"{day} {a.title}" if kind in DATED_KINDS else a.title)
            if kind in ENTITY_KINDS:
                base = note_name(self.index.canonical(kind, a.title))
            note = base
            taken = {v["note"] for k, v in self.state.records.items() if k != r.id}
            if note in taken and kind not in ENTITY_KINDS:
                note = f"{base} ({slug(r.id)[-6:]})"
            path = f"{FOLDERS[kind]}/{note}.md"
        return {"hash": h, "kind": kind, "title": a.title, "note": note, "path": path,
                "date": day, "source": r.source, "url": r.url, "summary": a.summary,
                "tasks": [t.model_dump() for t in a.tasks], "topics": a.topics,
                "analysis": a.model_dump(mode="json")}

    def _record_ctx(self, rec: dict[str, Any], r: Record) -> dict[str, Any]:
        tasks = [{**t, "owner": self.index.canonical("person", t["owner"]) if t.get("owner") else None,
                  "note": rec["note"]} for t in rec["tasks"]]
        related = [f"[[{p}]]" for p in rec["projects"]] + [f"[[{c}]]" for c in rec["companies"]]
        related.append(f"[[{rec['date']}]]")
        label = {"meeting": "Transcript", "email_thread": "Email thread",
                 "session": "Session transcript"}.get(rec["kind"], "Source text")
        return {
            "title": rec["title"], "kind": rec["kind"], "date": rec["date"], "summary": rec["summary"],
            "source": rec["source"], "url": rec["url"],
            "tags": sorted({rec["kind"].replace("_", "-"), *rec["topics"]}),
            "people_links": [link(p) for p in rec["people"]],
            "company_links": [link(c) for c in rec["companies"]],
            "project_links": [link(p) for p in rec["projects"]],
            "people_list": bullet([f"[[{p}]]" for p in rec["people"]]),
            "decisions_list": bullet([f"[[{d}]]" for d in rec["decisions"]]),
            "tasks_list": "\n".join(task_line(t, with_source=False) for t in tasks) or "_None._",
            "related_list": bullet(related),
            "body_callout": callout(label, r.body),
        }

    def _entity_ctx(self, ent: dict[str, Any]) -> dict[str, Any]:
        mentions = sorted((m for m in ent["mentions"].values() if m["note"] != ent["name"]), key=lambda m: (m["date"], m["note"]), reverse=True)
        mentions_list = bullet([f"[[{m['note']}]] ({m['kind'].replace('_', ' ')}, {m['date']})" for m in mentions])
        tasks = [t for ts in ent["tasks"].values() for t in ts]
        decisions = sorted({d for ds in ent["decisions"].values() for d in ds})
        people = sorted({p for l in ent["links"].values() for p in l.get("people", [])})
        companies = sorted({c for l in ent["links"].values() for c in l.get("companies", [])})
        projects = sorted({p for l in ent["links"].values() for p in l.get("projects", [])})
        ctx = {
            "name": ent["name"], "date": ent.get("date") or (ent["name"] if ent["kind"] == "daily" else None),
            "email": ent.get("email"), "role": ent.get("role"),
            "company_link": link(ent.get("company")),
            "headline": ", ".join(x for x in (ent.get("role"), f"[[{ent['company']}]]" if ent.get("company") else None) if x)
                        or "_No role recorded yet._",
            "overview": ent.get("overview") or "_No overview yet. Add your own notes below the managed block._",
            "mentions_list": mentions_list,
            "tasks_list": "\n".join(task_line(t) for t in tasks) or "_None._",
            "decisions_list": bullet([f"[[{d}]]" for d in decisions]),
            "people_links": [link(p) for p in people], "people_list": bullet([f"[[{p}]]" for p in people]),
            "company_links": [link(c) for c in companies], "company_list": bullet([f"[[{c}]]" for c in companies]),
            "project_links": [link(p) for p in (ent.get("projects") or projects)],
            "project_list": bullet([f"[[{p}]]" for p in projects]),
            "owner_link": link(ent.get("owner")), "owner_text": f"[[{ent['owner']}]]" if ent.get("owner") else "_Unassigned._",
            "source_link": link(ent.get("source_note")),
            "source_text": f"[[{ent['source_note']}]]" if ent.get("source_note") else "_Standalone record._",
        }
        return ctx
