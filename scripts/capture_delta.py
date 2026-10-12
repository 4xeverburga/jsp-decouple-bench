#!/usr/bin/env python3
"""Capture golden DB deltas by running the test's own flow.py.

Usage:
  .venv/bin/python scripts/capture_delta.py <test-name>
      e.g. vote-flow__upvote-increments-count

Requires: the mamute compose stack freshly reset (down -v && up -d --wait),
docker reachable via `sg docker`, python playwright installed (.venv).

The flow under bench/e2e/mamute/<test>/flow.py is the single source of
truth: this script imports it, runs run(page, base_url) against the
pristine app, and freezes the before/after DB delta. Screenshots are
taken after every goto/click for review only.

Outputs:
  bench/db/mamute/<test>/expected_delta.json   frozen golden delta
  $CAPTURE_OUT/<test>/*.png                    step screenshots (review only)
  $CAPTURE_OUT/<test>/artifacts.json           flow artifacts (dom snapshots etc.)
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

BENCH = Path(__file__).resolve().parent.parent
CAPTURE_OUT = Path(os.environ.get(
    "CAPTURE_OUT",
    "/home/ever/.copilot/session-state/f795803e-47a0-42d2-a67b-b47614e310e9/files/mamute-capture"))
BASE_URL = os.environ.get("MAMUTE_BASE_URL", "http://localhost:8090")
COMPOSE = BENCH / "environments" / "mamute" / "compose.yml"

if len(sys.argv) != 2:
    sys.exit(__doc__)
test_name = sys.argv[1]


def load_env():
    env = {}
    for line in (BENCH / "environments/mamute/.env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    return env


ENV = load_env()
ADMIN_USER, ADMIN_PASSWORD = ENV.get("MAMUTE_ADMIN_USER"), ENV.get("MAMUTE_ADMIN_PASSWORD")
if not ADMIN_USER or not ADMIN_PASSWORD:
    sys.exit("missing admin credentials in environments/mamute/.env")
# flows read credentials from the harness-injected environment only
os.environ.setdefault("MAMUTE_ADMIN_USER", ADMIN_USER)
os.environ.setdefault("MAMUTE_ADMIN_PASSWORD", ADMIN_PASSWORD)


# --- db dump helpers ----------------------------------------------------------
def mysql(sql):
    return subprocess.run(
        ["sg", "docker", "-c",
         f"docker compose -f {COMPOSE} exec -T db mysql -uroot mamute_development --batch -e \"{sql}\""],
        capture_output=True, text=True, check=True).stdout


def parse_batch(out):
    lines = [l for l in out.splitlines() if l]
    if not lines:
        return []
    cols = lines[0].split("\t")
    rows = []
    for line in lines[1:]:
        vals = line.split("\t")
        row = {}
        for i, c in enumerate(cols):
            v = vals[i] if i < len(vals) else "NULL"
            row[c] = None if v == "NULL" else v.replace("\\n", "\n").replace("\\t", "\t").replace("\\\\", "\\")
        rows.append(row)
    return rows


def table_names():
    return [list(r.values())[0] for r in parse_batch(mysql("SHOW TABLES"))]


# --- delta --------------------------------------------------------------------
def _sort(rows):
    return sorted(rows, key=lambda r: json.dumps(r, sort_keys=True))


def delta_table(before, after, key_cols, ignore_cols):
    ignored = set(ignore_cols or [])
    strip = lambda row: {c: v for c, v in row.items() if c not in ignored}
    key_of = lambda row: json.dumps([row[c] for c in key_cols])
    b = {key_of(r): r for r in before}
    a = {key_of(r): r for r in after}
    inserted, deleted, updated = [], [], []
    for k, row in a.items():
        if k not in b:
            inserted.append(strip(row))
        else:
            changes = {c: [b[k][c], row[c]] for c in row
                       if c not in ignored and row[c] != b[k][c]}
            if changes:
                updated.append({"key": {c: row[c] for c in key_cols}, "changes": changes})
    for k, row in b.items():
        if k not in a:
            deleted.append(strip(row))
    return {"key_columns": key_cols, "ignore_columns": sorted(ignored),
            "inserted": _sort(inserted), "updated": _sort(updated), "deleted": _sort(deleted)}


def delta_multiset(before, after):
    def count(rows):
        m = {}
        for r in rows:
            k = json.dumps(r, sort_keys=True)
            m[k] = m.get(k, 0) + 1
        return m
    b, a = count(before), count(after)
    net = []
    for k, n in a.items():
        net.extend([json.loads(k)] * max(0, n - b.get(k, 0)))
    for k, n in b.items():
        net.extend([json.loads(k)] * max(0, n - a.get(k, 0)))
    return _sort(net)


# --- flow import + screenshot wrapper ------------------------------------------
spec_path = BENCH / f"bench/e2e/mamute/{test_name}/spec.json"
flow_path = BENCH / f"bench/e2e/mamute/{test_name}/flow.py"
spec = json.loads(spec_path.read_text())
flow_spec = importlib.util.spec_from_file_location(f"flow_{test_name}", flow_path)
flow = importlib.util.module_from_spec(flow_spec)
flow_spec.loader.exec_module(flow)

out_dir = CAPTURE_OUT / test_name
out_dir.mkdir(parents=True, exist_ok=True)
step = 0


def shot(page, label=None):
    global step
    step += 1
    slug = label or re.sub(r"\W+", "_", urlparse(page.url).path) or "root"
    path = out_dir / f"{step:02d}-{slug}.png"
    page.screenshot(path=str(path), full_page=True)
    print(f"  shot: {step:02d}-{slug}")


class ShotPage:
    """Delegates everything to the real page; screenshots after goto/click."""

    def __init__(self, page):
        self._page = page

    def __getattr__(self, name):
        return getattr(self._page, name)

    def goto(self, url, **kw):
        r = self._page.goto(url, **kw)
        shot(self._page)
        return r

    def click(self, selector, **kw):
        r = self._page.click(selector, **kw)
        slug = re.sub(r"\W+", "_", selector)
        shot(self._page, label=f"after-click-{slug}")
        return r


# --- main -----------------------------------------------------------------------
from playwright.sync_api import sync_playwright  # noqa: E402

tables = table_names()
print(f"capturing {test_name} against {BASE_URL} ({len(tables)} tables)")
before = {t: parse_batch(mysql(f"SELECT * FROM {t}")) for t in tables}

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(
        viewport=spec["viewport"], locale=spec["locale"], timezone_id=spec["timezone_id"])
    page = ShotPage(context.new_page())
    artifacts = flow.run(page, BASE_URL)
    browser.close()

after = {t: parse_batch(mysql(f"SELECT * FROM {t}")) for t in tables}

db_spec = json.loads((BENCH / f"bench/db/mamute/{test_name}/spec.json").read_text())
spec_tables = {t["name"]: t for t in db_spec["tables"]}
delta = {"tables": {}}
changed_elsewhere = []
for t in tables:
    if t in spec_tables:
        d = delta_table(before[t], after[t], spec_tables[t]["key_columns"],
                        spec_tables[t]["ignore_columns"])
        empty = not d["inserted"] and not d["updated"] and not d["deleted"]
        if not empty:
            delta["tables"][t] = d
    else:
        net = delta_multiset(before[t], after[t])
        if net:
            changed_elsewhere.append(f"{t} ({len(net)} rows net)")

delta_path = BENCH / f"bench/db/mamute/{test_name}/expected_delta.json"
delta_path.write_text(json.dumps(delta, indent=2) + "\n")
(out_dir / "artifacts.json").write_text(json.dumps(artifacts, indent=2) + "\n")

print(f"delta tables: {', '.join(sorted(delta['tables'])) or '(none)'}")
if changed_elsewhere:
    print("WARNING — changes outside the spec's table list (review spec):")
    for c in changed_elsewhere:
        print(f"  {c}")

frozen = delta_path.read_text()
print(f"golden delta written: {delta_path.relative_to(BENCH)}")
