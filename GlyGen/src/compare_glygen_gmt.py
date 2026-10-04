#!/usr/bin/env python3
"""Report required shared-term and global GlyGen GMT reconstruction metrics."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def _read(path: Path) -> dict[str, set[str]]:
    sets: dict[str, set[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"): continue
        fields = line.split("\t")
        if len(fields) >= 3: sets[fields[0]] = {gene for gene in fields[2:] if gene}
    return sets


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("target"); parser.add_argument("candidate"); parser.add_argument("--out", required=True)
    args = parser.parse_args(); target, candidate = _read(Path(args.target)), _read(Path(args.candidate)); shared = set(target) & set(candidate)
    shared_target = {(term, gene) for term in shared for gene in target[term]}; shared_candidate = {(term, gene) for term in shared for gene in candidate[term]}; global_target = {(term, gene) for term, genes in target.items() for gene in genes}; global_candidate = {(term, gene) for term, genes in candidate.items() for gene in genes}
    def metrics(reference: set[tuple[str, str]], observed: set[tuple[str, str]]) -> dict[str, float]:
        overlap = len(reference & observed); return {"recall": _ratio(overlap, len(reference)), "precision": _ratio(overlap, len(observed)), "jaccard": _ratio(overlap, len(reference | observed))}
    report = {"target_sets": len(target), "candidate_sets": len(candidate), "shared_terms": len(shared), "target_only_terms": len(set(target) - set(candidate)), "candidate_only_terms": len(set(candidate) - set(target)), "exact_set_matches": sum(target[term] == candidate[term] for term in shared), "target_memberships": len(global_target), "candidate_memberships": len(global_candidate), "target_unique_genes": len({gene for genes in target.values() for gene in genes}), "candidate_unique_genes": len({gene for genes in candidate.values() for gene in genes}), "shared_term_metrics": metrics(shared_target, shared_candidate), "global_term_gene_metrics": metrics(global_target, global_candidate), "candidate_set_size_distribution": dict(sorted(Counter(map(len, candidate.values())).items()))}
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(json.dumps(report, indent=2, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
