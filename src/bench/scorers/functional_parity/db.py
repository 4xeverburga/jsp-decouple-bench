"""Reading table state from inside the database's own service.

The client lives in the `db` service of the case's stack, so there is no
host-side mysql install, no published port and no credentials dance.
"""

from ...stack import Stack
from .tabular import parse_batch


def _argv(database: str) -> list[str]:
    return [
        "mysql",
        "-uroot",
        database,
        "--batch",
        "--default-character-set=utf8",
    ]


async def query(
    stack: Stack, service: str, database: str, sql: str
) -> list[dict]:
    result = await stack.exec(service, _argv(database), sql)
    if result.returncode != 0:
        raise RuntimeError(f"mysql failed: {result.stderr[:400]}")
    return parse_batch(result.stdout)


async def snapshot(
    stack: Stack, service: str, database: str, tables: list[str]
) -> dict[str, list[dict]]:
    """Every named table, as it stands right now."""
    return {
        table: await query(
            stack, service, database, f"SELECT * FROM `{table}`"
        )
        for table in tables
    }
