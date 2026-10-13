#!/usr/bin/env python3
"""Capture golden DB deltas by running the test's own flow.py.

Usage:
  .venv/bin/python scripts/capture_delta.py <sample> <test-name>
      e.g. capture_delta.py mamute vote-flow__upvote-increments-count
           capture_delta.py openclinica study-flow__study-creation

Requires: the sample's stack freshly reset (pristine state is mandatory:
ids must match across runs), the sample's DB reachable, python playwright
installed (.venv). Sample-specific knobs (base URL, DB access command,
table-list query) live in environments/<sample>/capture.env.

The flow under bench/e2e/<sample>/<test>/flow.py is the single source of
truth: this script imports it, runs run(page, base_url) against the
pristine app, and freezes the before/after DB delta. Screenshots are taken
after every goto/click for review only.

Outputs:
  bench/e2e/<sample>/<test>/images/*.png          step screenshots (traceability)
  bench/e2e/<sample>/<test>/artifacts.json        flow artifacts (dom snapshots etc.)
  bench/db/<sample>/<test>/expected_delta.json    frozen golden delta
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

if len(sys.argv) != 3:
    sys.exit(__doc__)
sample, test_name = sys.argv[1], sys.argv[2]


def load_kv(path):
    env = {}
    if Path(path).exists():
        for line in Path(path).read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


COV = load_kv(BENCH / "environments" / sample / "capture.env")
BASE_URL = os.environ.get(f"{sample.upper()}_BASE_URL", COV.get("CAPTURE_BASE_URL"))
if not BASE_URL:
    sys.exit(f"missing CAPTURE_BASE_URL in environments/{sample}/capture.env")

# flows read credentials from the harness-injected environment only
for k, v in load_kv(BENCH / COV.get("CAPTURE_ENV_FILE", "")).items():
    os.environ.setdefault(k, v)

DB_CMD = COV["CAPTURE_DB_CMD"]
LIST_TABLES_SQL = COV["CAPTURE_LIST_TABLES_SQL"]


# --- db dump helpers ----------------------------------------------------------
def db(sql):
    # the command template reads the SQL from stdin — no quoting pitfalls
    env = dict(os.environ, BENCH=str(BENCH))
    return subprocess.run(["bash", "-c", DB_CMD],
                          input=sql, capture_output=True, text=True,
                          check=True, env=env).stdout


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
    return [list(r.values())[0] for r in parse_batch(db(LIST_TABLES_SQL))]


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
spec_path = BENCH / f"bench/e2e/{sample}/{test_name}/spec.json"
flow_path = BENCH / f"bench/e2e/{sample}/{test_name}/flow.py"
spec = json.loads(spec_path.read_text())
flow_spec = importlib.util.spec_from_file_location(f"flow_{test_name}", flow_path)
flow = importlib.util.module_from_spec(flow_spec)
flow_spec.loader.exec_module(flow)

out_dir = BENCH / f"bench/e2e/{sample}/{test_name}/images"
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
print(f"capturing {sample}/{test_name} against {BASE_URL} ({len(tables)} tables)")
before = {t: parse_batch(db(f"SELECT * FROM {t}")) for t in tables}

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(
        viewport=spec["viewport"], locale=spec["locale"], timezone_id=spec["timezone_id"])
    page = ShotPage(context.new_page())
    artifacts = flow.run(page, BASE_URL)
    browser.close()

after = {t: parse_batch(db(f"SELECT * FROM {t}")) for t in tables}

db_spec = json.loads((BENCH / f"bench/db/{sample}/{test_name}/spec.json").read_text())
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

delta_path = BENCH / f"bench/db/{sample}/{test_name}/expected_delta.json"
delta_path.write_text(json.dumps(delta, indent=2) + "\n")
(BENCH / f"bench/e2e/{sample}/{test_name}/artifacts.json").write_text(
    json.dumps(artifacts, indent=2) + "\n")

print(f"delta tables: {', '.join(sorted(delta['tables'])) or '(none)'}")
if changed_elsewhere:
    print("WARNING — changes outside the spec's table list (review spec):")
    for c in changed_elsewhere:
        print(f"  {c}")

frozen = delta_path.read_text()
print(f"golden delta written: {delta_path.relative_to(BENCH)}")
