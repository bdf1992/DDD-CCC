"""Expose the four-proof harness through pytest.

The canonical runner is `cube proofs` (equivalently
`python -m s3.cubes.run_proofs`). The proof modules under
`s3/cubes/**/tests/*_test.py` are not pytest tests: each exports `run()`
returning a result dict, so a bare `pytest` reports "no tests ran" on a
repository that does have a working suite.

This module bridges the two, so `pytest` is an honest entry point without
displacing `cube proofs` as the authority.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PROOF_MODULES = [
    "s3.cubes.metrics.tests.vacuum_test",
    "s3.cubes.adapters.tests.obsidian_vault_test",
    "s3.cubes.adapters.tests.regency_test",
    "s3.cubes.adapters.tests.csharp_unity_test",
]


@pytest.mark.parametrize("module_name", PROOF_MODULES)
def test_proof_module_passes(module_name: str) -> None:
    """Each proof module's `run()` reports every one of its proofs green."""
    module = importlib.import_module(module_name)
    result = module.run()
    assert result["passed"], f"{module_name}: {result.get('summary')}\n{result.get('details')}"


@pytest.mark.parametrize("module_name", PROOF_MODULES)
def test_proof_module_skill_test_passes(module_name: str) -> None:
    """Each proof module's skill-test fixture round-trips, where it declares one."""
    module = importlib.import_module(module_name)
    runner = getattr(module, "run_skill_test", None)
    fixture = getattr(module, "FIXTURE", None)
    if runner is None or fixture is None:
        pytest.skip(f"{module_name} declares no skill-test fixture")
    result = runner(str(fixture))
    assert result["passed"], f"{module_name}: {result.get('summary')}\n{result.get('details')}"
