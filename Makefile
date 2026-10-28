# JSP-Decouple-Bench — an Inspect evaluation
#
# The checkout under test and the URL its stack publishes come from the
# environment Inspect runs in, so export them once per shell:
#
#   export BENCH_CHECKOUT=/abs/checkout                              # the tree
#   export BENCH_BASE_URL=http://localhost:8080                      # published port
#   export APP_HTTP_PORT=8080 MAMUTE_PUBLIC_URL=$BENCH_BASE_URL      # compose subst.
#   export MAMUTE_FRONT_IMAGE=<prebuilt front image>                 # skip the build
#   set -a; . "$BENCH_CHECKOUT/.env"; set +a                         # sample creds
#
#   make topology SAMPLE=mamute MANIFEST=vote-flow   # shape gate, no stack, seconds
#   make slice    SAMPLE=mamute MANIFEST=vote-flow   # boots a stack per case
#   make view                                        # browse the logs
#   make check                                       # lint

SAMPLE   ?= mamute
MANIFEST ?= vote-flow
LOGS     ?= out/evals

.PHONY: topology slice view check

# Reads files only: the declared topology against the pin. Must FAIL on an
# untouched tree, because the pristine app reads the database directly.
topology:
	uv run inspect eval inspect_bench.py@topology_task \
		-T sample=$(SAMPLE) -T manifest=$(MANIFEST) \
		--model mockllm/model --log-dir $(LOGS)

# One Sample per case, so Inspect boots a fresh stack for each — the goldens
# were captured on a pristine database. Sequential, because every stack
# publishes the same host port.
slice:
	uv run inspect eval inspect_bench.py@slice_task \
		-T sample=$(SAMPLE) -T manifest=$(MANIFEST) \
		--model mockllm/model --max-samples 1 --log-dir $(LOGS)

view:
	uv run inspect view --log-dir $(LOGS)

check:
	uv run ruff check inspect_bench.py src/
