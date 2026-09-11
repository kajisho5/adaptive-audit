"""Keeps the project's version bookkeeping internally consistent.

VERSION (read by .github/workflows/release.yml to tag/release main) and
.claude-plugin/marketplace.json's plugin entry version (read by Claude Code
when someone installs this repo as a plugin) are two separate files that
have to be bumped together by hand -- nothing enforces that at write time,
so this test catches the two silently drifting apart, the same role
test_scripts_stay_identical plays for the two receipts.py copies.
"""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_marketplace_version_matches_version_file():
    version = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    marketplace = json.loads(
        (REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )
    plugin_versions = [p.get("version") for p in marketplace["plugins"] if p["name"] == "adaptive-audit"]
    assert plugin_versions, "no 'adaptive-audit' plugin entry found in marketplace.json"
    for plugin_version in plugin_versions:
        assert plugin_version == version, (
            f"marketplace.json plugin version ({plugin_version!r}) doesn't match "
            f"VERSION ({version!r}) -- bump both together"
        )


def test_marketplace_json_is_valid_and_points_at_both_skills():
    marketplace = json.loads(
        (REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )
    assert marketplace["name"]
    assert marketplace["owner"]["name"]
    plugin = next(p for p in marketplace["plugins"] if p["name"] == "adaptive-audit")
    skill_paths = set(plugin["skills"])
    assert skill_paths == {"./adaptive-audit-plan", "./adaptive-audit-execute"}
    for rel_path in skill_paths:
        skill_md = REPO_ROOT / rel_path.lstrip("./") / "SKILL.md"
        assert skill_md.is_file(), f"{skill_md} does not exist"
