"""src/store/repo.py — reads and writes the registry. No business logic."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from src.errors import NotFoundError


def _manifest(conn: sqlite3.Connection, manifest_id: int) -> dict[str, Any]:
    row = conn.execute(
        "SELECT m.*, s.slug AS sample_slug, s.project_id, s.branch, "
        "s.commit_sha,"
        " s.license, s.description AS sample_description, s.entrypoint,"
        " s.target_url, t.name AS task_type"
        " FROM task_manifest m"
        " JOIN sample s ON s.sample_id = m.sample_id"
        " JOIN task_type t ON t.task_type_id = m.task_type_id"
        " WHERE m.manifest_id = ?",
        (manifest_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError(f"no manifest with manifest_id={manifest_id}")
    data = dict(row)
    data["bindings"] = json.loads(data.pop("bindings_json"))
    data["scope"] = json.loads(data.pop("scope_json"))
    technologies = conn.execute(
        "SELECT t.name FROM sample_technology st"
        " JOIN technology t ON t.technology_id = st.technology_id"
        " WHERE st.sample_id = ? ORDER BY t.name",
        (row["sample_id"],),
    ).fetchall()
    data["sample_technologies"] = [r["name"] for r in technologies]
    data["sample"] = {
        "slug": data.pop("sample_slug"),
        "project_id": data["project_id"],
        "branch": data["branch"],
        "commit_sha": data["commit_sha"],
        "license": data["license"],
        "description": data.pop("sample_description"),
        "entrypoint": data["entrypoint"],
        "target_url": data["target_url"],
    }
    return data


def manifest_by_id(
    conn: sqlite3.Connection, manifest_id: int
) -> dict[str, Any]:
    return _manifest(conn, manifest_id)


def manifests(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT manifest_id FROM task_manifest "
        "ORDER BY sample_id, name, version"
    ).fetchall()
    return [_manifest(conn, r["manifest_id"]) for r in rows]


def samples(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        dict(r) for r in conn.execute("SELECT * FROM sample ORDER BY slug")
    ]


def gate_definition(
    conn: sqlite3.Connection, gate_id: str, version: int | None = None
):
    if version is None:
        row = conn.execute(
            "SELECT * FROM gate WHERE gate_id = ? "
            "ORDER BY version DESC LIMIT 1",
            (gate_id,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM gate WHERE gate_id = ? AND version = ?",
            (gate_id, version),
        ).fetchone()
    if row is None:
        raise NotFoundError(
            f"no gate {gate_id}" + (f" v{version}" if version else "")
        )
    return dict(row)


def insert_run(
    conn: sqlite3.Connection,
    run_id: str,
    manifest_id: int,
    started_at: str,
    harness: str,
    environment: str | None,
) -> None:
    conn.execute(
        "INSERT INTO task_run(run_id, manifest_id, started_at, harness, "
        "environment)"
        " VALUES (?,?,?,?,?)",
        (run_id, manifest_id, started_at, harness, environment),
    )
    conn.commit()


def finish_run(
    conn: sqlite3.Connection,
    run_id: str,
    finished_at: str,
    duration_s: float,
    estimated_cost_usd: float | None = None,
) -> None:
    conn.execute(
        "UPDATE task_run SET finished_at = ?, run_duration_s = ?,"
        " estimated_cost_usd = COALESCE(?, estimated_cost_usd)"
        " WHERE run_id = ?",
        (finished_at, duration_s, estimated_cost_usd, run_id),
    )
    conn.commit()


def run(conn: sqlite3.Connection, run_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM v_run WHERE run_id = ?", (run_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError(f"no run with run_id={run_id}")
    data = dict(row)
    data["manifest"] = _manifest(conn, data["manifest_id"])
    return data


def runs(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in conn.execute("SELECT * FROM v_run ORDER BY started_at DESC")
    ]
