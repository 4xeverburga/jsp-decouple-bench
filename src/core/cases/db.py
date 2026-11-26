"""Reading table state from inside the database's own service.

The client lives in the `db` service of the case's stack, so there is no
host-side install, no published port and no credentials dance.

Which client is the manifest's business: `bindings.db.options.dialect`
names it. Both engines are driven into the same unaligned, tab-separated,
`NULL`-as-a-literal shape that `tabular.parse_batch` reads, so only the
argv and the identifier quoting differ — the comparison never does.
"""

from dataclasses import dataclass

from ...stack import Stack
from .tabular import parse_batch


@dataclass(frozen=True)
class Target:
    """The case's database, as its manifest describes it."""

    dialect: str
    service: str
    database: str
    user: str
    password: str

    @classmethod
    def from_options(cls, options: dict) -> "Target":
        """A manifest's `bindings.db.options`, made explicit.

        Every key is required: a sample that forgets its dialect is a
        broken manifest, not a MySQL one.
        """
        return cls(
            dialect=options["dialect"],
            service=options["service"],
            database=options["database"],
            user=options["user"],
            password=options["password"],
        )


def _argv(target: Target, sql: str) -> list[str]:
    if target.dialect == "mysql":
        auth = [f"-u{target.user}"]
        if target.password:
            auth.append(f"-p{target.password}")
        return [
            "mysql",
            *auth,
            target.database,
            "--batch",
            "--default-character-set=utf8",
            "-e",
            sql,
        ]
    if target.dialect == "postgres":
        # Through the local socket, so the container's own trust rule
        # applies: the password is the compose service's, never typed here.
        return [
            "psql",
            "-X",
            "-q",
            "-A",
            "-F",
            "\t",
            "-P",
            "footer=off",
            "-P",
            "null=NULL",
            "-U",
            target.user,
            "-d",
            target.database,
            "-c",
            sql,
        ]
    raise ValueError(f"unknown database dialect: {target.dialect!r}")


def _identifier(target: Target, name: str) -> str:
    """Quote a table name the way this engine expects it."""
    if target.dialect == "mysql":
        return f"`{name}`"
    return f'"{name}"'


async def query(stack: Stack, target: Target, sql: str) -> list[dict]:
    result = await stack.exec(target.service, _argv(target, sql), "")
    if result.returncode != 0:
        raise RuntimeError(f"{target.dialect} failed: {result.stderr[:400]}")
    return parse_batch(result.stdout)


async def snapshot(
    stack: Stack, target: Target, tables: list[str]
) -> dict[str, list[dict]]:
    """Every named table, as it stands right now."""
    return {
        table: await query(
            stack,
            target,
            f"SELECT * FROM {_identifier(target, table)}",
        )
        for table in tables
    }
