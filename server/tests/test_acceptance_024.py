"""TICKET-024 end-to-end acceptance: the two data-level cross-checks.

The ticket's checklist is verified mainly by running the existing suites; these
tests pin the comparisons that had no automated coverage, reading `SPEC.md`
§5.4 as the independent source of truth:

B) every §5.4 endpoint is published in `contracts/openapi.json` — including the
   `/regression/*` trio TICKET-023 added.
C) the AC-B-41 error-branch table covers every §5.4 endpoint and never
   understates the §5.4 error codes, and the published contract declares them.

The `http-contract` divergence subset (H-1…H-12) is handed to 024 by the
registry; 024 consumes it, starting by pinning the subset it answers for.
"""

import json
import re
from pathlib import Path

from regression.divergences import http_contract_ids, load_registry
from tests.test_declared_error_branches import SPEC_ERROR_BRANCHES

SERVER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVER_ROOT.parent
CONTRACTS = REPO_ROOT / "contracts"
SPEC = REPO_ROOT / "SPEC.md"

_PATH_PARAM = re.compile(r"\{[^}]+\}")
_ROW = re.compile(r"\|\s*(GET|POST|PUT|DELETE)\s*\|\s*`([^`]+)`\s*\|(.*)\|\s*$")


def _normalize(path: str) -> str:
    """Collapse path parameters so `{id}` and `{entity_id}` compare equal."""
    return _PATH_PARAM.sub("{}", path)


def _spec_error_cell(rest: str) -> set[int]:
    cell = [part.strip() for part in rest.split("|")][-1]
    if cell in ("—", "-", ""):
        return set()
    return {int(code) for code in re.findall(r"\d+", cell)}


def spec_5_4() -> dict[tuple[str, str], set[int]]:
    """Parse the endpoint table of `SPEC.md` §5.4 into (method, path) → errors."""
    lines = SPEC.read_text(encoding="utf-8").splitlines()
    start = next(
        index for index, line in enumerate(lines) if line.strip().startswith("### 5.4")
    )
    end = next(
        index for index, line in enumerate(lines) if line.strip().startswith("### 5.5")
    )
    endpoints: dict[tuple[str, str], set[int]] = {}
    for line in lines[start:end]:
        match = _ROW.match(line)
        if match is None:
            continue
        method, path, rest = match.group(1), match.group(2), match.group(3)
        endpoints[(method, "/api/v1" + path)] = _spec_error_cell(rest)
    return endpoints


def _openapi() -> dict:
    return json.loads((CONTRACTS / "openapi.json").read_text(encoding="utf-8"))


def _normalized(
    items: set[tuple[str, str]] | dict[tuple[str, str], set[int]],
) -> set[tuple[str, str]]:
    return {(method.upper(), _normalize(path)) for method, path in items}


def _openapi_endpoints(contract: dict) -> set[tuple[str, str]]:
    return {
        (method.upper(), path)
        for path, operations in contract["paths"].items()
        for method in operations
    }


def _declared_status_codes(contract: dict) -> dict[tuple[str, str], set[int]]:
    return {
        (method.upper(), path): {
            int(code) for code in operation.get("responses", {}) if code.isdigit()
        }
        for path, operations in contract["paths"].items()
        for method, operation in operations.items()
    }


SPEC_5_4 = spec_5_4()


def test_spec_5_4_parses_its_endpoint_table():
    """Guard the parser: §5.4 lists 78 endpoints across its eight tables."""
    assert len(SPEC_5_4) == 78


def test_every_spec_endpoint_is_published_in_the_contract():
    expected = _normalized(SPEC_5_4)
    published = _normalized(_openapi_endpoints(_openapi()))

    assert expected - published == set()


def test_the_contract_publishes_nothing_but_health_beyond_the_spec():
    expected = _normalized(SPEC_5_4)
    published = _normalized(_openapi_endpoints(_openapi()))

    # `/api/v1/health` is not in §5.4 (see test_declared_error_branches.py).
    assert published - expected == {("GET", "/api/v1/health")}


def test_the_regression_trio_is_published():
    published = _normalized(_openapi_endpoints(_openapi()))

    assert {
        ("POST", "/api/v1/regression/runs"),
        ("GET", "/api/v1/regression/runs/{}"),
        ("GET", "/api/v1/regression/baselines"),
    } <= published


def test_error_branch_table_covers_every_spec_endpoint():
    # SPEC_ERROR_BRANCHES is keyed (path, method) — the mirror of §5.4.
    covered = {(method.upper(), path) for path, method in SPEC_ERROR_BRANCHES}

    assert _normalized(covered) == _normalized(SPEC_5_4)


def test_error_branch_table_never_understates_the_spec():
    table = {
        (method.upper(), _normalize(path)): set(codes)
        for (path, method), codes in SPEC_ERROR_BRANCHES.items()
    }

    for (method, path), codes in SPEC_5_4.items():
        assert codes <= table[(method, _normalize(path))], (method, path)


def test_the_contract_declares_every_spec_error_code():
    declared = {
        (method, _normalize(path)): codes
        for (method, path), codes in _declared_status_codes(_openapi()).items()
    }

    for (method, path), codes in SPEC_5_4.items():
        key = (method, _normalize(path))
        assert codes <= declared[key], key
        assert 200 in declared[key], key


def test_024_consumes_the_http_contract_divergence_subset():
    """The registry hands H-1…H-12 to 024; this ticket answers for that set."""
    assert http_contract_ids(load_registry()) == [f"H-{n}" for n in range(1, 13)]
