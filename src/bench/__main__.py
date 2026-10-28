"""`uv run python -m src.bench` — the manifests, one per line.

The id is the unit of work: `make solve MANIFEST=<id>` and
`make score MANIFEST=<id>` both take it.
"""

from .seeds import manifests


def main() -> None:
    for row in manifests():
        cases = len(row["scope"]["cases"])
        print(
            f"{row['id']:>3}  {row['source']:<20} {row['task_type']:<18} "
            f"{row['name']:<24} {cases} case(s)"
        )


if __name__ == "__main__":
    main()
