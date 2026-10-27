"""src/harness/adapters/postgres/db.py — `postgres@1` → DatabasePort.

Same contract as mysql@1, driven by `psql` inside the db service with
unaligned/tab output so the shared TSV parser applies.

bindings_json options:
    service   default "db"
    user      default "postgres"
    database  required
    list_tables_sql  default: the public schema's tables
"""
from __future__ import annotations

from typing import Any

from src.env.adapters.tabular import parse_batch


class PostgresDatabase:
    DEFAULT_LIST_TABLES_SQL = (
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
    )

    def __init__(self, ctx: Any, options: dict[str, Any]):
        self.ctx = ctx
        self.options = options
        self.service = options.get("service", "db")
        self.user = options.get("user", "postgres")
        self.database = options.get("database")
        self.list_tables_sql = options.get("list_tables_sql", self.DEFAULT_LIST_TABLES_SQL)
        if not self.database:
            raise ValueError("postgres@1 requires options.database")

    def _argv(self) -> list[str]:
        return ["psql", "-U", self.user, "-d", self.database,
                "-X", "-A", "-F", "\t", "-P", "footer=off", "-P", "null=NULL"]

    def _query(self, sql: str) -> list[dict[str, Any]]:
        return parse_batch(self.ctx.stack().exec_(self.service, self._argv(), stdin=sql))

    def list_tables(self) -> list[str]:
        rows = self._query(self.list_tables_sql)
        return [str(next(iter(row.values()))) for row in rows]

    def dump(self, table: str) -> list[dict[str, Any]]:
        return self._query(f'SELECT * FROM "{table}"')

    def dump_many(self, tables: list[str]) -> dict[str, list[dict[str, Any]]]:
        return {table: self.dump(table) for table in tables}
