# JSP-Decouple-Bench
#
# Two verbs. Everything else is `python3 main.py ...`.
#
#   make db-init
#   make task  MANIFEST_ID=1 SAMPLE_SANDBOX=/abs/tmp/run-id   # -> run_id
#   make gate  GATE_ID=functional_parity RUN_ID=<run_id>      # -> value

PYTHON ?= python3

MANIFEST_ID     ?=
SAMPLE_SANDBOX  ?=
HARNESS         ?=
HARNESS_CMD     ?=
GATE_ID         ?=
GATE_VERSION    ?=
RUN_ID          ?=
SAMPLE          ?=
TASK            ?=
CASE            ?=

# optional task arguments, expanded inline so neither can leave a dangling
# line-continuation (a comment must never end with a backslash here: it would
# swallow the next line)
HARNESS_ARG      = $(if $(HARNESS),--harness '$(HARNESS)')
HARNESS_CMD_ARG  = $(if $(HARNESS_CMD),--harness-cmd '$(HARNESS_CMD)')

.PHONY: help db-init db-init-force samples manifests runs task gate case-capture

help:
	@echo "make db-init                                    build bench.db from schema.sql + seeds"
	@echo "make task  MANIFEST_ID=1 SAMPLE_SANDBOX=/abs/tmp/run-id [HARNESS=<label>]"
	@echo "         or  SAMPLE=mamute TASK=vote-flow SAMPLE_SANDBOX=/abs/tmp/run-id"
	@echo "         SAMPLE_SANDBOX is the folder THIS run owns (absolute, absent or empty)."
	@echo "         The bench puts the pin's only checkout there from the local mirror"
	@echo "         out/cache/<slug>.git and refuses a folder holding anything else:"
	@echo "         a sibling tree would be somewhere to look for the answer."
	@echo "         the agent is the command in BENCH_HARNESS_CMD (.env), or"
	@echo "         HARNESS_CMD='my-agent ...' for a single run; the prompt"
	@echo "         arrives on stdin. HARNESS=<label> only names the run."
	@echo "make gate  GATE_ID=functional_parity RUN_ID=<run_id> [GATE_VERSION=1]"
	@echo "make case-capture SAMPLE=mamute CASE=<case> SAMPLE_SANDBOX=/abs/tmp/capture-id"
	@echo "make samples | manifests | runs                 inspect the registry"
	@echo "the pin is SAMPLE.commit_sha in seeds/samples.json -> make db-init"

db-init:
	$(PYTHON) main.py db init

db-init-force:
	$(PYTHON) main.py db init --force

samples:
	$(PYTHON) main.py db samples

manifests:
	$(PYTHON) main.py db manifests

runs:
	$(PYTHON) main.py db runs

task:
	@test -n "$(SAMPLE_SANDBOX)" || (echo "SAMPLE_SANDBOX is required" && exit 2)
	$(PYTHON) main.py task run \
		$(if $(MANIFEST_ID),--manifest $(MANIFEST_ID),--sample $(SAMPLE) --task $(TASK)) \
		--sample-sandbox "$(SAMPLE_SANDBOX)" $(HARNESS_ARG) $(HARNESS_CMD_ARG)

gate:
	@test -n "$(GATE_ID)" || (echo "GATE_ID is required" && exit 2)
	@test -n "$(RUN_ID)" || (echo "RUN_ID is required" && exit 2)
	$(PYTHON) main.py gate run --gate $(GATE_ID) --run $(RUN_ID) $(if $(GATE_VERSION),--gate-version $(GATE_VERSION))

case-capture:
	@test -n "$(SAMPLE)" -a -n "$(CASE)" -a -n "$(SAMPLE_SANDBOX)" || \
		(echo "SAMPLE, CASE and SAMPLE_SANDBOX are required" && exit 2)
	$(PYTHON) main.py case capture --sample $(SAMPLE) --case $(CASE) \
		--sample-sandbox "$(SAMPLE_SANDBOX)"
