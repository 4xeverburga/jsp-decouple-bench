"""Reading table state from inside the database's own service.

The client lives in the `db` service of the stack Inspect provisioned, so
there is no host-side mysql install, no published port and no credentials
dance: the same argv the old adapter used, run through `sandbox()`.
"""

from inspect_ai.util import sandbox

from .tabular import parse_batch


def _argv(database: str) -> list[str]:
    return [
        "mysql",
        "-uroot",
        database,
        "--batch",
        "--default-character-set=utf8",
    ]


async def query(service: str, database: str, sql: str) -> list[dict]:
    result = await sandbox(service).exec(_argv(database), input=sql)
    if not result.success:
        raise RuntimeError(f"mysql failed: {result.stderr[:400]}")
    return parse_batch(result.stdout)


async def snapshot(
    service: str, database: str, tables: list[str]
) -> dict[str, list[dict]]:
    """Every named table, as it stands right now."""
    return {
        table: await query(service, database, f"SELECT * FROM `{table}`")
        for table in tables
    }
