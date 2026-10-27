"""src/run/context.py — everything a task or a gate is allowed to know.

Built once per invocation. It is also the only place that resolves an
adapter, so tasks and gates never import an adapter module directly.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import config
from src.errors import NotFound
from src.run.paths import RunPaths


@dataclass
class RunContext:
    run_id: str
    paths: RunPaths
    manifest: dict[str, Any]
    sample_location: Path
    _adapters: dict[str, Any] = field(default_factory=dict, repr=False)

    # --- manifest view -------------------------------------------------------
    @property
    def sample(self) -> dict[str, Any]:
        return self.manifest["sample"]

    @property
    def bindings(self) -> dict[str, Any]:
        return self.manifest["bindings"]

    @property
    def scope(self) -> dict[str, Any]:
        return self.manifest["scope"]

    @property
    def cases_dir(self) -> Path:
        return Path(config.CASES_DIR) / self.sample["slug"]

    def binding(self, capability: str) -> dict[str, Any]:
        if capability not in self.bindings:
            raise NotFound(
                f"manifest {self.manifest['manifest_id']} binds no '{capability}' "
                f"adapter (has: {sorted(self.bindings)})"
            )
        return self.bindings[capability]

    # --- adapters ------------------------------------------------------------
    def adapter(self, capability: str) -> Any:
        if capability not in self._adapters:
            from src.harness.registry import resolve

            self._adapters[capability] = resolve(self, capability)
        return self._adapters[capability]

    def stack(self) -> Any:
        return self.adapter("stack")

    def base_url(self) -> str:
        return self.stack().base_url()

    # --- cases ---------------------------------------------------------------
    def case(self, name: str) -> dict[str, Any]:
        path = self.cases_dir / name / "case.json"
        if not path.is_file():
            raise NotFound(f"no such case: {path}")
        return json.loads(path.read_text())

    def expect(self, name: str) -> dict[str, Any]:
        path = self.cases_dir / name / "expect.json"
        if not path.is_file():
            raise NotFound(f"case {name} has no expect.json — run `make case-capture`")
        return json.loads(path.read_text())

    def flow_file(self, name: str) -> Path:
        path = self.cases_dir / name / "flow.py"
        if not path.is_file():
            raise NotFound(f"no such flow: {path}")
        return path

    # --- construction --------------------------------------------------------
    @classmethod
    def load(cls, run_id: str, manifest: dict[str, Any]) -> "RunContext":
        """Rebuild the context of an existing run from its task.json."""
        paths = RunPaths.load(run_id)
        if not paths.task_json.is_file():
            raise NotFound(f"run {run_id} has no task.json — was it started with `make task`?")
        task = json.loads(paths.task_json.read_text())
        return cls(
            run_id=run_id,
            paths=paths,
            manifest=manifest,
            sample_location=Path(task["sample"]["location"]),
        )
