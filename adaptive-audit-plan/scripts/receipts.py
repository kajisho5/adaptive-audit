#!/usr/bin/env python3
"""Local, per-project audit history for the adaptive-audit skills.

Stores two kinds of JSON record, both named after ProductionReceipt in
kajisho5/AI-video-production-OS's docs/SPEC.md (a content-addressed record of
one completed run, kept outside the thing it was run against):

- a **plan receipt** (written by adaptive-audit-plan): what was decided --
  which domains were selected/excluded, at what depth, and why.
- an **execution result** (written by adaptive-audit-execute): what actually
  got audited and confirmed, referencing the plan receipt it executed via
  `plan_id` (the SPEC.md `derived_from` pattern) -- a plan being selected is
  not the same claim as a domain having actually been looked at, so debt is
  computed from execution results, not from plan intent alone.

Both live under ~/.adaptive-audit/projects/<fingerprint>/{receipts,results}/,
keyed by a hash of the project's absolute path, never inside the audited
project itself -- running these skills must never change the target repo's
own git status.

Stdlib only, matching this ecosystem's other skills (see ffmpeg-skill).

Subcommands:
  fingerprint  --project-root PATH               print the project's fingerprint
  write        --project-root PATH FILE          store FILE (a plan record) as a new receipt, print its path and id
  write-result --project-root PATH --plan-id ID FILE
                                                  store FILE (an execution result) linked to plan receipt ID, print its path
  list         --project-root PATH               print all plan receipts, oldest first
  list-results --project-root PATH               print all execution results, oldest first
  debt         --project-root PATH               print per-domain audit-debt stats computed from history, as JSON
  report       --project-root PATH               same stats as `debt`, as a human-readable table + attention list
  export-csv   --project-root PATH               same stats as `debt`, as CSV on stdout -- opens directly in
                                                  Excel/Sheets. For a PDF instead, ask Claude to render one from
                                                  this CSV or from `report`'s output when you actually need a
                                                  shareable document -- deliberately not a feature of this script,
                                                  which stays dependency-free (no PDF library, no XLSX writer).
"""
import argparse
import csv
import hashlib
import json
import os
import sys
import time
from pathlib import Path

STORE_ROOT = Path(os.environ.get("ADAPTIVE_AUDIT_HOME", str(Path.home() / ".adaptive-audit")))

DEPTH_RANK = {"quick": 1, "standard": 2, "deep": 3}


def project_fingerprint(project_root: str) -> str:
    real = str(Path(project_root).resolve())
    return hashlib.sha256(real.encode("utf-8")).hexdigest()[:16]


def _dir(project_root: str, kind: str) -> Path:
    d = STORE_ROOT / "projects" / project_fingerprint(project_root) / kind
    d.mkdir(parents=True, exist_ok=True)
    return d


def receipts_dir(project_root: str) -> Path:
    return _dir(project_root, "receipts")


def results_dir(project_root: str) -> Path:
    return _dir(project_root, "results")


def _load_all(d: Path):
    records = []
    for f in sorted(d.glob("*.json")):
        with open(f, encoding="utf-8") as fh:
            records.append(json.load(fh))
    records.sort(key=lambda r: r.get("created_at", ""))
    return records


def load_receipts(project_root: str):
    return _load_all(receipts_dir(project_root))


def load_results(project_root: str):
    return _load_all(results_dir(project_root))


def _content_hash(body: dict) -> str:
    # Identity excludes timestamps, same reasoning as qc-skill's identity scheme
    # (see docs/SPEC.md, Artifact / QCReport): two runs with identical decisions
    # should be recognizable as the same content even if run at different times.
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]


def cmd_fingerprint(args):
    print(project_fingerprint(args.project_root))


def cmd_list(args):
    print(json.dumps(load_receipts(args.project_root), ensure_ascii=False, indent=2))


def cmd_list_results(args):
    print(json.dumps(load_results(args.project_root), ensure_ascii=False, indent=2))


def cmd_write(args):
    with open(args.plan_record_file, encoding="utf-8") as fh:
        receipt = json.load(fh)

    receipt.pop("id", None)
    receipt.pop("created_at", None)
    content_hash = _content_hash(receipt)
    receipt["id"] = content_hash
    receipt["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    out_path = receipts_dir(args.project_root) / f"{content_hash}.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, ensure_ascii=False, indent=2)
    print(str(out_path))


