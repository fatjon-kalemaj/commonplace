"""Command line entry point."""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

from . import __version__, connectors
from .config import DEFAULT_CONFIG_PATH, Config
from .paths import UnsafeVaultPath
from .pipeline.analyze import ClaudeAnalyzer, OfflineAnalyzer
from .pipeline.run import Pipeline, Report
from .secrets import has_secret, set_secret


def _print_report(report: Report, dry_run: bool) -> None:
    verb = "Would write" if dry_run else "Wrote"
    print(f"\nRecords: {report.fetched} fetched, {report.analyzed} analyzed, "
          f"{report.skipped_unchanged} unchanged")
    counts = report.counts()
    print(f"{verb}: " + (", ".join(f"{n} {k}" for k, n in sorted(counts.items())) or "nothing"))
    for w in report.writes:
        if w.status == "edited":
            print(f"  kept your edits: {w.path} (proposed update in .commonplace/pending/)")
        elif w.status == "foreign":
            print(f"  skipped, not created by commonplace: {w.path}")
        elif dry_run and w.status in {"created", "updated"}:
            print(f"  {w.status:8} {w.path}")
    for f in report.failed:
        print(f"  failed: {f}", file=sys.stderr)


def cmd_demo(args: argparse.Namespace) -> int:
    from .demo import DEFAULT_DEMO_VAULT, demo_config, write_obsidian_settings

    vault = Path(args.vault or DEFAULT_DEMO_VAULT).expanduser()
    config = demo_config(vault)
    print(f"Building the offline demo vault at {config.vault}")
    if args.online:
        analyzer = ClaudeAnalyzer(config.model, config.effort)
    else:
        analyzer = OfflineAnalyzer()
    pipe = Pipeline(config, analyzer, dry_run=args.dry_run)
    records, cursors = pipe.collect()
    report = pipe.run(records, cursors)
    if not args.dry_run:
        write_obsidian_settings(config.vault)
    _print_report(report, args.dry_run)
    if not args.dry_run:
        print(f"\nOpen it in Obsidian: Open folder as vault -> {config.vault}")
    return 1 if report.failed else 0


def cmd_sync(args: argparse.Namespace) -> int:
    config = Config.load(args.config)
    pipe = Pipeline(config, OfflineAnalyzer(), dry_run=args.dry_run)
    print(f"Vault: {config.vault}")
    records, cursors = pipe.collect(only=args.only, limit=args.limit)
    if not args.offline:
        to_send = [r for r in records if pipe.state.records.get(r.id, {}).get("hash") != r.content_hash()]
        chars = sum(len(r.body) for r in to_send)
        redaction = config.redactor.mode
        print(f"\n{len(to_send)} records (~{chars:,} characters) will be sent to the Claude API "
              f"({config.model}) for classification and extraction. Redaction: {redaction}.")
        if to_send and not args.yes:
            if input("Continue? [y/N] ").strip().lower() != "y":
                print("Stopped. Nothing was sent or written.")
                return 1
        redact = config.redactor.redact if config.redactor.for_api else None
        pipe.analyzer = ClaudeAnalyzer(config.model, config.effort, config.use_fallbacks, redact=redact)
    report = pipe.run(records, cursors)
    _print_report(report, args.dry_run)
    return 1 if report.failed else 0


def cmd_connectors(args: argparse.Namespace) -> int:
    for name, cls in connectors.REGISTRY.items():
        status = "ready" if cls.implemented else "stub"
        secrets = ", ".join(f"{s} {'set' if has_secret(s) else 'missing'}" for s in cls.secrets)
        print(f"{name:16} {status:6} {cls.description}" + (f"  [{secrets}]" if secrets else ""))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    ok = True
    path = args.config or DEFAULT_CONFIG_PATH
    try:
        config = Config.load(path)
        print(f"config     ok   {path}")
        print(f"vault      ok   {config.vault} (outside the repo)")
        print(f"model           {config.model}, effort {config.effort}, redaction {config.redactor.mode}")
        for name, opts in config.connectors.items():
            if not opts.get("enabled", True):
                continue
            cls = connectors.REGISTRY.get(opts.get("type", name))
            missing = [s for s in (cls.secrets if cls else ()) if not has_secret(s)]
            state = "stub" if cls and not cls.implemented else ("missing " + ", ".join(missing) if missing else "ok")
            print(f"connector  {name:14} {state}")
    except (FileNotFoundError, UnsafeVaultPath, ValueError) as exc:
        ok = False
        print(f"config     FAIL {exc}")
    api = has_secret("ANTHROPIC_API_KEY")
    print(f"claude api {'ok  ' if api else 'none'} ANTHROPIC_API_KEY {'found' if api else 'not set (use --offline, or ant auth login)'}")
    return 0 if ok else 1


def cmd_graph(args: argparse.Namespace) -> int:
    from .graph import render_svg

    vault = Path(args.vault).expanduser()
    exclude = () if args.include_daily else ("Daily",)
    n_nodes, n_edges = render_svg(vault, Path(args.out), exclude=exclude)
    print(f"Wrote {args.out}: {n_nodes} notes, {n_edges} links")
    return 0


def cmd_secrets(args: argparse.Namespace) -> int:
    value = getpass.getpass(f"{args.name}: ")
    set_secret(args.name, value)
    print(f"Stored {args.name} in the OS keychain (service 'commonplace').")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="commonplace", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("demo", help="build the synthetic demo vault (offline by default)")
    p.add_argument("--vault", help="where to build it (default ~/commonplace-demo-vault)")
    p.add_argument("--online", action="store_true", help="use Claude instead of the offline analyzer")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("sync", help="sync configured connectors into the vault")
    p.add_argument("--config", type=Path)
    p.add_argument("--dry-run", action="store_true", help="analyze and plan, but write nothing")
    p.add_argument("--offline", action="store_true", help="rule-based analysis, nothing sent to the API")
    p.add_argument("--only", nargs="+", metavar="CONNECTOR")
    p.add_argument("--limit", type=int)
    p.add_argument("--yes", action="store_true", help="skip the confirmation before sending to the API")
    p.set_defaults(func=cmd_sync)

    sub.add_parser("connectors", help="list connectors").set_defaults(func=cmd_connectors)

    p = sub.add_parser("doctor", help="check config, vault location and credentials")
    p.add_argument("--config", type=Path)
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("graph", help="render the vault's link graph to SVG")
    p.add_argument("--vault", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--include-daily", action="store_true", help="also draw Daily notes")
    p.set_defaults(func=cmd_graph)

    p = sub.add_parser("secrets", help="store a secret in the OS keychain")
    p.add_argument("action", choices=["set"])
    p.add_argument("name")
    p.set_defaults(func=cmd_secrets)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except UnsafeVaultPath as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
