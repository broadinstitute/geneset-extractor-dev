#!/usr/bin/env python3

import argparse
import csv
import statistics
from pathlib import Path


def read_gmt(path):
    """
    Read a GMT file.

    Returns
    -------
    dict
        {set_name: set(genes)}
    """
    sets = {}

    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.rstrip("\n")
            if not line:
                continue

            fields = line.split("\t")

            if len(fields) < 3:
                print(
                    f"WARNING: {path}:{line_no} has fewer than 3 columns; skipping"
                )
                continue

            name = fields[0]
            genes = {g.strip() for g in fields[2:] if g.strip()}

            if name in sets:
                print(
                    f"WARNING: duplicate gene-set name {name!r} in {path}; "
                    "merging memberships"
                )
                sets[name].update(genes)
            else:
                sets[name] = genes

    return sets


def safe_div(numerator, denominator):
    return numerator / denominator if denominator else 0.0


def compare_sets(reference, candidate):
    intersection = reference & candidate
    union = reference | candidate

    tp = len(intersection)
    ref_n = len(reference)
    cand_n = len(candidate)

    recall = safe_div(tp, ref_n)
    precision = safe_div(tp, cand_n)
    jaccard = safe_div(tp, len(union))

    if precision + recall:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = 0.0

    return {
        "reference_size": ref_n,
        "candidate_size": cand_n,
        "intersection": tp,
        "reference_only": ref_n - tp,
        "candidate_only": cand_n - tp,
        "recall": recall,
        "precision": precision,
        "jaccard": jaccard,
        "f1": f1,
        "exact_match": reference == candidate,
    }


def mean(values):
    return statistics.mean(values) if values else 0.0


def median(values):
    return statistics.median(values) if values else 0.0


