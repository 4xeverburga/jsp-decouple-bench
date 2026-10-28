"""src/harness/adapters/mysql/db.py — `mysql@1` → DatabasePort.

Runs the client *inside the db service* of the sample's own stack, so no
host-side mysql installation or credentials-file dance is needed.

bindings_json options:
    service       compose service name of the database (default "db")
    user          default "root"
    password      default "" (empty)
    database      required — schema to dump
    list_tables_sql  default "SHOW TABLES"
"""

from __future__ import annotations

from typing import Any

from src.env.adapters.tabular import parse_batch


class MysqlDatabase:
    DEFAULT_LIST_TABLES_SQL = "SHOW TABLES"

    def __init__(self, ctx: Any, options: dict[str, Any]):
        self.ctx = ctx
        self.options = options
        self.service = options.get("service", "db")
        self.user = options.get("user", "root")
        self.password = options.get("password", "")
        self.database = options.get("database")
        self.list_tables_sql = options.get(
            "list_tables_sql", self.DEFAULT_LIST_TABLES_SQL
        )
        if not self.database:
            raise ValueError("mysql@1 requires options.database")

    def _argv(self) -> list[str]:
        argv = ["mysql", f"-u{self.user}"]
        if self.password:
            argv.append(f"-p{self.password}")
        argv += [self.database, "--batch", "--default-character-set=utf8"]
        return argv

    def _query(self, sql: str) -> list[dict[str, Any]]:
        return parse_batch(
            self.ctx.stack().exec_(self.service, self._argv(), stdin=sql)
        )

    def list_tables(self) -> list[str]:
        rows = self._query(self.list_tables_sql)
        return [str(next(iter(row.values()))) for row in rows]

    def dump(self, table: str) -> list[dict[str, Any]]:
        return self._query(f"SELECT * FROM `{table}`")

    def dump_many(self, tables: list[str]) -> dict[str, list[dict[str, Any]]]:
        return {table: self.dump(table) for table in tables}
