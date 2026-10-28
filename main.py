#!/usr/bin/env python3
"""main.py — the stable interface.

python3 main.py db init [--force]
python3 main.py db samples|manifests|runs
python3 main.py task run --manifest MANIFEST_ID --sample-sandbox PATH
python3 main.py gate run --gate G --run RUN_ID
python3 main.py case capture --manifest MANIFEST_ID --case C \
    --sample-sandbox PATH
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import config
from src import log
from src.errors import BenchError
from src.gates import registry as gate_registry
from src.gates.functional_parity.capture import capture
from src.harness import registry as harness_registry
from src.run import RunContext, RunPaths, new_run_id, utcnow
from src.run.atomic import write_json
from src.store import db as store_db
from src.store import repo
from src.tasks import registry as task_registry

logger = log.get("main")


# --- helpers -----------------------------------------------------------------
def _manifest(conn, manifest_id: int) -> dict:
    """The manifest a run is about — by id, the only way in.

    No sample+name lookup with a "latest version" tie-break: a run names
    exactly one manifest row, and `make manifests` prints the ids.
    """
    return repo.manifest_by_id(conn, manifest_id)


# --- db ----------------------------------------------------------------------
def cmd_db(args) -> int:
    if args.action == "init":
        path = store_db.init(force=args.force)
        conn = store_db.connect(path)
        try:
            counts = {
                table: conn.execute(
                    f"SELECT count(*) AS c FROM {table}"
                ).fetchone()["c"]
                for table in (
                    "technology",
                    "sample",
                    "task_type",
                    "task_manifest",
                    "task_run",
                    "gate",
                )
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
                print(
                    f"{s['sample_id']:>3}  {s['slug']:<22} "
                    f"{s['branch']}@{s['commit_sha'][:10]}  "
                    f"{s['entrypoint'] or '-'}  {s['target_url'] or '-'}"
                )
        elif args.action == "manifests":
            for m in repo.manifests(conn):
                adapters = ", ".join(
                    f"{cap}={bind.get('adapter')}"
                    for cap, bind in m["bindings"].items()
                )
                print(
                    f"{m['manifest_id']:>3}  {m['sample']['slug']:<22} "
                    f"{m['name']:<24} {m['task_type']:<20} v{m['version']}  "
                    f"{len(m['scope'].get('cases') or [])} case(s)"
                )
                print(f"     adapters: {adapters}")
        elif args.action == "runs":
            rows = repo.runs(conn)
            if not rows:
                print("no runs yet")
            for r in rows:
                print(
                    f"{r['run_id']}  {r['started_at']}  {r['sample']}/"
                    f"{r['task']}  harness={r['harness']}"
                )
    finally:
        conn.close()
    return 0


# --- task --------------------------------------------------------------------
def cmd_task_run(args) -> int:
    conn = store_db.connect()
    try:
        manifest = _manifest(conn, args.manifest)
        harness = harness_registry.resolve(args.harness, args.harness_cmd)
        run_id = new_run_id()
        paths = RunPaths.create(run_id)
        ctx = RunContext(
            run_id=run_id,
            paths=paths,
            manifest=manifest,
            sample_location=Path(args.sample_sandbox).expanduser(),
        )
        repo.insert_run(
            conn,
            run_id,
            manifest["manifest_id"],
            utcnow(),
            harness.name,
            args.environment,
        )

        sample = manifest["sample"]
        logger.info(
            "run %s — %s/%s v%s (%s) harness=%r",
            run_id,
            sample["slug"],
            manifest["name"],
            manifest["version"],
            manifest["task_type"],
            harness.name,
        )
        logger.info("artifacts: %s", paths.root)

        started = time.monotonic()
        result = None
        try:
            result = task_registry.resolve(manifest["task_type"]).prepare(
                ctx, harness
            )
            logger.info(
                "run %s finished in %.1fs (harness exit %s)",
                run_id,
                time.monotonic() - started,
                result.exit_code,
            )
        finally:
            cost = args.estimated_cost or (result.cost_usd if result else None)
            repo.finish_run(
                conn, run_id, utcnow(), time.monotonic() - started, cost
            )
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
    logger.info("gate %s on run %s", definition["gate_id"], args.run)
    result = gate_registry.resolve(ctx, definition).evaluate()
    payload = result.to_dict()
    write_json(ctx.paths.gate(definition["gate_id"]), payload)
    logger.info(
        "gate %s: %s (value %s) in %.1fs",
        definition["gate_id"],
        result.verdict,
        result.value,
        payload["duration_s"],
    )
    print(json.dumps(payload, indent=2))
    return result.exit_code


# --- case --------------------------------------------------------------------
def cmd_case_capture(args) -> int:
    """Authoring only: freeze a golden. The corpus itself lives in the gate."""
    conn = store_db.connect()
    try:
        manifest = _manifest(conn, args.manifest)
    finally:
        conn.close()

    owner = args.case.split("__", 1)[0]
    if owner != manifest["name"]:
        raise BenchError(
            f"case '{args.case}' belongs to '{owner}', but manifest "
            f"{args.manifest} is '{manifest['name']}'"
        )

    run_id = new_run_id()
    paths = RunPaths.create(run_id)
    ctx = RunContext(
        run_id=run_id,
        paths=paths,
        manifest=manifest,
        sample_location=Path(args.sample_sandbox).expanduser(),
    )
    print(
        f"captured {manifest['sample']['slug']}/{args.case} -> "
        f"{capture(ctx, args.case, keep_stack=args.keep_stack)}"
    )
    return 0


# --- argument parsing --------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bench",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="verb", required=True)

    db = sub.add_parser("db", help="registry inspection / initialisation")
    db_sub = db.add_subparsers(dest="action", required=True)
    db_init = db_sub.add_parser(
        "init", help="create bench.db from schema.sql + seeds"
    )
    db_init.add_argument(
        "--force", action="store_true", help="delete and rebuild"
    )
    db_init.set_defaults(func=cmd_db)
    for action in ("samples", "manifests", "runs"):
        db_sub.add_parser(action, help=f"list {action}").set_defaults(
            func=cmd_db
        )

    task = sub.add_parser("task", help="start a run")
    task_sub = task.add_subparsers(dest="action", required=True)
    task_run = task_sub.add_parser(
        "run", help="prepare a run, print its run_id"
    )
    task_run.add_argument(
        "--manifest",
        type=int,
        required=True,
        help="manifest_id, as printed by `make manifests`",
    )
    task_run.add_argument(
        "--sample-sandbox",
        required=True,
        help="the folder allocated to this run (absolute, empty): the bench "
        "puts the pin there and nothing else",
    )
    task_run.add_argument(
        "--harness",
        default=config.HARNESS_LABEL,
        help="label recorded with the run, e.g. opencode-ds-flash-max "
        "(free text: it selects nothing, the command does)",
    )
    task_run.add_argument(
        "--harness-cmd",
        default=None,
        help="the command that does the work, prompt on stdin "
        "(overrides BENCH_HARNESS_CMD)",
    )
    task_run.add_argument(
        "--environment",
        default=None,
        help="free-text description of the machine/image",
    )
    task_run.add_argument(
        "--estimated-cost",
        type=float,
        default=None,
        help="USD, if the harness reports it",
    )
    task_run.set_defaults(func=cmd_task_run)

    gate = sub.add_parser("gate", help="evaluate a run")
    gate_sub = gate.add_subparsers(dest="action", required=True)
    gate_run = gate_sub.add_parser(
        "run", help="evaluate and write gates/<id>.json"
    )
    gate_run.add_argument("--gate", required=True)
    gate_run.add_argument("--run", required=True, dest="run")
    gate_run.add_argument("--gate-version", type=int, default=None)
    gate_run.set_defaults(func=cmd_gate_run)

    case = sub.add_parser("case", help="freeze a case's golden")
    case_sub = case.add_subparsers(dest="action", required=True)
    case_capture = case_sub.add_parser(
        "capture", help="capture expect.json + images"
    )
    case_capture.add_argument(
        "--manifest",
        type=int,
        required=True,
        help="manifest_id the case belongs to (`make manifests`)",
    )
    case_capture.add_argument("--case", required=True)
    case_capture.add_argument(
        "--sample-sandbox",
        required=True,
        help="the folder allocated to this capture (absolute, empty)",
    )
    case_capture.add_argument("--keep-stack", action="store_true")
    case_capture.set_defaults(func=cmd_case_capture)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    log.setup(config.LOG_LEVEL)
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
