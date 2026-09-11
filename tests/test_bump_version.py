"""Regression tests for scripts/bump_version.py, the core logic behind
.github/workflows/release.yml's single-job release automation.

Runs against an isolated throwaway git fixture (tmp_path), never the real
repo -- these tests build a small fake repo with its own VERSION,
CHANGELOG.md, and .claude-plugin/marketplace.json, commit to it, and invoke
the real script as a subprocess exactly as the workflow does.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "bump_version.py"

CHANGELOG_TEMPLATE = """# Changelog

Intro text.

## [Unreleased]

Nothing yet.

## [0.1.0] - first tracked release

- initial stuff
"""

MARKETPLACE_TEMPLATE = {
    "name": "adaptive-audit",
    "owner": {"name": "kajisho5"},
    "plugins": [
        {
            "name": "adaptive-audit",
            "source": "./",
            "version": "0.1.0",
            "skills": ["./adaptive-audit-plan", "./adaptive-audit-execute"],
        }
    ],
}


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def make_fixture(tmp_path):
    fixture = tmp_path / "fixture"
    (fixture / "scripts").mkdir(parents=True)
    (fixture / ".claude-plugin").mkdir()
    (fixture / "scripts" / "bump_version.py").write_text(
        SCRIPT.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (fixture / "VERSION").write_text("0.1.0\n", encoding="utf-8")
    (fixture / "CHANGELOG.md").write_text(CHANGELOG_TEMPLATE, encoding="utf-8")
    (fixture / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps(MARKETPLACE_TEMPLATE, indent=2), encoding="utf-8"
    )

    _git(fixture, "init", "-q")
    _git(fixture, "config", "user.email", "test@example.com")
    _git(fixture, "config", "user.name", "Test")
    _git(fixture, "add", "-A")
    _git(fixture, "commit", "-q", "-m", "Initial commit (v0.1.0 baseline)")
    _git(fixture, "tag", "v0.1.0")
    return fixture


def run_bump(fixture, version, prev_ref=""):
    args = [sys.executable, "scripts/bump_version.py", version]
    if prev_ref:
        args.append(prev_ref)
    return subprocess.run(args, cwd=fixture, capture_output=True, text=True)


def test_bump_updates_version_file(tmp_path):
    fixture = make_fixture(tmp_path)
    (fixture / "feature.txt").write_text("x", encoding="utf-8")
    _git(fixture, "add", "-A")
    _git(fixture, "commit", "-q", "-m", "Add a feature")

    result = run_bump(fixture, "0.2.0", "v0.1.0")
    assert result.returncode == 0, result.stderr
    assert (fixture / "VERSION").read_text(encoding="utf-8").strip() == "0.2.0"


def test_bump_updates_marketplace_json_version(tmp_path):
    fixture = make_fixture(tmp_path)
    result = run_bump(fixture, "0.2.0", "v0.1.0")
    assert result.returncode == 0, result.stderr
    data = json.loads((fixture / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    plugin = next(p for p in data["plugins"] if p["name"] == "adaptive-audit")
    assert plugin["version"] == "0.2.0"


def test_bump_inserts_new_changelog_section_with_commit_subjects(tmp_path):
    fixture = make_fixture(tmp_path)
    (fixture / "a.txt").write_text("x", encoding="utf-8")
    _git(fixture, "add", "-A")
    _git(fixture, "commit", "-q", "-m", "Add feature A")
    (fixture / "b.txt").write_text("x", encoding="utf-8")
    _git(fixture, "add", "-A")
    _git(fixture, "commit", "-q", "-m", "Fix bug B")

    result = run_bump(fixture, "0.2.0", "v0.1.0")
    assert result.returncode == 0, result.stderr
    changelog = (fixture / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "## [Unreleased]" in changelog
    assert "## [0.2.0]" in changelog
    assert "- Add feature A" in changelog
    assert "- Fix bug B" in changelog
    # Unreleased must be reset to empty, not carry the new version's notes.
    unreleased_idx = changelog.index("## [Unreleased]")
    next_heading_idx = changelog.index("## [0.2.0]")
    unreleased_body = changelog[unreleased_idx:next_heading_idx]
    assert "Nothing yet." in unreleased_body
    assert "Add feature A" not in unreleased_body
    # A blank line must separate the new section from what follows it.
    assert "\n\n## [0.1.0]" in changelog

    # The script also prints the new section to stdout for release notes.
    assert "Add feature A" in result.stdout
    assert "Fix bug B" in result.stdout


def test_bump_with_no_prior_tag_uses_full_history(tmp_path):
    fixture = make_fixture(tmp_path)
    result = run_bump(fixture, "0.1.0", "")
    assert result.returncode == 0, result.stderr
    assert "Initial commit" in result.stdout


def test_commit_subjects_are_not_shell_evaluated(tmp_path):
    # A commit subject containing shell metacharacters must appear verbatim
    # in the output, never be executed -- this is the core defense against
    # the GitHub Actions script-injection class the workflow avoids by
    # reading git log as subprocess data, never interpolating it into a
    # shell string via `${{ }}`.
    fixture = make_fixture(tmp_path)
    dangerous = 'Fix `$(touch pwned)` and "quotes" and $VAR'
    (fixture / "c.txt").write_text("x", encoding="utf-8")
    _git(fixture, "add", "-A")
    _git(fixture, "commit", "-q", "-m", dangerous)

    result = run_bump(fixture, "0.2.0", "v0.1.0")
    assert result.returncode == 0, result.stderr
    assert not (fixture / "pwned").exists()
    changelog = (fixture / "CHANGELOG.md").read_text(encoding="utf-8")
    assert dangerous in changelog
