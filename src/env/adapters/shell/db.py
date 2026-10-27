"""src/harness/adapters/shell/db.py — `shell@1` → DatabasePort.

Escape hatch for stacks whose DB is not reachable through `compose exec`
(podman, a JDBC file, an external container). The command reads SQL on
stdin and must print a header line then tab-separated rows, NULL as the
literal `NULL` — exactly the contract the old `capture.env` used.

bindings_json options:
    cmd              required — shell command reading SQL from stdin
    list_tables_sql  required — query listing table names in column 1
"""
from __future__ import annotations

import os
import subprocess
from typing import Any

import config
from src.errors import GateError
from src.env.adapters.tabular import parse_batch


class ShellDatabase:
    def __init__(self, ctx: Any, options: dict[str, Any]):
        self.ctx = ctx
        self.options = options
        self.cmd = options.get("cmd")
        self.list_tables_sql = options.get("list_tables_sql")
        if not self.cmd or not self.list_tables_sql:
            raise ValueError("shell@1 requires options.cmd and options.list_tables_sql")

    def _query(self, sql: str) -> list[dict[str, Any]]:
        env = dict(os.environ)
        env.update(config.load_env_file(
            self.ctx.sample_location / config.SAMPLE_ENV_FILE))  # type: ignore[operator]
        proc = subprocess.run(
            ["bash", "-c", self.cmd], input=sql, capture_output=True, text=True, env=env
        )
        if proc.returncode != 0:
            raise GateError(f"db command failed: {proc.stderr.strip()[-2000:]}")
        return parse_batch(proc.stdout)

    def list_tables(self) -> list[str]:
        rows = self._query(self.list_tables_sql)
        return [str(next(iter(row.values()))) for row in rows]

    def dump(self, table: str) -> list[dict[str, Any]]:
        return self._query(f"SELECT * FROM {table}")

    def dump_many(self, tables: list[str]) -> dict[str, list[dict[str, Any]]]:
        return {table: self.dump(table) for table in tables}
