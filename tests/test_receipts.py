"""Regression tests for receipts.py -- the one part of this project that is
pure, deterministic logic (no LLM output), so it's the one part that can
actually be protected by an automated test suite rather than a hand-run eval.

Both `adaptive-audit-plan/scripts/receipts.py` and
`adaptive-audit-execute/scripts/receipts.py` are meant to be byte-identical
copies (each skill folder is self-contained per Claude Code Skill
convention, but the two skills share this exact script) -- every functional
test below runs against both copies via the `script` fixture, and
`test_scripts_stay_identical` guards against the two silently drifting apart
when only one copy gets edited.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = [
    REPO_ROOT / "adaptive-audit-plan" / "scripts" / "receipts.py",
    REPO_ROOT / "adaptive-audit-execute" / "scripts" / "receipts.py",
]


def test_scripts_stay_identical():
    a, b = SCRIPTS
    assert a.read_text(encoding="utf-8") == b.read_text(encoding="utf-8"), (
        "adaptive-audit-plan and adaptive-audit-execute ship separate copies "
        "of receipts.py by design, but the two copies must stay byte-"
        "identical -- a fix or behavior change landed in only one of them."
    )


def run(script, home, *args):
    env = dict(os.environ)
    env["ADAPTIVE_AUDIT_HOME"] = str(home)
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True, text=True, env=env, check=False,
    )


@pytest.fixture(params=SCRIPTS, ids=["plan-copy", "execute-copy"])
def script(request):
    return request.param


def write_json(tmp_path, name, data):
    p = tmp_path / name
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _write_plan_and_get_id(script, home, project, domains, tmp_path):
    plan = tmp_path / f"plan-{time.time_ns()}.json"
    plan.write_text(json.dumps({"domains": domains}), encoding="utf-8")
    r = run(script, home, "write", "--project-root", str(project), str(plan))
    assert r.returncode == 0, r.stderr
    return json.loads(Path(r.stdout.strip()).read_text(encoding="utf-8"))["id"]


def test_fingerprint_deterministic(script, tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "project"
    project.mkdir()
    r1 = run(script, home, "fingerprint", "--project-root", str(project))
    r2 = run(script, home, "fingerprint", "--project-root", str(project))
    assert r1.returncode == 0, r1.stderr
    assert r1.stdout.strip() == r2.stdout.strip()
    assert len(r1.stdout.strip()) == 16


def test_write_and_list_roundtrip(script, tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "project"
    project.mkdir()
    plan = write_json(tmp_path, "plan.json", {
        "domains": [
            {"domain_id": "security", "selected": True, "depth": "deep", "reasoning": "x"},
            {"domain_id": "performance", "selected": False, "reasoning": "no signal"},
        ]
    })
    r = run(script, home, "write", "--project-root", str(project), str(plan))
    assert r.returncode == 0, r.stderr
    assert Path(r.stdout.strip()).exists()

    r_list = run(script, home, "list", "--project-root", str(project))
    receipts = json.loads(r_list.stdout)
    assert len(receipts) == 1
    assert receipts[0]["domains"][0]["domain_id"] == "security"
    assert "id" in receipts[0] and "created_at" in receipts[0]


def test_write_result_requires_existing_plan(script, tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "project"
    project.mkdir()
    result = write_json(tmp_path, "result.json", {"domains": []})
    r = run(script, home, "write-result", "--project-root", str(project),
            "--plan-id", "doesnotexist", str(result))
    assert r.returncode != 0
    assert "no plan receipt" in r.stderr


def test_debt_uses_depth_executed_not_plan_depth(script, tmp_path):
    # Regression test for the staged-escalation bug fixed while building
    # depth_confidence-based escalation: a domain planned at "deep" but only
    # actually executed at "quick" (e.g. a provisional domain's Quick pass
    # found nothing and staged escalation stopped there) must be counted in
    # debt as verified at "quick", not silently credited with the plan's
    # "deep".
    home = tmp_path / "home"
    project = tmp_path / "project"
    project.mkdir()
    plan_id = _write_plan_and_get_id(script, home, project, [
        {"domain_id": "correctness", "selected": True, "depth": "deep", "reasoning": "x"},
    ], tmp_path)

    result = write_json(tmp_path, "result.json", {
        "domains": [
            {"domain_id": "correctness", "depth_executed": "quick",
             "confirmed_findings": 0, "plausible_findings": 0, "rejected_findings": 0},
        ]
    })
    r = run(script, home, "write-result", "--project-root", str(project),
            "--plan-id", plan_id, str(result))
    assert r.returncode == 0, r.stderr

    r_debt = run(script, home, "debt", "--project-root", str(project))
    debt = json.loads(r_debt.stdout)
    entry = next(e for e in debt["domains"] if e["domain_id"] == "correctness")
    assert entry["max_verified_depth_ever"] == "quick"


def test_debt_falls_back_to_plan_depth_for_old_result_records(script, tmp_path):
    # Backward compatibility: a result record written before `depth_executed`
    # existed has no such field, and must still resolve verified depth from
    # the plan's depth for that domain (pre-staged-escalation behavior).
    home = tmp_path / "home"
    project = tmp_path / "project"
    project.mkdir()
    plan_id = _write_plan_and_get_id(script, home, project, [
        {"domain_id": "reliability", "selected": True, "depth": "standard", "reasoning": "x"},
    ], tmp_path)

    result = write_json(tmp_path, "result.json", {
        "domains": [
            {"domain_id": "reliability",
             "confirmed_findings": 1, "plausible_findings": 0, "rejected_findings": 0},
        ]
    })
    r = run(script, home, "write-result", "--project-root", str(project),
            "--plan-id", plan_id, str(result))
    assert r.returncode == 0, r.stderr

    r_debt = run(script, home, "debt", "--project-root", str(project))
    debt = json.loads(r_debt.stdout)
    entry = next(e for e in debt["domains"] if e["domain_id"] == "reliability")
    assert entry["max_verified_depth_ever"] == "standard"


def test_export_csv_matches_debt(script, tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "project"
    project.mkdir()
    _write_plan_and_get_id(script, home, project, [
        {"domain_id": "security", "selected": True, "depth": "deep", "reasoning": "x"},
    ], tmp_path)

    r_csv = run(script, home, "export-csv", "--project-root", str(project))
    assert r_csv.returncode == 0, r_csv.stderr
    lines = r_csv.stdout.strip().splitlines()
    assert lines[0].startswith("domain_id,")
    assert any(line.startswith("security,") for line in lines[1:])


def test_diff_scoped_result_does_not_count_as_full_verification(script, tmp_path):
    # A result executed against a plan with "scope": "diff" (adaptive-audit-plan's
    # small-diff re-audit option) only looked at a slice of the project. It must
    # not advance times_executed/max_verified_depth_ever the way a full-scope
    # result does -- otherwise a string of cheap diff checks would look
    # identical to actually re-verifying the whole domain.
    home = tmp_path / "home"
    project = tmp_path / "project"
    project.mkdir()
    plan = write_json(tmp_path, "plan.json", {
        "scope": "diff",
        "diff_base_commit": "deadbeef",
        "diff_files": ["src/app.py"],
        "domains": [
            {"domain_id": "correctness", "selected": True, "depth": "standard", "reasoning": "x"},
        ],
    })
    r = run(script, home, "write", "--project-root", str(project), str(plan))
    assert r.returncode == 0, r.stderr
    plan_id = json.loads(Path(r.stdout.strip()).read_text(encoding="utf-8"))["id"]

    result = write_json(tmp_path, "result.json", {
        "domains": [
            {"domain_id": "correctness", "depth_executed": "standard",
             "confirmed_findings": 1, "plausible_findings": 0, "rejected_findings": 0},
        ]
    })
    r = run(script, home, "write-result", "--project-root", str(project),
            "--plan-id", plan_id, str(result))
    assert r.returncode == 0, r.stderr

    r_debt = run(script, home, "debt", "--project-root", str(project))
    debt = json.loads(r_debt.stdout)
    entry = next(e for e in debt["domains"] if e["domain_id"] == "correctness")
    assert entry["times_executed"] == 0
    assert entry["max_verified_depth_ever"] is None
    assert entry["diff_checks_since_last_full"] == 1


def test_full_scope_result_after_diff_resets_counter(script, tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "project"
    project.mkdir()

    diff_plan = write_json(tmp_path, "diff_plan.json", {
        "scope": "diff",
        "domains": [
            {"domain_id": "reliability", "selected": True, "depth": "standard", "reasoning": "x"},
        ],
    })
    r = run(script, home, "write", "--project-root", str(project), str(diff_plan))
    assert r.returncode == 0, r.stderr
    diff_plan_id = json.loads(Path(r.stdout.strip()).read_text(encoding="utf-8"))["id"]

    diff_result = write_json(tmp_path, "diff_result.json", {
        "domains": [{"domain_id": "reliability", "depth_executed": "standard",
                     "confirmed_findings": 0, "plausible_findings": 0, "rejected_findings": 0}]
    })
    r = run(script, home, "write-result", "--project-root", str(project),
            "--plan-id", diff_plan_id, str(diff_result))
    assert r.returncode == 0, r.stderr

    full_plan_id = _write_plan_and_get_id(script, home, project, [
        {"domain_id": "reliability", "selected": True, "depth": "standard", "reasoning": "y"},
    ], tmp_path)
    full_result = write_json(tmp_path, "full_result.json", {
        "domains": [{"domain_id": "reliability", "depth_executed": "standard",
                     "confirmed_findings": 1, "plausible_findings": 0, "rejected_findings": 0}]
    })
    r = run(script, home, "write-result", "--project-root", str(project),
            "--plan-id", full_plan_id, str(full_result))
    assert r.returncode == 0, r.stderr

    r_debt = run(script, home, "debt", "--project-root", str(project))
    debt = json.loads(r_debt.stdout)
    entry = next(e for e in debt["domains"] if e["domain_id"] == "reliability")
    assert entry["times_executed"] == 1
    assert entry["max_verified_depth_ever"] == "standard"
    assert entry["diff_checks_since_last_full"] == 0


def test_report_flags_unaudited_selected_domain(script, tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "project"
    project.mkdir()
    _write_plan_and_get_id(script, home, project, [
        {"domain_id": "dependency-health", "selected": True, "depth": "standard", "reasoning": "x"},
    ], tmp_path)

    r_report = run(script, home, "report", "--project-root", str(project))
    assert r_report.returncode == 0, r_report.stderr
    assert "PLANNED-ONLY" in r_report.stdout
    assert "dependency-health" in r_report.stdout
