"""Contract enforcement test.

Purpose: the design post-mortem (July 14-18) found that faults came from
functions that touched external systems without a stated contract — a
sentence saying what valid output looks like, and where each output field
comes from. Writing that contract before the code is the discipline. This
test makes the contract impossible to *silently drop*: if someone edits a
contracted function and removes its contract, this test goes red, and the
red test blocks the push (it runs inside "test locally, then push").

Scope (Option A, July 27): this guards the functions that CURRENTLY carry
contracts against regression. It does not yet require contracts on every
external-facing function — that stricter mode (Option B) is a later step,
tracked in FAULTS.md. To graduate: move a function from EXTERNAL_FACING_TODO
into CONTRACTED once it has a contract, and the test will enforce it.

A contract is two docstring lines:
    Valid output: <one falsifiable sentence about a correct result>
    Provenance:   <each output field <- the input it derives from>

Note the honest limit: this checks the contract EXISTS, not that it is
correct. A lazy contract passes. It is a forcing function for the habit,
not a proof of correctness.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

# Functions that carry a contract today and must keep it.
# Format: (relative file path, function name)
CONTRACTED = [
    ("src/integrations/hubspot/client.py", "_first_association_id"),
    ("src/revenue/churn.py", "resolve_at_risk_companies"),
    ("src/api/routes/exa.py", "_check_one_company"),
]

# External-facing functions that SHOULD get a contract eventually but do not
# have one yet. Listed here so the gap is visible and tracked, not forgotten.
# Moving one into CONTRACTED (after writing its contract) makes the test
# enforce it. This list is documentation, not enforced.
EXTERNAL_FACING_TODO = [
    ("src/integrations/exa/client.py", "company_brief"),
    ("src/revenue/yield_.py", "compute_yield"),
    ("src/integrations/hubspot/client.py", "fetch_all_deals"),
    ("src/integrations/hubspot/sync.py", "sync_deals"),
]

CONTRACT_MARKERS = ("Valid output:", "Provenance:")


def _get_function_docstring(file_path: Path, func_name: str) -> str | None:
    """Return the docstring of `func_name` in `file_path`, or None if the
    function or its docstring is missing."""
    tree = ast.parse(file_path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            return ast.get_docstring(node)
    return None


def test_contracted_functions_have_contracts():
    """Every function in CONTRACTED must retain both contract lines."""
    failures = []

    for rel_path, func_name in CONTRACTED:
        file_path = REPO_ROOT / rel_path

        if not file_path.exists():
            failures.append(f"{rel_path}: file not found")
            continue

        doc = _get_function_docstring(file_path, func_name)

        if doc is None:
            failures.append(
                f"{rel_path}::{func_name} — function or docstring missing"
            )
            continue

        missing = [m for m in CONTRACT_MARKERS if m not in doc]
        if missing:
            failures.append(
                f"{rel_path}::{func_name} — contract missing lines: {', '.join(missing)}"
            )

    assert not failures, "Contract check failed:\n  " + "\n  ".join(failures)


if __name__ == "__main__":
    # Allow running directly: `python test_contracts.py`
    try:
        test_contracted_functions_have_contracts()
        print(f"OK — all {len(CONTRACTED)} contracted functions retain their contracts.")
        if EXTERNAL_FACING_TODO:
            print(
                f"\nNote: {len(EXTERNAL_FACING_TODO)} external-facing functions "
                f"still lack contracts (tracked, not enforced):"
            )
            for rel_path, func_name in EXTERNAL_FACING_TODO:
                print(f"  - {rel_path}::{func_name}")
    except AssertionError as e:
        print("FAILED —", e)
        raise
