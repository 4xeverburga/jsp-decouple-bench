// Capture golden DB deltas for a mamute vote-flow behavior test.
//
// Usage:
//   node scripts/capture_delta.mjs <test-name>     e.g. vote-flow__upvote-increments-count
//
// Requires: the mamute compose stack freshly reset (down -v && up -d --wait),
// node playwright resolvable from TEST_SUITE_NODE_MODULES, docker via `sg docker`.
//
// Outputs:
//   bench/db/mamute/<test>/expected_delta.json   frozen golden delta
//   $CAPTURE_OUT/<test>/*.png                    step screenshots (review only)
//   $CAPTURE_OUT/<test>/artifacts.json           flow artifacts (dom snapshots etc.)
import { createRequire } from "node:module";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { execFileSync } from "node:child_process";
import path from "node:path";

const BENCH = path.resolve(import.meta.dirname, "..");
const TEST_SUITE_NODE_MODULES = process.env.TEST_SUITE_NODE_MODULES
  ?? "/home/ever/Documents/Me/Work/2026/Kyndryl/Tinka/DemoModernizacion/test-suite/node_modules";
const CAPTURE_OUT = process.env.CAPTURE_OUT
  ?? "/home/ever/.copilot/session-state/f795803e-47a0-42d2-a67b-b47614e310e9/files/mamute-capture";
const BASE_URL = process.env.MAMUTE_BASE_URL ?? "http://localhost:8090";
const COMPOSE = `${BENCH}/environments/mamute/compose.yml`;

const require = createRequire(path.join(TEST_SUITE_NODE_MODULES, "noop.js"));
const { chromium } = require("playwright");

const testName = process.argv[2];
if (!testName) {
  console.error("usage: capture_delta.mjs <test-name>");
  process.exit(1);
}

// --- env --------------------------------------------------------------------
const env = Object.fromEntries(
  readFileSync(`${BENCH}/environments/mamute/.env`, "utf8")
    .split("\n").filter(l => l.includes("=") && !l.startsWith("#"))
    .map(l => [l.slice(0, l.indexOf("=")).trim(), l.slice(l.indexOf("=") + 1).trim()]));
const ADMIN_USER = env.MAMUTE_ADMIN_USER;
const ADMIN_PASSWORD = env.MAMUTE_ADMIN_PASSWORD;
if (!ADMIN_USER || !ADMIN_PASSWORD) { console.error("missing admin credentials in .env"); process.exit(1); }

