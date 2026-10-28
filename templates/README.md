# `templates/` — the stack shape every sample commits

`compose.template.yaml` is the one stack shape shared by every sample.
It exists so that `network_isolation` has a stable vocabulary (`front`,
`back`, `db`, `api`, `data`) and so that "the data side is isolatable" is
a property of the sample, not of whatever names an agent invents.

## The two shapes

| | at the pin (captured) | after the work (graded) |
|---|---|---|
| `front` networks | `api`, `data` | `api` |
| `back` networks | — (does not exist) | `api`, `data` |
| `db` networks | `data` | `data` |
| published host ports | `front` only | `front` only |
| isolation assertion | **fails** | **passes** |

The pin is deliberately non-conformant. That is the only reason the
assertion is falsifiable: an untouched tree must fail it, and only real
work can make it pass.

## Rules

1. **One repository, one application.** `front` and `back` are built from
   the same context. The sample is not two projects; it is one app whose
   data side has been made isolatable, so the frontend can be refactored
   later without the data side moving.
2. **Only `front` publishes.** The harness reaches the database through
   `compose exec`, so publishing it would widen the surface the gate
   allows for no reason.
3. **No `network_mode:`.** Neither `host` nor `service:` — both escape
   the declared topology.
4. **Add services, never networks.** A new service (collector, sidecar,
   worker) joins `api` or `data`. A new network at the top level is a
   change to the contract and belongs in this template first.
5. **The baseline is the pinned file.** The gate reads the contract from
   `git show <commit_sha>:compose.yaml`, never from the worktree, so an
   agent cannot widen its own allowance by editing the file. It is
   **static**: both files are rendered with `compose config` and compared;
   no container is started.

## Applying it

```bash
cp templates/compose.template.yaml ../<sample>/compose.yaml
# adapt the lines marked "kept", then commit it at the pin before capturing
```

The copied file is read by whoever gets the checkout, so the authoring
guidance lives here, not in the YAML: `compose.template.yaml` carries no
`ADAPT` markers, no mention of gates, pins or goldens, and no sentence
that tells the reader what the work is. Anything you want to say to
yourself goes in this README (and §1 of `prepare-repo-for-dataset` has the
grep that keeps it that way).

`prepare-repo-for-dataset` §2 covers the authoring side;
`dataset-ready-check` §1–3 verifies conformance and falsifiability.
