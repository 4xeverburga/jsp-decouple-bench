# JSP-Decouple-Bench — the two commands
#
#   make setup SAMPLE=<name>                        build + compose up --wait
#   make eval SAMPLE=<name> TASK=<t> AGENT=<a>      run harness, emit verdict.json
#
SAMPLE ?= mamute
TASK   ?= vote-flow
AGENT  ?= pristine

COMPOSE = docker compose -f environments/$(SAMPLE)/compose.yml

.PHONY: setup eval down verify-manifest help

help:
	@echo "make setup SAMPLE=$(SAMPLE)   — build image, start stack, wait for healthcheck"
	@echo "make eval  SAMPLE=$(SAMPLE) TASK=$(TASK) AGENT=$(AGENT) — run harness"

setup: ## build image and start the stack; returns only when healthy
	$(COMPOSE) build
	$(COMPOSE) up -d --wait
	@echo "Sample '$(SAMPLE)' is up."

verify-manifest: ## step 0 of every eval: bench/ must be unmodified
	python3 bench/harness/manifest.py verify bench/MANIFEST.sha256

eval: verify-manifest ## run the harness for one task; emits verdict.json
	@echo "TODO: harness not yet implemented (Mamute vote-flow vertical slice)"
	@echo "Planned: build gate -> parity replay -> db delta -> no-server-html -> verdict.json"
	@exit 2

down:
	$(COMPOSE) down -v
