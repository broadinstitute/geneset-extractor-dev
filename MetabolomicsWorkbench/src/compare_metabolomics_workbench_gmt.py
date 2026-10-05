#!/usr/bin/env python3
"""Compare generated and legacy Metabolomics Workbench GMTs without using either as input."""
from __future__ import annotations
import argparse, json, statistics
from pathlib import Path

def read_gmt(path: Path) -> dict[str, set[str]]:
    rows: dict[str, set[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) >= 3: rows[fields[0]] = {gene for gene in fields[2:] if gene}
    return rows

def normalized_map(rows: dict[str, set[str]]) -> dict[str, tuple[str, set[str]]]:
    result = {}
    for term, genes in rows.items():
        key = term.casefold()
        if key in result: raise ValueError(f"ambiguous case-normalized term: {term}")
        result[key] = (term, genes)
    return result

def metrics(legacy: dict[str, set[str]], generated: dict[str, set[str]]) -> tuple[dict[str, object], list[dict[str, object]]]:
    shared = sorted(set(legacy) & set(generated)); legacy_pairs = {(t, g) for t, gs in legacy.items() for g in gs}; generated_pairs = {(t, g) for t, gs in generated.items() for g in gs}; intersect = legacy_pairs & generated_pairs
    details = []
    for term in shared:
        left, right = legacy[term], generated[term]; common = left & right
        details.append({"metabolite": term, "legacy_size": len(left), "generated_size": len(right), "intersection": len(common), "legacy_only_genes": sorted(left-right), "generated_only_genes": sorted(right-left), "jaccard": len(common)/len(left|right)})
    jaccards = [row["jaccard"] for row in details]
    return {"legacy_sets": len(legacy), "generated_sets": len(generated), "common_terms": len(shared), "legacy_only_terms": sorted(set(legacy)-set(generated)), "generated_only_terms": sorted(set(generated)-set(legacy)), "exact_sets": sum(legacy[t] == generated[t] for t in shared), "legacy_memberships": len(legacy_pairs), "generated_memberships": len(generated_pairs), "membership_intersection": len(intersect), "legacy_recall": len(intersect)/len(legacy_pairs) if legacy_pairs else 1.0, "generated_precision": len(intersect)/len(generated_pairs) if generated_pairs else 1.0, "membership_jaccard": len(intersect)/len(legacy_pairs|generated_pairs) if legacy_pairs|generated_pairs else 1.0, "legacy_unique_genes": len({g for _, g in legacy_pairs}), "generated_unique_genes": len({g for _, g in generated_pairs}), "gene_intersection": len({g for _, g in legacy_pairs}&{g for _, g in generated_pairs}), "mean_per_set_jaccard": statistics.mean(jaccards) if jaccards else 0.0, "median_per_set_jaccard": statistics.median(jaccards) if jaccards else 0.0, "set_size_mae": statistics.mean(abs(r["legacy_size"]-r["generated_size"]) for r in details) if details else 0.0, "exact_size_matches": sum(r["legacy_size"] == r["generated_size"] for r in details)}, details

def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--legacy", type=Path, required=True); parser.add_argument("--generated", type=Path, required=True); parser.add_argument("--out", type=Path, required=True); args = parser.parse_args()
    legacy, generated = read_gmt(args.legacy), read_gmt(args.generated)
    literal, literal_details = metrics(legacy, generated)
    normalized_legacy, normalized_generated = normalized_map(legacy), normalized_map(generated)
    norm_left = {key: genes for key, (_, genes) in normalized_legacy.items()}; norm_right = {key: genes for key, (_, genes) in normalized_generated.items()}
    normalized, normalized_details = metrics(norm_left, norm_right)
    normalized["common_normalized_names"] = normalized.pop("common_terms")
    payload = {"literal_name_comparison": literal, "case_insensitive_name_comparison": normalized, "literal_term_details": literal_details, "normalized_term_details": normalized_details}
    args.out.parent.mkdir(parents=True, exist_ok=True); args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"literal": literal, "case_insensitive": normalized}, sort_keys=True)); return 0
if __name__ == "__main__": raise SystemExit(main())