def main():
    parser = argparse.ArgumentParser(
        description="Compare two GMT gene-set files."
    )

    parser.add_argument(
        "reference",
        help="Reference / legacy GMT file",
    )

    parser.add_argument(
        "candidate",
        help="Candidate / reconstructed GMT file",
    )

    parser.add_argument(
        "--output",
        "-o",
        default="gmt_comparison.tsv",
        help="Per-set comparison TSV (default: gmt_comparison.tsv)",
    )

    parser.add_argument(
        "--summary",
        default=None,
        help="Optional file to write the summary report",
    )

    parser.add_argument(
        "--show-only",
        type=int,
        default=20,
        help="Number of reference-only/candidate-only names to print (default: 20)",
    )

    args = parser.parse_args()

    reference_path = Path(args.reference)
    candidate_path = Path(args.candidate)

    reference = read_gmt(reference_path)
    candidate = read_gmt(candidate_path)

    reference_names = set(reference)
    candidate_names = set(candidate)

    common_names = sorted(reference_names & candidate_names)
    reference_only_names = sorted(reference_names - candidate_names)
    candidate_only_names = sorted(candidate_names - reference_names)

    rows = []

    total_reference_memberships = 0
    total_candidate_memberships = 0
    total_intersection = 0

    for name in common_names:
        metrics = compare_sets(reference[name], candidate[name])

        total_reference_memberships += metrics["reference_size"]
        total_candidate_memberships += metrics["candidate_size"]
        total_intersection += metrics["intersection"]

        rows.append(
            {
                "gene_set": name,
                **metrics,
            }
        )

    # Membership-level metrics across matched sets
    membership_recall = safe_div(
        total_intersection,
        total_reference_memberships,
    )

    membership_precision = safe_div(
        total_intersection,
        total_candidate_memberships,
    )

    membership_union = (
        total_reference_memberships
        + total_candidate_memberships
        - total_intersection
    )

    membership_jaccard = safe_div(
        total_intersection,
        membership_union,
    )

    # Macro / per-set metrics
    recalls = [r["recall"] for r in rows]
    precisions = [r["precision"] for r in rows]
    jaccards = [r["jaccard"] for r in rows]
    f1s = [r["f1"] for r in rows]

    exact_matches = sum(r["exact_match"] for r in rows)

    name_recall = safe_div(
        len(common_names),
        len(reference_names),
    )

    name_precision = safe_div(
        len(common_names),
        len(candidate_names),
    )

    summary_lines = []

    def add(line=""):
        summary_lines.append(line)

    add("=== GMT COMPARISON ===")
    add()
    add(f"Reference: {reference_path}")
    add(f"Candidate: {candidate_path}")
    add()

    add("=== GENE SET NAMES ===")
    add(f"Reference sets:       {len(reference_names):,}")
    add(f"Candidate sets:       {len(candidate_names):,}")
    add(f"Matched names:        {len(common_names):,}")
    add(f"Reference only:       {len(reference_only_names):,}")
    add(f"Candidate only:       {len(candidate_only_names):,}")
    add(f"Name recall:          {name_recall:.4f}")
    add(f"Name precision:       {name_precision:.4f}")
    add()

    add("=== MEMBERSHIPS — MATCHED SETS ===")
    add(
        f"Reference memberships: {total_reference_memberships:,}"
    )
    add(
        f"Candidate memberships: {total_candidate_memberships:,}"
    )
    add(
        f"Intersection:           {total_intersection:,}"
    )
    add(
        "Membership difference: "
        f"{abs(total_candidate_memberships - total_reference_memberships):,}"
    )
    add(f"Membership recall:      {membership_recall:.4f}")
    add(f"Membership precision:   {membership_precision:.4f}")
    add(f"Membership Jaccard:     {membership_jaccard:.4f}")
    add()

    add("=== PER-SET SIMILARITY ===")
    add(f"Mean recall:          {mean(recalls):.4f}")
    add(f"Median recall:        {median(recalls):.4f}")
    add(f"Mean precision:       {mean(precisions):.4f}")
    add(f"Median precision:     {median(precisions):.4f}")
    add(f"Mean Jaccard:         {mean(jaccards):.4f}")
    add(f"Median Jaccard:       {median(jaccards):.4f}")
    add(f"Mean F1:              {mean(f1s):.4f}")
    add(f"Median F1:            {median(f1s):.4f}")
    add(
        f"Exact set matches:    {exact_matches:,}/{len(common_names):,}"
    )
    add()

    if reference_only_names:
        add("=== REFERENCE-ONLY SETS ===")
        for name in reference_only_names[: args.show_only]:
            add(name)

        remaining = len(reference_only_names) - args.show_only
        if remaining > 0:
            add(f"... and {remaining:,} more")
        add()

    if candidate_only_names:
        add("=== CANDIDATE-ONLY SETS ===")
        for name in candidate_only_names[: args.show_only]:
            add(name)

        remaining = len(candidate_only_names) - args.show_only
        if remaining > 0:
            add(f"... and {remaining:,} more")
        add()

    # Lowest-scoring matched sets
    if rows:
        add("=== LOWEST JACCARD MATCHED SETS ===")

        for row in sorted(rows, key=lambda x: x["jaccard"])[:20]:
            add(
                f"{row['jaccard']:.4f}\t"
                f"recall={row['recall']:.4f}\t"
                f"precision={row['precision']:.4f}\t"
                f"ref={row['reference_size']}\t"
                f"cand={row['candidate_size']}\t"
                f"{row['gene_set']}"
            )

    summary_text = "\n".join(summary_lines)

    print(summary_text)

    if args.summary:
        with open(args.summary, "w", encoding="utf-8") as f:
            f.write(summary_text)
            f.write("\n")

    # Write detailed table
    fieldnames = [
        "gene_set",
        "reference_size",
        "candidate_size",
        "intersection",
        "reference_only",
        "candidate_only",
        "recall",
        "precision",
        "jaccard",
        "f1",
        "exact_match",
    ]

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            delimiter="\t",
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(row)

    print()
    print(f"Per-set results written to: {args.output}")

    if args.summary:
        print(f"Summary written to:         {args.summary}")


if __name__ == "__main__":
    main()
