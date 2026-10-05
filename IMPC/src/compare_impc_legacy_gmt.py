#!/usr/bin/env python3
"""Compare a regenerated IMPC GMT with a validation-only legacy GMT."""
from __future__ import annotations
import argparse, json
from pathlib import Path

def read(path: Path):
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) >= 3: result[fields[0]] = set(fields[2:])
    return result

def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--candidate", type=Path, required=True); p.add_argument("--legacy", type=Path, required=True); p.add_argument("--out", type=Path, required=True); args = p.parse_args(); a, b = read(args.candidate), read(args.legacy)
    candidate = {(t, g) for t, genes in a.items() for g in genes}; legacy = {(t, g) for t, genes in b.items() for g in genes}; shared = set(a) & set(b)
    payload = {"candidate_terms": len(a), "legacy_terms": len(b), "candidate_memberships": len(candidate), "legacy_memberships": len(legacy), "candidate_unique_genes": len({g for _, g in candidate}), "legacy_unique_genes": len({g for _, g in legacy}), "shared_terms": len(shared), "legacy_only_terms": len(set(b)-set(a)), "candidate_only_terms": len(set(a)-set(b)), "membership_intersection": len(candidate & legacy), "membership_recall": len(candidate & legacy)/len(legacy) if legacy else 1.0, "membership_precision": len(candidate & legacy)/len(candidate) if candidate else 1.0, "membership_jaccard": len(candidate & legacy)/len(candidate | legacy) if candidate | legacy else 1.0, "mean_per_set_jaccard": sum(len(a[t]&b[t])/len(a[t]|b[t]) for t in shared)/len(shared) if shared else 0.0, "exact_set_matches": sum(a[t] == b[t] for t in shared)}
    args.out.parent.mkdir(parents=True, exist_ok=True); args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n"); print(json.dumps(payload, sort_keys=True)); return 0
if __name__ == "__main__": raise SystemExit(main())