// --- db dump helpers ----------------------------------------------------------
function mysql(sql) {
  return execFileSync("sg", ["docker", "-c",
    `docker compose -f ${COMPOSE} exec -T db mysql -uroot mamute_development --batch -e "${sql.replace(/"/g, '\\"')}"`],
    { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
}

function parseBatch(out) {
  const lines = out.split("\n").filter(l => l.length > 0);
  if (lines.length === 0) return [];
  const cols = lines[0].split("\t");
  return lines.slice(1).map(line => {
    const vals = line.split("\t");
    const row = {};
    cols.forEach((c, i) => {
      const v = vals[i] ?? "NULL";
      row[c] = v === "NULL" ? null : v.replace(/\\n/g, "\n").replace(/\\t/g, "\t").replace(/\\\\/g, "\\");
    });
    return row;
  });
}

function dumpTable(table) {
  return parseBatch(mysql(`SELECT * FROM ${table}`));
}

function tableNames() {
  return parseBatch(mysql("SHOW TABLES")).map(r => Object.values(r)[0]);
}

// --- delta --------------------------------------------------------------------
// Rows are compared as full-tuple strings; NULL -> null. Deterministic ordering.
const rowKey = row => JSON.stringify(row);
const sortRows = rows => rows.slice().sort((a, b) => rowKey(a) < rowKey(b) ? -1 : 1);

function deltaTable(before, after, keyCols, ignoreCols) {
  const ignored = new Set(ignoreCols ?? []);
  const strip = row => Object.fromEntries(Object.entries(row).filter(([c]) => !ignored.has(c)));
  const keyOf = row => JSON.stringify(keyCols.map(c => row[c]));
  const b = new Map(before.map(r => [keyOf(r), r]));
  const a = new Map(after.map(r => [keyOf(r), r]));
  const inserted = [], deleted = [], updated = [];
  for (const [k, row] of a) {
    if (!b.has(k)) inserted.push(strip(row));
    else {
      const changes = {};
      for (const col of Object.keys(row)) {
        if (!ignored.has(col) && row[col] !== b.get(k)[col]) changes[col] = [b.get(k)[col], row[col]];
      }
      if (Object.keys(changes).length > 0) updated.push({ key: Object.fromEntries(keyCols.map(c => [c, row[c]])), changes });
    }
  }
  for (const [k, row] of b) if (!a.has(k)) deleted.push(strip(row));
  return { key_columns: keyCols, ignore_columns: [...ignored], inserted: sortRows(inserted), updated: sortRows(updated), deleted: sortRows(deleted) };
}

function deltaMultiset(before, after) {
  const count = rows => {
    const m = new Map();
    for (const r of rows) m.set(rowKey(r), (m.get(rowKey(r)) ?? 0) + 1);
    return m;
  };
  const b = count(before), a = count(after);
  const net = [];
  for (const [k, n] of a) { const d = n - (b.get(k) ?? 0); if (d > 0) net.push(...Array(d).fill(JSON.parse(k))); }
  for (const [k, n] of b) { const d = (a.get(k) ?? 0) - n; if (d < 0) net.push(...Array(-d).fill(JSON.parse(k))); }
  return sortRows(net);
}

// --- flow (faithful port of bench/e2e/mamute/<test>/flow.py) --------------------
const ARRANGE = {
  email: "author@bench.test", password: "bench-author-pass", name: "Bench Author",
  title: "How do I decouple a JSP frontend from its backend?",
  body: "I have a legacy JSP page that renders questions server side. "
    + "What is the recommended way to expose the same data through REST "
    + "endpoints instead of rendering HTML on the server?",
  tags: "jsp",
};

function normalize(html) {
  return html.replace(/<script\b.*?<\/script>/gis, "")
    .replace(/<style\b.*?<\/style>/gis, "")
    .replace(/\s+/g, " ").trim();
}

async function runFlow(page, shot) {
  const { goto: gotoRaw, click: clickRaw } = page;
  page.goto = async (url, opts) => { const r = await gotoRaw.call(page, url, opts); await shot(page); return r; };

  // arrange: author signs up and asks a question
  await page.goto(BASE_URL + "/sign-up");
  await page.waitForLoadState("networkidle");
  await page.fill("#name", ARRANGE.name);
  await page.fill("#email", ARRANGE.email);
  await page.fill("#password", ARRANGE.password);
  await page.fill("#password-confirmation", ARRANGE.password);
  await shot(page, "signup-filled");
  await Promise.all([
    page.waitForNavigation({ waitUntil: "load" }),
    clickRaw.call(page, "input[type=submit]"),
  ]);
  await page.waitForLoadState("networkidle");

  await page.goto(BASE_URL + "/ask");
  await page.waitForLoadState("networkidle");
  await page.fill("input[name=title]", ARRANGE.title);
  await page.fill("textarea[name=description]", ARRANGE.body);
  // tagNames is a select2 v3 widget (the real input is hidden); drive the UI:
  // focus -> type >= 3 chars (minimumInputLength) -> wait for the AJAX result -> pick it
  await page.click(".select2-container");
  await page.fill(".select2-input", ARRANGE.tags);
  await page.waitForSelector(".select2-result-selectable", { timeout: 5000 });
  await page.click(".select2-result-selectable");
  await shot(page, "ask-filled");
  await Promise.all([
    page.waitForNavigation({ waitUntil: "load" }),
    clickRaw.call(page, "input[type=submit]"),
  ]);
  await page.waitForLoadState("networkidle");
  const questionUrl = page.url(); // redirected to /{question.id}-{sluggedTitle}

  await page.goto(BASE_URL + "/logout");
  await page.waitForLoadState("networkidle");

  // act: moderator votes through the vote widget
  await page.goto(BASE_URL + "/login");
  await page.waitForLoadState("networkidle");
  await page.fill("input[name=email]", ADMIN_USER);
  await page.fill("input[name=password]", ADMIN_PASSWORD);
  await shot(page, "login-filled");
  await Promise.all([
    page.waitForNavigation({ waitUntil: "load" }),
    clickRaw.call(page, "input[type=submit]"),
  ]);
  await page.waitForLoadState("networkidle");

  await page.goto(questionUrl);
  await page.waitForLoadState("networkidle");

  const voteContainer = page.locator(".vote-container").first();
  const countBefore = (await voteContainer.locator(".vote-count").innerText()).trim();
  const domBefore = normalize(await page.content());
  await shot(page, "question-before-vote");

  const votePath = testName.includes("downvote") ? "/voto/negativo" : "/voto/positivo";
  const arrow = testName.includes("downvote") ? "a.down-arrow" : "a.up-arrow";
  const [resp] = await Promise.all([
    page.waitForResponse(r => r.url().includes(votePath)),
    clickRaw.call(page, arrow),
  ]);
  if (resp.status() !== 200) throw new Error(`vote POST failed with HTTP ${resp.status()}`);
  await page.waitForFunction(
    count => {
      const el = document.querySelector(".vote-container .vote-count");
      return el && el.textContent.trim() !== count;
    }, countBefore, { timeout: 5000 });
  await shot(page, "after-vote");

  const countAfter = (await voteContainer.locator(".vote-count").innerText()).trim();
  const domAfter = normalize(await page.content());
  const expected = testName.includes("downvote") ? "-1" : "1";
  if (countAfter !== expected) throw new Error(`expected vote count '${expected}' after vote, got '${countAfter}'`);

  return {
    question_url: questionUrl,
    vote_count_before: countBefore,
    vote_count_after: countAfter,
    dom_before: domBefore,
    dom_after: domAfter,
  };
}

// --- main -----------------------------------------------------------------------
const spec = JSON.parse(readFileSync(`${BENCH}/bench/e2e/mamute/${testName}/spec.json`, "utf8"));
const outDir = `${CAPTURE_OUT}/${testName}`;
mkdirSync(outDir, { recursive: true });

let step = 0;
const shot = async (page, label) => {
  step += 1;
  const name = label ?? `step-${String(step).padStart(2, "0")}-${new URL(page.url()).pathname.replace(/\W+/g, "_")}`;
  await page.screenshot({ path: `${outDir}/${String(step).padStart(2, "0")}-${name}.png`, fullPage: true });
  console.log(`  shot: ${step}-${name}`);
};

const tables = tableNames();
console.log(`capturing ${testName} against ${BASE_URL} (${tables.length} tables)`);

const before = Object.fromEntries(tables.map(t => [t, dumpTable(t)]));

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: spec.viewport, locale: spec.locale, timezoneId: spec.timezone_id,
});
const page = await context.newPage();
const artifacts = await runFlow(page, shot);
await browser.close();

