#!/usr/bin/env python3
from __future__ import annotations
"""
Read deg_long.tsv and print gene counts at multiple logFC thresholds.
Run AFTER sbatch_01_de_only.sh completes.
Use this to decide TOP_K for sbatch_03_extract_genesets.sh.

Expected deg_long.tsv columns:
  comparison_id, gene_id, gene_symbol, logFC, stat, pvalue, padj

Usage:
  # Full table for one study:
  python summarize_de_natural_sizes.py --deg_tsv outputs/analysis/KF-TALL-vs-T21/de_results/deg_long.tsv

  # One-line summary (used by 02_check_natural_sizes.sh):
  python summarize_de_natural_sizes.py --deg_tsv ... --one_line
"""
import argparse
import csv
import sys
from pathlib import Path

PADJ_MAX = 0.05
LOGFC_THRESHOLDS = [0.5, 1.0, 1.5, 2.0, 2.5]


def _safe_float(s: str) -> float | None:
    if s in ("", "NA", "nan", "NaN", "Inf", "-Inf"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def summarize(deg_tsv: Path) -> dict:
    up: list[float] = []
    down: list[float] = []
    total = 0

    with open(deg_tsv) as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            total += 1
            padj = _safe_float(row.get("padj", ""))
            logfc = _safe_float(row.get("logFC", ""))
            if padj is None or logfc is None:
                continue
            if padj < PADJ_MAX:
                if logfc > 0:
                    up.append(logfc)
                else:
                    down.append(abs(logfc))

    result: dict = {
        "total_tested": total,
        "up": {},    # threshold → count
        "down": {},
    }
    for t in LOGFC_THRESHOLDS:
        result["up"][t]   = sum(1 for v in up   if v >= t)
        result["down"][t] = sum(1 for v in down if v >= t)

    return result


def print_table(label: str, result: dict) -> None:
    total = result["total_tested"]
    print(f"\n{'='*72}")
    print(f"  Study : {label}")
    print(f"  Total genes tested : {total:,}")
    print(f"  Filter : padj < {PADJ_MAX}")
    print(f"{'─'*72}")
    print(f"  {'|logFC| ≥':<12} {'UP':>8}  {'DOWN':>8}  {'TOTAL':>8}  note")
    print(f"  {'─'*62}")
    for t in LOGFC_THRESHOLDS:
        u = result["up"][t]
        d = result["down"][t]
        tot = u + d
        note = ""
        if t == 1.0:
            note = "← baseline plan"
        if tot == 0:
            note += "  ⚠ no genes pass"
        elif tot < 50:
            note += "  ⚠ <50 total (PIGEAN underpowered)"
        elif tot <= 100:
            note += "  ← natural size ≤100: top_k cap not needed"
        elif tot <= 300:
            note += "  (top_k=100~200 reasonable)"
        else:
            note += "  (large: top_k cap useful)"
        print(f"  {t:<12.1f} {u:>8,}  {d:>8,}  {tot:>8,}  {note}")
    print(f"{'='*72}")

    # Recommendation
    print("  → Suggested action:")
    u1 = result["up"][1.0]
    d1 = result["down"][1.0]
    tot1 = u1 + d1
    u2 = result["up"][2.0]
    d2 = result["down"][2.0]
    tot2 = u2 + d2
    if tot1 < 50:
        print(f"     Natural size at |logFC|≥1 is {tot1} — try |logFC|≥0.5 for more genes")
    elif tot1 <= 150:
        print(f"     Natural size at |logFC|≥1 is {tot1} — top_k cap not needed, use natural cutoff")
    elif tot2 <= 150:
        print(f"     Natural size at |logFC|≥2 is {tot2} — consider tightening to |logFC|≥2")
    else:
        print(f"     {tot1:,} genes at |logFC|≥1 — top_k=100 or 200 both reasonable for GWAS")
    print()


def print_one_line(label: str, result: dict) -> None:
    parts = []
    for t in LOGFC_THRESHOLDS:
        u = result["up"][t]
        d = result["down"][t]
        parts.append(f"|FC|≥{t:.1f}: {u}↑{d}↓")
    print(f"{label:<30}  tested={result['total_tested']:,}  |  " + "  |  ".join(parts))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--deg_tsv", required=True)
    p.add_argument("--one_line", action="store_true", help="Print compact one-line summary")
    args = p.parse_args()

    path = Path(args.deg_tsv)
    if not path.exists():
        print(f"[SKIP] not found: {path}", file=sys.stderr)
        return

    # Label: parent-parent directory name (e.g. KF-TALL-vs-T21)
    label = path.parent.parent.name

    result = summarize(path)

    if args.one_line:
        print_one_line(label, result)
    else:
        print_table(label, result)


if __name__ == "__main__":
    main()
