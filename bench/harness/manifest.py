#!/usr/bin/env python3
"""bench/harness/manifest.py — tamper detection for the eval infrastructure.

Usage:
  manifest.py generate <bench_dir>          # (re)write MANIFEST.sha256
  manifest.py verify <manifest_path>        # exit 0 if unmodified, 2 if TAMPERED
"""
import hashlib
import sys
from pathlib import Path


def _digests(bench_dir: Path) -> dict[str, str]:
    out = {}
    for p in sorted(bench_dir.rglob("*")):
        if p.is_file() and p.name != "MANIFEST.sha256":
            out[str(p.relative_to(bench_dir))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def generate(bench_dir: Path) -> None:
    lines = [f"{h}  {rel}" for rel, h in _digests(bench_dir).items()]
    (bench_dir / "MANIFEST.sha256").write_text("\n".join(lines) + "\n")
    print(f"manifest: {len(lines)} files")


def verify(manifest_path: Path) -> int:
    bench_dir = manifest_path.parent
    expected = {}
    for line in manifest_path.read_text().splitlines():
        if line.strip():
            digest, rel = line.split("  ", 1)
            expected[rel] = digest
    actual = _digests(bench_dir)
    if expected == actual:
        print(f"manifest OK ({len(actual)} files)")
        return 0
    missing = set(expected) - set(actual)
    added = set(actual) - set(expected)
    changed = [f for f in set(expected) & set(actual) if expected[f] != actual[f]]
    for label, files in (("MODIFIED", changed), ("ADDED", added), ("DELETED", missing)):
        for f in sorted(files):
            print(f"TAMPERED {label}: bench/{f}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    cmd, target = sys.argv[1], Path(sys.argv[2])
    sys.exit(generate(target) is None and 0 if cmd == "generate" else verify(target))