def cmd_write_result(args):
    with open(args.result_file, encoding="utf-8") as fh:
        result = json.load(fh)

    plan_path = receipts_dir(args.project_root) / f"{args.plan_id}.json"
    if not plan_path.exists():
        print(f"error: no plan receipt {args.plan_id} for this project", file=sys.stderr)
        sys.exit(1)

    result.pop("id", None)
    result.pop("created_at", None)
    result["plan_id"] = args.plan_id
    content_hash = _content_hash(result)
    result["id"] = content_hash
    result["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    out_path = results_dir(args.project_root) / f"{content_hash}.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    print(str(out_path))


def cmd_debt(args):
    computed = _compute_debt(args.project_root)
    print(json.dumps(computed, ensure_ascii=False, indent=2))


def cmd_report(args):
    computed = _compute_debt(args.project_root)
    print(_render_report(args.project_root, computed))


def cmd_export_csv(args):
    computed = _compute_debt(args.project_root)
    fieldnames = [
        "domain_id", "status", "times_appeared", "times_selected", "times_excluded",
        "max_depth_ever", "runs_since_last_deep", "times_executed",
        "max_verified_depth_ever", "runs_since_last_verified_deep",
    ]
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for e in computed["domains"]:
        row = dict(e)
        row["status"] = _debt_status(e)
        writer.writerow(row)


def _compute_debt(project_root: str) -> dict:
    receipts = load_receipts(project_root)
    results = load_results(project_root)
    receipts_by_id = {r["id"]: r for r in receipts}

    debt = {}

    # Plan-level tallies (intent: what was selected/excluded, and at what
    # depth it was *planned* to be looked at). Unchanged from iteration 2 --
    # this reflects what each run *decided*, independent of whether a
    # follow-up execution ever happened.
    for idx, r in enumerate(receipts):
        for dm in r.get("domains", []):
            did = dm["domain_id"]
            entry = debt.setdefault(did, _new_entry(did))
            entry["times_appeared"] += 1
            if dm.get("selected"):
                entry["times_selected"] += 1
                depth = dm.get("depth")
                if depth and (
                    entry["max_depth_ever"] is None
                    or DEPTH_RANK[depth] > DEPTH_RANK[entry["max_depth_ever"]]
                ):
                    entry["max_depth_ever"] = depth
                if depth == "deep":
                    entry["last_deep_run_index"] = idx
            else:
                entry["times_excluded"] += 1

    for did, entry in debt.items():
        entry["runs_since_last_deep"] = _runs_since(receipts, did, entry.pop("last_deep_run_index"))

    # Execution-level tallies (verified: a domain only counts here once an
    # execution result actually references it). Depth is resolved by looking
    # up the plan the result claims to have executed.
    last_verified_deep_index = {}
    for idx, res in enumerate(results):
        plan = receipts_by_id.get(res.get("plan_id"))
        plan_depths = {
            dm["domain_id"]: dm.get("depth")
            for dm in (plan.get("domains", []) if plan else [])
            if dm.get("selected")
        }
        for dm in res.get("domains", []):
            did = dm["domain_id"]
            entry = debt.setdefault(did, _new_entry(did))
            entry["times_executed"] += 1
            depth = plan_depths.get(did)
            if depth and (
                entry["max_verified_depth_ever"] is None
                or DEPTH_RANK[depth] > DEPTH_RANK[entry["max_verified_depth_ever"]]
            ):
                entry["max_verified_depth_ever"] = depth
            if depth == "deep":
                last_verified_deep_index[did] = idx

    for did, entry in debt.items():
        entry["runs_since_last_verified_deep"] = _runs_since(
            results, did, last_verified_deep_index.get(did), key="domains"
        )

    domains = list(debt.values())
    domains.sort(key=lambda e: (-e["runs_since_last_deep"], -e["times_excluded"]))
    return {"total_runs": len(receipts), "total_executions": len(results), "domains": domains}


def _debt_status(entry: dict) -> str:
    # A small, fixed rubric -- not a precise measurement, just enough to sort
    # a human's attention at a glance. Verified (executed) state always wins
    # over planned-only state: a domain nobody has ever actually looked at is
    # worse than one that's merely due for another look.
    if entry["times_executed"] == 0:
        if entry["times_selected"] == 0:
            return "UNAUDITED" if entry["times_appeared"] > 0 else "UNKNOWN"
        return "PLANNED-ONLY"  # selected in a plan, never actually executed/verified
    if entry["max_verified_depth_ever"] != "deep" and entry["runs_since_last_deep"] >= 3:
        return "STALE"
    if entry["runs_since_last_deep"] >= 2:
        return "AGING"
    return "FRESH"


_STATUS_ORDER = {"UNAUDITED": 0, "PLANNED-ONLY": 1, "STALE": 2, "AGING": 3, "FRESH": 4, "UNKNOWN": 5}


def _render_report(project_root: str, computed: dict) -> str:
    lines = []
    lines.append(f"Audit Debt Report — {project_root}")
    lines.append(f"fingerprint: {project_fingerprint(project_root)}")
    lines.append(f"plan runs: {computed['total_runs']}   executions: {computed['total_executions']}")
    lines.append("")

    if not computed["domains"]:
        lines.append("No history recorded yet for this project.")
        return "\n".join(lines)

    domains = sorted(
        computed["domains"],
        key=lambda e: (_STATUS_ORDER[_debt_status(e)], -e["runs_since_last_deep"]),
    )

    header = f"{'DOMAIN':<24} {'STATUS':<13} {'VERIFIED DEPTH':<15} {'SINCE DEEP':<11} {'SEL/EXCL':<9}"
    lines.append(header)
    lines.append("-" * len(header))
    for e in domains:
        status = _debt_status(e)
        verified = e["max_verified_depth_ever"] or "-"
        since = str(e["runs_since_last_deep"])
        sel_excl = f"{e['times_selected']}/{e['times_excluded']}"
        lines.append(f"{e['domain_id']:<24} {status:<13} {verified:<15} {since:<11} {sel_excl:<9}")

    lines.append("")
    stale_or_worse = [e for e in domains if _debt_status(e) in ("UNAUDITED", "PLANNED-ONLY", "STALE")]
    if stale_or_worse:
        lines.append("Needs attention:")
        for e in stale_or_worse:
            status = _debt_status(e)
            if status == "UNAUDITED":
                why = "planned and excluded every time it's come up -- never selected"
            elif status == "PLANNED-ONLY":
                why = "selected in a plan but no execution result was ever recorded for it"
            else:
                why = f"verified {e['runs_since_last_deep']} runs ago or more, not since at Deep"
            lines.append(f"  - {e['domain_id']}: {why}")
    else:
        lines.append("No domain is currently flagged as stale or unaudited.")

    lines.append("")
    lines.append(
        "Note: UNAUDITED/PLANNED-ONLY here is a numeric proxy, not a verdict -- a"
        " domain can be legitimately never-selected because it's structurally"
        " inapplicable (e.g. dependency-health with zero dependencies), not because"
        " it's neglected. Check the plan receipts' own `reasoning` field for that"
        " domain before treating a row here as an actual gap."
    )

    return "\n".join(lines)


def _new_entry(did):
    return {
        "domain_id": did,
        "times_appeared": 0,
        "times_selected": 0,
        "times_excluded": 0,
        "max_depth_ever": None,
        "last_deep_run_index": None,
        "times_executed": 0,
        "max_verified_depth_ever": None,
    }


def _runs_since(records, domain_id, last_index, key="domains"):
    if last_index is None:
        return sum(1 for r in records if any(dm["domain_id"] == domain_id for dm in r.get(key, [])))
    return sum(
        1
        for idx, r in enumerate(records)
        if idx > last_index and any(dm["domain_id"] == domain_id for dm in r.get(key, []))
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("fingerprint")
    p.add_argument("--project-root", required=True)
    p.set_defaults(func=cmd_fingerprint)

    p = sub.add_parser("list")
    p.add_argument("--project-root", required=True)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("list-results")
    p.add_argument("--project-root", required=True)
    p.set_defaults(func=cmd_list_results)

    p = sub.add_parser("write")
    p.add_argument("--project-root", required=True)
    p.add_argument("plan_record_file")
    p.set_defaults(func=cmd_write)

    p = sub.add_parser("write-result")
    p.add_argument("--project-root", required=True)
    p.add_argument("--plan-id", required=True)
    p.add_argument("result_file")
    p.set_defaults(func=cmd_write_result)

    p = sub.add_parser("debt")
    p.add_argument("--project-root", required=True)
    p.set_defaults(func=cmd_debt)

    p = sub.add_parser("report")
    p.add_argument("--project-root", required=True)
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("export-csv")
    p.add_argument("--project-root", required=True)
    p.set_defaults(func=cmd_export_csv)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