const after = Object.fromEntries(tables.map(t => [t, dumpTable(t)]));

// delta for the spec-declared tables (key-based), multiset net for the rest
const dbSpec = JSON.parse(readFileSync(`${BENCH}/bench/db/mamute/${testName}/spec.json`, "utf8"));
const specTables = new Map(dbSpec.tables.map(t => [t.name, t]));
const delta = { tables: {} };
const changedElsewhere = [];
for (const t of tables) {
  const d = specTables.has(t)
    ? deltaTable(before[t], after[t], specTables.get(t).key_columns, specTables.get(t).ignore_columns)
    : { inserted: deltaMultiset(before[t], after[t]) };
  const empty = d.inserted.length === 0 && (d.updated?.length ?? 0) === 0 && (d.deleted?.length ?? 0) === 0;
  if (!empty) {
    if (specTables.has(t)) delta.tables[t] = d;
    else changedElsewhere.push(`${t} (${d.inserted.length} rows net)`);
  }
}

writeFileSync(`${BENCH}/bench/db/mamute/${testName}/expected_delta.json`, JSON.stringify(delta, null, 2) + "\n");
writeFileSync(`${outDir}/artifacts.json`, JSON.stringify(artifacts, null, 2) + "\n");

console.log(`delta tables: ${Object.keys(delta.tables).join(", ") || "(none)"}`);
if (changedElsewhere.length > 0) {
  console.log(`WARNING — changes outside the spec's table list (review spec):`);
  for (const c of changedElsewhere) console.log(`  ${c}`);
}
console.log(`artifacts: ${outDir}/artifacts.json`);
console.log(`golden delta written: bench/db/mamute/${testName}/expected_delta.json`);
