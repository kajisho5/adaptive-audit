#!/usr/bin/env python3
"""Local, per-project audit history for the adaptive-audit skill.

Stores one JSON record per completed Audit Plan run ("receipt", named after
ProductionReceipt in kajisho5/AI-video-production-OS's docs/SPEC.md -- this is
the same idea: a content-addressed record of one completed run, kept outside
the thing it was run against). Receipts live under
~/.adaptive-audit/projects/<fingerprint>/receipts/, keyed by a hash of the
project's absolute path, never inside the audited project itself -- running
this skill must never change the target repo's own git status.

Stdlib only, matching this ecosystem's other skills (see ffmpeg-skill).

Subcommands:
  fingerprint --project-root PATH        print the project's fingerprint
  write       --project-root PATH FILE   store FILE (a plan record) as a new receipt, print its path
  list        --project-root PATH        print all receipts for this project, oldest first
  debt        --project-root PATH        print per-domain audit-debt stats computed from history
"""
import argparse
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


def receipts_dir(project_root: str) -> Path:
    d = STORE_ROOT / "projects" / project_fingerprint(project_root) / "receipts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_receipts(project_root: str):
    receipts = []
    for f in sorted(receipts_dir(project_root).glob("*.json")):
        with open(f, encoding="utf-8") as fh:
            receipts.append(json.load(fh))
    receipts.sort(key=lambda r: r.get("created_at", ""))
    return receipts


def cmd_fingerprint(args):
    print(project_fingerprint(args.project_root))


def cmd_list(args):
    print(json.dumps(load_receipts(args.project_root), ensure_ascii=False, indent=2))


def cmd_write(args):
    with open(args.plan_record_file, encoding="utf-8") as fh:
        receipt = json.load(fh)

    receipt.pop("id", None)
    receipt.pop("created_at", None)
    # Identity excludes timestamps, same reasoning as qc-skill's identity scheme
    # (see docs/SPEC.md, Artifact / QCReport): two runs with identical decisions
    # should be recognizable as the same content even if run at different times.
    content_hash = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
    receipt["id"] = content_hash
    receipt["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    out_path = receipts_dir(args.project_root) / f"{content_hash}.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, ensure_ascii=False, indent=2)
    print(str(out_path))


def cmd_debt(args):
    receipts = load_receipts(args.project_root)
    debt = {}

    for idx, r in enumerate(receipts):
        for dm in r.get("domains", []):
            did = dm["domain_id"]
            entry = debt.setdefault(did, {
                "domain_id": did,
                "times_appeared": 0,
                "times_selected": 0,
                "times_excluded": 0,
                "max_depth_ever": None,
                "last_deep_run_index": None,
            })
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

    domains = []
    for did, entry in debt.items():
        if entry["last_deep_run_index"] is None:
            runs_since_last_deep = entry["times_appeared"]
        else:
            runs_since_last_deep = sum(
                1
                for idx, r in enumerate(receipts)
                if idx > entry["last_deep_run_index"]
                and any(dm["domain_id"] == did for dm in r.get("domains", []))
            )
        entry["runs_since_last_deep"] = runs_since_last_deep
        entry.pop("last_deep_run_index")
        domains.append(entry)

    domains.sort(key=lambda e: (-e["runs_since_last_deep"], -e["times_excluded"]))
    print(json.dumps({"total_runs": len(receipts), "domains": domains}, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("fingerprint")
    p.add_argument("--project-root", required=True)
    p.set_defaults(func=cmd_fingerprint)

    p = sub.add_parser("list")
    p.add_argument("--project-root", required=True)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("write")
    p.add_argument("--project-root", required=True)
    p.add_argument("plan_record_file")
    p.set_defaults(func=cmd_write)

    p = sub.add_parser("debt")
    p.add_argument("--project-root", required=True)
    p.set_defaults(func=cmd_debt)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
