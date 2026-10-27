"""src/harness/adapters/h2/db.py — `h2@1` → DatabasePort.

H2 has no client usable through `compose exec` in the images these
samples use, so this adapter is `shell@1` plus a H2-specific default: it
still requires an explicit `cmd` (typically

    java -cp h2.jar org.h2.tools.Shell -url jdbc:h2:./target/db/repository \\
         -user sa -sql "$(cat)"

) because the classpath and file location belong to the sample, not to the
bench. Keeping the technology name in the binding makes the manifest say
`h2`, which is what a reader needs to know.
"""
from __future__ import annotations

from src.harness.adapters.shell.db import ShellDatabase


class H2Database(ShellDatabase):
    DEFAULT_LIST_TABLES_SQL = (
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='PUBLIC' ORDER BY table_name"
    )

    def __init__(self, ctx, options):
        merged = dict(options)
        merged.setdefault("list_tables_sql", self.DEFAULT_LIST_TABLES_SQL)
        super().__init__(ctx, merged)
