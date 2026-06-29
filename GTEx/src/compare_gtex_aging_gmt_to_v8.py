#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare a v10-adapted GTExAgingSignatures GMT pair to the existing v8 GTEx aging GMT."
    )
    parser.add_argument("--up_gmt", required=True)
    parser.add_argument("--down_gmt", required=True)
    parser.add_argument("--reference_gmt", required=True)
    parser.add_argument("--out_dir", required=True)
    return parser


def parse_gmt(path: Path) -> dict[str, list[str]]:
    terms: dict[str, list[str]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            terms[parts[0]] = [gene for gene in parts[1:] if gene]
    return terms


def normalize_term(term: str) -> str:
    normalized = term.replace(" ", "_")
    normalized = re.sub(r"_Up$", "_Up", normalized)
    normalized = re.sub(r"_Down$", "_Down", normalized)
    return normalized


def extract_tissue(term: str) -> str:
    token = normalize_term(term)
    match = re.match(r"^GTEx_([^_]+(?:_[^_]+)*)_20-29_vs_", token)
    if match:
        return match.group(1)
    return token


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def write_tsv_gz(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with gzip.open(path, "wt", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    args = build_parser().parse_args()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    up_terms = {f"{normalize_term(term)}_Up" if not normalize_term(term).endswith("_Up") else normalize_term(term): genes for term, genes in parse_gmt(Path(args.up_gmt)).items()}
    down_terms = {f"{normalize_term(term)}_Down" if not normalize_term(term).endswith("_Down") else normalize_term(term): genes for term, genes in parse_gmt(Path(args.down_gmt)).items()}
    produced_terms = {}
    produced_terms.update(up_terms)
    produced_terms.update(down_terms)
    reference_terms = {normalize_term(term): genes for term, genes in parse_gmt(Path(args.reference_gmt)).items()}

    produced_term_set = set(produced_terms)
    reference_term_set = set(reference_terms)
    shared_terms = sorted(produced_term_set & reference_term_set)

    per_term_rows: list[dict[str, object]] = []
    for term in shared_terms:
        produced_genes = set(produced_terms[term])
        reference_genes = set(reference_terms[term])
        per_term_rows.append(
            {
                "term": term,
                "tissue": extract_tissue(term),
                "produced_gene_count": len(produced_genes),
                "reference_gene_count": len(reference_genes),
                "intersection_gene_count": len(produced_genes & reference_genes),
                "union_gene_count": len(produced_genes | reference_genes),
                "gene_jaccard": round(jaccard(produced_genes, reference_genes), 6),
            }
        )

    produced_tissues = sorted({extract_tissue(term) for term in produced_term_set})
    reference_tissues = sorted({extract_tissue(term) for term in reference_term_set})
    summary = {
        "produced_term_count": len(produced_term_set),
        "reference_term_count": len(reference_term_set),
        "shared_term_count": len(shared_terms),
        "produced_only_term_count": len(produced_term_set - reference_term_set),
        "reference_only_term_count": len(reference_term_set - produced_term_set),
        "produced_tissue_count": len(produced_tissues),
        "reference_tissue_count": len(reference_tissues),
        "shared_tissue_count": len(set(produced_tissues) & set(reference_tissues)),
        "mean_shared_term_gene_jaccard": round(sum(row["gene_jaccard"] for row in per_term_rows) / len(per_term_rows), 6) if per_term_rows else 0.0,
    }

    write_tsv_gz(
        out_dir / "gtex_aging_v10_vs_v8_per_term.tsv.gz",
        per_term_rows,
        [
            "term",
            "tissue",
            "produced_gene_count",
            "reference_gene_count",
            "intersection_gene_count",
            "union_gene_count",
            "gene_jaccard",
        ],
    )
    write_text(out_dir / "gtex_aging_v10_vs_v8_summary.json", json.dumps(summary, indent=2, sort_keys=True) + "\n")
    write_text(
        out_dir / "gtex_aging_v10_vs_v8_summary.md",
        "\n".join(
            [
                "# GTEx Aging Signature GMT Comparison",
                "",
                f"- produced_term_count: `{summary['produced_term_count']}`",
                f"- reference_term_count: `{summary['reference_term_count']}`",
                f"- shared_term_count: `{summary['shared_term_count']}`",
                f"- produced_only_term_count: `{summary['produced_only_term_count']}`",
                f"- reference_only_term_count: `{summary['reference_only_term_count']}`",
                f"- produced_tissue_count: `{summary['produced_tissue_count']}`",
                f"- reference_tissue_count: `{summary['reference_tissue_count']}`",
                f"- shared_tissue_count: `{summary['shared_tissue_count']}`",
                f"- mean_shared_term_gene_jaccard: `{summary['mean_shared_term_gene_jaccard']}`",
                "",
                "Files:",
                "- `gtex_aging_v10_vs_v8_summary.json`",
                "- `gtex_aging_v10_vs_v8_summary.md`",
                "- `gtex_aging_v10_vs_v8_per_term.tsv.gz`",
            ]
        )
        + "\n",
    )
    write_text(
        out_dir / "gtex_aging_v10_vs_v8_summary.log",
        "wrote GTEx aging signature comparison outputs\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
