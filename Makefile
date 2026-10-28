# JSP-Decouple-Bench — an Inspect evaluation
#
# One command runs an agent and then every scorer assigned by its manifest:
#
#   make task MANIFEST=3 AGENT='...'
#
# The checkout and the stack's published URL come from the environment:
#
#   export BENCH_CHECKOUT=/abs/checkout
#   export BENCH_BASE_URL=http://localhost:8080
#   export APP_HTTP_PORT=8080 MAMUTE_PUBLIC_URL=$BENCH_BASE_URL
#   export BENCH_AGENT_IMAGE=<toolbox image the agent runs in>
#   set -a; . "$BENCH_CHECKOUT/.env"; set +a        # the sample's credentials

# The manifest id is the unit of work: it names the sample, the slice, the
# task type and the cases. Run `make manifests` to see them.
MANIFEST ?= 3
TASK_TYPE := $(shell uv run python -c 'from src.bench.seeds import manifest; print(manifest($(MANIFEST))["task_type"])')
# `:=` so the id is generated once: with `?=` the shell call re-runs on
# every reference and the printed id would not match the one recorded.
RUN      := $(shell python3 -c 'import uuid;print(uuid.uuid4().hex)')
LOGS     ?= out/evals
AGENT    ?= true

.PHONY: task manifests view check

# One manifest, one agent run, then its assigned scorers. Both Inspect
# phases share this run id; scoring reads the tree captured by solving.
task:
	@echo "run: $(RUN)"
	BENCH_SANDBOX=src/bench/compose.solve.yaml \
	uv run inspect eval inspect_bench.py@$(TASK_TYPE) \
		-T manifest_id=$(MANIFEST) -T phase=solve -T run=$(RUN) \
		-T agent='$(AGENT)' \
		--model mockllm/model --display plain --log-dir $(LOGS)
	@export BENCH_CHECKOUT=$(CURDIR)/out/solves/$(RUN)/tree; \
	trap 'rm -f "$$BENCH_CHECKOUT/.bench-inspect-compose.yaml"' EXIT; \
	uv run inspect eval inspect_bench.py@$(TASK_TYPE) \
		-T manifest_id=$(MANIFEST) -T phase=score \
		--model mockllm/model --max-samples 1 --display plain \
		--log-dir $(LOGS)

manifests:
	uv run python -m src.bench

view:
	uv run inspect view --log-dir $(LOGS)

check:
	uv run ruff check inspect_bench.py src/
