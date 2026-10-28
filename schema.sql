-- schema.sql — registry for the JSP decoupling bench. See specs/er.md.
-- Inputs only. Gate results live in out/runs/<run_id>/gates/*.json.

-- Bump when this file changes shape; `make db-init` refuses to reuse a DB
-- built from a different version (never silently migrations-by-luck).
PRAGMA user_version = 2;

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS technology (
    technology_id INTEGER PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    kind          TEXT NOT NULL CHECK (kind IN
        ('language','runtime','framework','database','server','other'))
);

CREATE TABLE IF NOT EXISTS sample (
    sample_id   INTEGER PRIMARY KEY,
    slug        TEXT NOT NULL UNIQUE,
    -- project_id is the original upstream owner/repo; source is the copy we build from.
    project_id  TEXT NOT NULL,
    source      TEXT,
    branch      TEXT NOT NULL,
    commit_sha  TEXT NOT NULL,
    license     TEXT,
    description TEXT,
    entrypoint  TEXT,
    target_url  TEXT,
    UNIQUE (project_id, branch, commit_sha)
);

CREATE TABLE IF NOT EXISTS sample_technology (
    sample_id     INTEGER NOT NULL REFERENCES sample(sample_id) ON DELETE CASCADE,
    technology_id INTEGER NOT NULL REFERENCES technology(technology_id) ON DELETE RESTRICT,
    PRIMARY KEY (sample_id, technology_id)
);

CREATE TABLE IF NOT EXISTS task_type (
    task_type_id INTEGER PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    description  TEXT
);

CREATE TABLE IF NOT EXISTS task_manifest (
    manifest_id  INTEGER PRIMARY KEY,
    sample_id    INTEGER NOT NULL REFERENCES sample(sample_id) ON DELETE RESTRICT,
    task_type_id INTEGER NOT NULL REFERENCES task_type(task_type_id) ON DELETE RESTRICT,
    -- the feature boundary this manifest is about: 'vote-flow', 'study-flow'.
    -- task_type is the *kind* of work; name is *which* work.
    name         TEXT NOT NULL,
    version      INTEGER NOT NULL,
    prompt       TEXT NOT NULL,
    bindings_json TEXT NOT NULL,
    scope_json   TEXT NOT NULL,
    UNIQUE (sample_id, name, version)
);

CREATE TABLE IF NOT EXISTS task_run (
    run_id             TEXT PRIMARY KEY,
    manifest_id        INTEGER NOT NULL REFERENCES task_manifest(manifest_id) ON DELETE RESTRICT,
    started_at         TEXT NOT NULL,
    finished_at        TEXT,
    harness            TEXT NOT NULL,
    environment        TEXT,
    estimated_cost_usd REAL,
    run_duration_s     REAL
);

CREATE INDEX IF NOT EXISTS idx_task_run_manifest ON task_run(manifest_id);

-- Gates simply exist: no FK to task or manifest, no ordering column.
CREATE TABLE IF NOT EXISTS gate (
    gate_id     TEXT NOT NULL,
    version     INTEGER NOT NULL,
    description TEXT NOT NULL,
    threshold   REAL NOT NULL CHECK (threshold >= 0),
    direction   TEXT NOT NULL CHECK (direction IN ('minimize','maximize')),
    PRIMARY KEY (gate_id, version)
);

CREATE VIEW IF NOT EXISTS v_run AS
SELECT r.run_id, r.started_at, r.finished_at, r.harness,
       m.manifest_id, m.name AS task, m.version AS manifest_version, m.prompt,
       s.slug AS sample, s.project_id, s.commit_sha, s.entrypoint,
       t.name AS task_type
FROM task_run r
JOIN task_manifest m ON m.manifest_id = r.manifest_id
JOIN sample s        ON s.sample_id   = m.sample_id
JOIN task_type t     ON t.task_type_id = m.task_type_id;
