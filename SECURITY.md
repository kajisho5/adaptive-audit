# Security Policy

## Reporting a vulnerability

Please report security vulnerabilities in this repository privately, using
GitHub's private vulnerability reporting flow rather than a public issue:

**[Security] → [Advisories] → [Report a vulnerability]**
(or go directly to
https://github.com/kajisho5/adaptive-audit/security/advisories/new)

This opens a private draft security advisory visible only to the repo
maintainer and you, so a real finding isn't disclosed publicly before
there's a fix.

## Scope

This repo ships two Claude Code Skills (`adaptive-audit-plan`,
`adaptive-audit-execute`) and the local audit-history tooling they use
(`scripts/receipts.py`). In scope: anything in this behavior or tooling
that could cause it to do something unsafe to a project it's asked to
audit, leak data it shouldn't, or otherwise behave in a way a user
wouldn't reasonably expect from a read-only auditing tool.

Out of scope: `evals/fixtures/**` — those projects are deliberately
vulnerable, seeded on purpose as test corpora for the audit skills
themselves. Findings in them aren't vulnerabilities in this repo.
