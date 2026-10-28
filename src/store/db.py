"""src/store/db.py — sqlite connection, schema and seeding."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import config
from src.errors import BenchError, NotFoundError

SCHEMA_VERSION = 3


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = Path(path or config.BENCH_DB)
    if not path.exists():
        raise NotFoundError(f"{path} does not exist — run `make db-init`")
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init(force: bool = False) -> Path:
    """(Re)create bench.db from schema.sql + seeds. Idempotent by default."""
    path = Path(config.BENCH_DB)
    if path.exists() and not force:
        existing = sqlite3.connect(path)
        try:
            version = existing.execute("PRAGMA user_version").fetchone()[0]
        finally:
            existing.close()
        if version != SCHEMA_VERSION:
            raise BenchError(
                f"{path} was built with schema v{version}, code expects "
                f"v{SCHEMA_VERSION}. Run `make db-init-force` (rebuilds the "
                f"registry; runs and artifacts under out/ are untouched)."
            )
    if force and path.exists():
        for suffix in ("", "-wal", "-shm"):
            Path(str(path) + suffix).unlink(missing_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(config.SCHEMA_SQL.read_text())
        _seed(conn)
        conn.commit()
    finally:
        conn.close()
    return path


def _rows(name: str) -> list[dict]:
    path = Path(config.SEEDS_DIR) / name
    if not path.is_file():
        return []
    return json.loads(path.read_text())


def _seed(conn: sqlite3.Connection) -> None:
    for tech in _rows("technologies.json"):
        conn.execute(
            "INSERT INTO technology(name, kind) VALUES (?,?) "
            "ON CONFLICT(name) DO UPDATE SET kind = excluded.kind",
            (tech["name"], tech["kind"]),
        )

    for ttype in _rows("task_types.json"):
        conn.execute(
            "INSERT INTO task_type(name, description, base_prompt) "
            "VALUES (?,?,?) ON CONFLICT(name) DO UPDATE SET "
            "description = excluded.description, "
            "base_prompt = excluded.base_prompt",
            (ttype["name"], ttype.get("description"), ttype["base_prompt"]),
        )

    for gate in _rows("gates.json"):
        conn.execute(
            "INSERT INTO gate(gate_id, version, description, threshold, "
            "direction) "
            "VALUES (?,?,?,?,?) ON CONFLICT(gate_id, version) DO UPDATE SET "
            "description = excluded.description, "
            "threshold = excluded.threshold, "
            "direction = excluded.direction",
            (
                gate["gate_id"],
                gate["version"],
                gate["description"],
                gate["threshold"],
                gate["direction"],
            ),
        )

    for sample in _rows("samples.json"):
        row = conn.execute(
            "SELECT sample_id FROM sample WHERE slug = ?", (sample["slug"],)
        ).fetchone()
        if row is None:
            # The natural key is (project_id, branch, commit_sha); a sample
            # that gets re-pinned keeps its id so old runs stay attached.
            cur = conn.execute(
                "INSERT INTO sample(slug, project_id, source, branch, "
                "commit_sha, license, description, entrypoint, target_url) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    sample["slug"],
                    sample["project_id"],
                    sample["source"],
                    sample["branch"],
                    sample["commit_sha"],
                    sample.get("license"),
                    sample.get("description"),
                    sample.get("entrypoint"),
                    sample.get("target_url"),
                ),
            )
            sample_id = cur.lastrowid
        else:
            sample_id = row["sample_id"]
            conn.execute(
                "UPDATE sample SET project_id = ?, source = ?, branch = ?,"
                " commit_sha = ?, license = ?, description = ?,"
                " entrypoint = ?, target_url = ? WHERE sample_id = ?",
                (
                    sample["project_id"],
                    sample["source"],
                    sample["branch"],
                    sample["commit_sha"],
                    sample.get("license"),
                    sample.get("description"),
                    sample.get("entrypoint"),
                    sample.get("target_url"),
                    sample_id,
                ),
            )
        conn.execute(
            "DELETE FROM sample_technology WHERE sample_id = ?", (sample_id,)
        )
        for tech_name in sample.get("technologies", []):
            tech = conn.execute(
                "SELECT technology_id FROM technology WHERE name = ?",
                (tech_name,),
            ).fetchone()
            if tech is None:
                raise NotFoundError(
                    f"sample {sample['slug']} tags unknown technology "
                    f"{tech_name}"
                )
            conn.execute(
                "INSERT INTO sample_technology(sample_id, technology_id) "
                "VALUES (?,?)",
                (sample_id, tech["technology_id"]),
            )

    for manifest in _rows("manifests.json"):
        sample = conn.execute(
            "SELECT sample_id FROM sample WHERE slug = ?",
            (manifest["sample"],),
        ).fetchone()
        ttype = conn.execute(
            "SELECT task_type_id FROM task_type WHERE name = ?",
            (manifest["task_type"],),
        ).fetchone()
        if sample is None or ttype is None:
            raise NotFoundError(
                f"manifest references unknown sample/task_type: {manifest}"
            )
        conn.execute(
            "INSERT INTO task_manifest(sample_id, task_type_id, name, "
            "version, prompt,"
            " bindings_json, scope_json) VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(sample_id, name, version) DO UPDATE SET "
            "task_type_id = excluded.task_type_id, prompt = excluded.prompt,"
            " bindings_json = excluded.bindings_json,"
            " scope_json = excluded.scope_json",
            (
                sample["sample_id"],
                ttype["task_type_id"],
                manifest["name"],
                manifest["version"],
                manifest["prompt"],
                json.dumps(manifest["bindings"], sort_keys=True),
                json.dumps(manifest["scope"], sort_keys=True),
            ),
        )
