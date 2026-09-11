#!/usr/bin/env python3
"""Bumps this repo's own version bookkeeping for a release.

Used by .github/workflows/release.yml, in-process (no shell=True, no
untrusted-string interpolation) -- reads the commit log via `git log` with
an explicit argv list (never a shell-interpolated string built from PR
titles or other untrusted GitHub Actions context values, which is exactly
the class of GitHub Actions script-injection vulnerability this avoids).

Given a target version and the previous release ref (a git tag, or empty
string for "no prior release"), this:
  1. Writes VERSION.
  2. Updates .claude-plugin/marketplace.json's "adaptive-audit" plugin
     entry's version field to match (kept in sync; see tests/test_versioning.py).
  3. Inserts a new "## [<version>] - <date>" section into CHANGELOG.md,
     directly under the existing "## [Unreleased]" section (which is reset
     to empty), listing commit subjects since the previous ref as bullets.
  4. Prints that new section's body to stdout, so the caller can use it
     directly as release notes (e.g. `python3 bump_version.py 1.2.0 v1.1.0
     > notes.md`) without a second pass over the same data.

Usage: bump_version.py <new_version> [<prev_ref>]
"""
import json
import subprocess
import sys
from datetime import date, timezone
from datetime import datetime as dt
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def commit_subjects_since(prev_ref: str) -> list[str]:
    rev_range = f"{prev_ref}..HEAD" if prev_ref else "HEAD"
    out = subprocess.run(
        ["git", "log", rev_range, "--no-merges", "--pretty=format:%s"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return [line for line in out.splitlines() if line.strip()]


def render_section(version: str, subjects: list[str]) -> str:
    today = dt.now(timezone.utc).date().isoformat()
    lines = [f"## [{version}] - {today}", ""]
    if subjects:
        lines += [f"- {s}" for s in subjects]
    else:
        lines.append("- (no commit subjects found since the previous release)")
    lines.append("")
    return "\n".join(lines)


def update_version_file(version: str) -> None:
    (REPO_ROOT / "VERSION").write_text(version + "\n", encoding="utf-8")


def update_marketplace_json(version: str) -> None:
    path = REPO_ROOT / ".claude-plugin" / "marketplace.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for plugin in data.get("plugins", []):
        if plugin.get("name") == "adaptive-audit":
            plugin["version"] = version
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def update_changelog(section: str) -> None:
    path = REPO_ROOT / "CHANGELOG.md"
    text = path.read_text(encoding="utf-8")
    marker = "## [Unreleased]"
    idx = text.find(marker)
    if idx == -1:
        # No Unreleased section found -- fall back to inserting right after
        # the first line (the "# Changelog" title), so a release still
        # happens rather than silently doing nothing.
        lines = text.splitlines(keepends=True)
        new_text = "".join(lines[:1]) + "\n" + section + "\n" + "".join(lines[1:])
        path.write_text(new_text, encoding="utf-8")
        return

    # Find the end of the "## [Unreleased]" section's own body (up to the
    # next "## [" heading, or end of file) and replace it with a reset
    # empty Unreleased section followed by the new version's section.
    rest = text[idx + len(marker):]
    next_heading = rest.find("\n## [")
    body_end = idx + len(marker) + (next_heading if next_heading != -1 else len(rest))
    new_text = (
        text[:idx]
        + "## [Unreleased]\n\nNothing yet.\n\n"
        + section
        + "\n"
        + text[body_end:].lstrip("\n")
    )
    path.write_text(new_text, encoding="utf-8")


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: bump_version.py <new_version> [<prev_ref>]", file=sys.stderr)
        sys.exit(2)
    version = sys.argv[1]
    prev_ref = sys.argv[2] if len(sys.argv) > 2 else ""

    subjects = commit_subjects_since(prev_ref)
    section = render_section(version, subjects)

    update_version_file(version)
    update_marketplace_json(version)
    update_changelog(section)

    print(section)


if __name__ == "__main__":
    main()
