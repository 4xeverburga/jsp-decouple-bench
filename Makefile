# JSP-Decouple-Bench — an Inspect evaluation
#
# Two verbs, split because solving is expensive and scoring is cheap:
#
#   make solve TASK=vote-flow AGENT='...'   -> prints the run id
#   make score RUN=<run id> [MANIFEST=...]  -> the verdict
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
# `:=` so the id is generated once: with `?=` the shell call re-runs on
# every reference and the printed id would not match the one recorded.
RUN      := $(shell python3 -c 'import uuid;print(uuid.uuid4().hex)')
LOGS     ?= out/evals
AGENT    ?= true

.PHONY: eval solve score topology manifests view check

# The whole thing: let the agent work, then grade what it left. One run id
# ties the two halves together.
eval:
	@$(MAKE) --no-print-directory solve MANIFEST=$(MANIFEST) \
		AGENT='$(AGENT)' RUN=$(RUN)
	@$(MAKE) --no-print-directory score MANIFEST=$(MANIFEST) RUN=$(RUN)

# One slice, one agent, one tree. Prints the id before running so the solve
# can be scored even if the run is interrupted.
solve:
	@echo "run: $(RUN)"
	BENCH_SANDBOX=src/bench/compose.solve.yaml \
	uv run inspect eval inspect_bench.py@solve_task \
		-T manifest_id=$(MANIFEST) -T run=$(RUN) -T agent='$(AGENT)' \
		--model mockllm/model --log-dir $(LOGS)

# Score a recorded tree. Builds the stack from it, so this is the slow half;
# re-scoring the same tree against a corrected manifest needs no agent.
score:
	BENCH_CHECKOUT=out/solves/$(RUN)/tree \
	BENCH_SANDBOX=src/bench/compose.build.yaml \
	uv run inspect eval inspect_bench.py@slice_task \
		-T manifest_id=$(MANIFEST) \
		--model mockllm/model --max-samples 1 --log-dir $(LOGS)

# Files only: the declared topology against the pin. No stack, seconds.
# Must FAIL on an untouched tree.
topology:
	BENCH_SANDBOX=src/bench/compose.prebuilt.yaml \
	uv run inspect eval inspect_bench.py@topology_task \
		-T manifest_id=$(MANIFEST) \
		--model mockllm/model --log-dir $(LOGS)

manifests:
	uv run python -m src.bench

view:
	uv run inspect view --log-dir $(LOGS)

check:
	uv run ruff check inspect_bench.py src/
