#!/usr/bin/env python3
"""main.py — the stable interface.

    python3 main.py db init [--force]
    python3 main.py db samples|manifests|runs
    python3 main.py task run --manifest N --sample-location PATH
    python3 main.py gate run --gate G --run RUN_ID
    python3 main.py case capture --sample S --case C --sample-location PATH
    python3 main.py case run     --sample S --case C --sample-location PATH
    python3 main.py pin --sample S --sample-location PATH
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from src.errors import BenchError, NotFound
from src.gates import registry as gate_registry
from src.run import RunContext, RunPaths, new_run_id, utcnow
from src.run.atomic import write_json
from src.run.sample_checkout import ensure_pinned
from src.store import db as store_db
from src.store import repo
from src.tasks import registry as task_registry


# --- helpers -----------------------------------------------------------------
def _resolve_manifest(conn, sample: str, task: str) -> dict:
    row = conn.execute(
        "SELECT m.manifest_id FROM task_manifest m"
        " JOIN sample s ON s.sample_id = m.sample_id"
        " WHERE s.slug = ? AND m.name = ?"
        " ORDER BY m.version DESC LIMIT 1",
        (sample, task),
    ).fetchone()
    if row is None:
        raise NotFound(f"no manifest for sample='{sample}' task='{task}'")
    return repo.manifest_by_id(conn, row["manifest_id"])


def _manifest_for(conn, args) -> dict:
    if getattr(args, "manifest", None) is not None:
        return repo.manifest_by_id(conn, args.manifest)
    if not getattr(args, "sample", None) or not getattr(args, "task", None):
        raise BenchError("give --manifest, or --sample together with --task")
    return _resolve_manifest(conn, args.sample, args.task)


def _git(location: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(location), *args],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise BenchError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


# --- db ----------------------------------------------------------------------
def cmd_db(args) -> int:
    if args.action == "init":
        path = store_db.init(force=args.force)
        conn = store_db.connect(path)
        try:
            counts = {
                table: conn.execute(f"SELECT count(*) AS c FROM {table}").fetchone()["c"]
                for table in ("technology", "sample", "task_type",
                              "task_manifest", "task_run", "gate")
            }
        finally:
            conn.close()
        print(f"bench.db initialised at {path}")
        print(json.dumps(counts, indent=2))
        return 0

    conn = store_db.connect()
    try:
        if args.action == "samples":
            for s in repo.samples(conn):
                print(f"{s['sample_id']:>3}  {s['slug']:<22} "
                      f"{s['branch']}@{s['commit_sha'][:10]}  "
                      f"{s['entrypoint'] or '-'}  {s['target_url'] or '-'}")
        elif args.action == "manifests":
            for m in repo.manifests(conn):
                adapters = ", ".join(
                    f"{cap}={bind.get('adapter')}" for cap, bind in m["bindings"].items())
                print(f"{m['manifest_id']:>3}  {m['sample']['slug']:<22} "
                      f"{m['name']:<24} {m['task_type']:<20} v{m['version']}  "
                      f"{len(m['scope'].get('cases') or [])} case(s)")
                print(f"     adapters: {adapters}")
        elif args.action == "runs":
            rows = repo.runs(conn)
            if not rows:
                print("no runs yet")
            for r in rows:
                print(f"{r['run_id']}  {r['started_at']}  {r['sample']}/"
                      f"{r['task']}  harness={r['harness']}")
    finally:
        conn.close()
    return 0


# --- task --------------------------------------------------------------------
def cmd_task_run(args) -> int:
    conn = store_db.connect()
    try:
        manifest = _manifest_for(conn, args)
        run_id = new_run_id()
        paths = RunPaths.create(run_id)
        ctx = RunContext(
            run_id=run_id,
            paths=paths,
            manifest=manifest,
            sample_location=Path(args.sample_location).expanduser(),
        )
        repo.insert_run(conn, run_id, manifest["manifest_id"], utcnow(),
                        args.harness, args.environment)

        started = time.monotonic()
        try:
            runner = task_registry.resolve(manifest["task_type"])
            runner.prepare(ctx)
        finally:
            repo.finish_run(conn, run_id, utcnow(), time.monotonic() - started,
                            args.estimated_cost)
    finally:
        conn.close()

    print(run_id)
    return 0


# --- gate --------------------------------------------------------------------
def cmd_gate_run(args) -> int:
    conn = store_db.connect()
    try:
        definition = repo.gate_definition(conn, args.gate, args.gate_version)
        manifest = repo.run(conn, args.run)["manifest"]
    finally:
        conn.close()

    ctx = RunContext.load(args.run, manifest)
    result = gate_registry.resolve(ctx, definition).evaluate()
    payload = result.to_dict()
    write_json(ctx.paths.gate(definition["gate_id"]), payload)
    print(json.dumps(payload, indent=2))
    return result.exit_code


# --- case --------------------------------------------------------------------
def _capture_ctx(args) -> RunContext:
    task = args.case.split("__", 1)[0]
    conn = store_db.connect()
    try:
        manifest = _resolve_manifest(conn, args.sample, task)
    finally:
        conn.close()
    run_id = new_run_id()
    return RunContext(
        run_id=run_id,
        paths=RunPaths.create(run_id),
        manifest=manifest,
        sample_location=Path(args.sample_location).expanduser(),
    )


def cmd_case_capture(args) -> int:
    ctx = _capture_ctx(args)
    sample = ctx.sample

    # Golden capture is only meaningful from the pinned, unmodified tree.
    preconditions = ensure_pinned(ctx.sample_location, sample["commit_sha"],
                                  sample.get("entrypoint"))

    case = ctx.case(args.case)
    tables = (case.get("db") or {}).get("tables") or []
    declared_artifacts = (case.get("e2e") or {}).get("artifacts") or []

    stack = ctx.stack()
    database = ctx.adapter("db")
    browser = ctx.adapter("browser")
    try:
        stack.reset()
        base_url = ctx.base_url()
        table_names = [t["name"] for t in tables]
        before = database.dump_many(table_names)
        artifacts = browser.capture_case(args.case, base_url, ctx.paths.images)
        after = database.dump_many(table_names)
    finally:
        stack.down() if not args.keep_stack else None

    from src.gates.functional_parity.delta import delta_table  # local: avoid cycle noise

    payload = {
        "sample": sample["slug"],
        "case": args.case,
        "sample_commit": preconditions["commit"],
        "captured_at": utcnow(),
        "db": {"tables": {
            t["name"]: delta_table(
                before.get(t["name"]) or [],
                after.get(t["name"]) or [],
                t.get("key_columns") or ["id"],
                t.get("ignore_columns") or [],
            )
            for t in tables
        }},
        "artifacts": {key: artifacts.get(key) for key in declared_artifacts},
    }
    expect_path = ctx.cases_dir / args.case / "expect.json"
    write_json(expect_path, payload)

    images = ctx.cases_dir / args.case / "images"
    if ctx.paths.images.is_dir():
        shutil.copytree(ctx.paths.images, images, dirs_exist_ok=True)

    print(f"captured {sample['slug']}/{args.case} -> {expect_path}")
    return 0


def cmd_case_run(args) -> int:
    ctx = _capture_ctx(args)
    ensure_pinned(ctx.sample_location, ctx.sample["commit_sha"], ctx.sample.get("entrypoint"))
    stack = ctx.stack()
    try:
        stack.up()
        artifacts = ctx.adapter("browser").run_case(args.case, ctx.base_url())
    finally:
        stack.down() if not args.keep_stack else None
    print(json.dumps(artifacts, indent=2))
    return 0


# --- pin ---------------------------------------------------------------------
def cmd_pin(args) -> int:
    location = Path(args.sample_location).expanduser().resolve()
    commit = _git(location, "rev-parse", "HEAD")
    branch = _git(location, "rev-parse", "--abbrev-ref", "HEAD")
    if branch == "HEAD":
        branch = _git(location, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    conn = store_db.connect()
    try:
        updated = conn.execute(
            "UPDATE sample SET commit_sha = ?, branch = ? WHERE slug = ?",
            (commit, branch, args.sample),
        ).rowcount
        conn.commit()
    finally:
        conn.close()
    if not updated:
        raise NotFound(f"no sample with slug '{args.sample}'")
    print(f"{args.sample} pinned to {branch}@{commit}")
    return 0


# --- argument parsing --------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bench", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="verb", required=True)

    db = sub.add_parser("db", help="registry inspection / initialisation")
    db_sub = db.add_subparsers(dest="action", required=True)
    db_init = db_sub.add_parser("init", help="create bench.db from schema.sql + seeds")
    db_init.add_argument("--force", action="store_true", help="delete and rebuild")
    db_init.set_defaults(func=cmd_db)
    for action in ("samples", "manifests", "runs"):
        db_sub.add_parser(action, help=f"list {action}").set_defaults(func=cmd_db)

    task = sub.add_parser("task", help="start a run")
    task_sub = task.add_subparsers(dest="action", required=True)
    task_run = task_sub.add_parser("run", help="prepare a run, print its run_id")
    task_run.add_argument("--manifest", type=int, help="manifest_id")
    task_run.add_argument("--sample", help="sample slug (alternative to --manifest)")
    task_run.add_argument("--task", help="feature boundary, e.g. vote-flow (with --sample)")
    task_run.add_argument("--sample-location", required=True,
                          help="where the sample checkout lives on this filesystem")
    task_run.add_argument("--harness", default="pristine",
                          help="who produced the diff (pristine, claude-code, ...)")
    task_run.add_argument("--environment", default=None,
                          help="free-text description of the machine/image")
    task_run.add_argument("--estimated-cost", type=float, default=None,
                          help="USD, if the harness reports it")
    task_run.set_defaults(func=cmd_task_run)

    gate = sub.add_parser("gate", help="evaluate a run")
    gate_sub = gate.add_subparsers(dest="action", required=True)
    gate_run = gate_sub.add_parser("run", help="evaluate and write gates/<id>.json")
    gate_run.add_argument("--gate", required=True)
    gate_run.add_argument("--run", required=True, dest="run")
    gate_run.add_argument("--gate-version", type=int, default=None)
    gate_run.set_defaults(func=cmd_gate_run)

    case = sub.add_parser("case", help="behaviour cases")
    case_sub = case.add_subparsers(dest="action", required=True)
    for action, func, text in (
        ("capture", cmd_case_capture, "freeze the golden db delta + artifacts"),
        ("run", cmd_case_run, "execute one flow against the current stack"),
    ):
        node = case_sub.add_parser(action, help=text)
        node.add_argument("--sample", required=True)
        node.add_argument("--case", required=True)
        node.add_argument("--sample-location", required=True)
        node.add_argument("--keep-stack", action="store_true")
        node.set_defaults(func=func)

    pin = sub.add_parser("pin", help="re-pin a sample to its checkout's HEAD")
    pin.add_argument("--sample", required=True)
    pin.add_argument("--sample-location", required=True)
    pin.set_defaults(func=cmd_pin)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except BenchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:  # pragma: no cover
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
