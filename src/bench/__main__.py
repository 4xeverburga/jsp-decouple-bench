"""`uv run python -m src.bench` — manifests and scorer assignments.

The id is the unit of work: `make task MANIFEST=<id>` runs it.
"""

from .seeds import manifests


def main() -> None:
    for row in manifests():
        cases = len(row["scope"]["cases"])
        scorers = ",".join(row["scorers"])
        print(
            f"{row['id']:>3}  {row['name']:<24} {row['task_type']:<18} "
            f"{cases} case(s)"
        )
        print(f"     scorers: {scorers}")


if __name__ == "__main__":
    main()
