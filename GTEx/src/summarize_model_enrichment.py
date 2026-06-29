#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


TISSUE_CONFIGS = {
    "adipose_subcutaneous": {
        "display_name": "Adipose Subcutaneous",
        "direction_categories": {
            "pos": ["immune_inflammation", "ecm_fibrosis"],
            "neg": ["adipocyte_lipid", "mitochondria_energetics"],
        },
        "category_keywords": {
            "adipocyte_lipid": [
                "adip",
                "lipid",
                "fatty acid",
                "triglycer",
                "cholesterol",
                "lipolysis",
                "ppar",
                "rxra",
                "insulin",
                "free fatty acid",
                "ketone",
                "adipogenesis",
                "peroxisome",
                "beige",
                "brown fat",
            ],
            "mitochondria_energetics": [
                "mitochond",
                "oxidative phosphorylation",
                "respiratory chain",
                "electron transport",
                "tca cycle",
                "atp synth",
                "beta oxidation",
                "microbody",
                "peroxisome",
                "metabolism",
            ],
            "ecm_fibrosis": [
                "extracellular matrix",
                "collagen",
                "fibroblast",
                "fibrosis",
                "elastic fiber",
                "wound healing",
                "epithelial mesenchymal",
                "emt",
                "stromal",
                "caf",
                "adhesion",
                "tgfb",
                "tgf beta",
            ],
            "immune_inflammation": [
                "immune",
                "interferon",
                "inflamm",
                "cytokine",
                "chemokine",
                "antigen",
                "leukocyte",
                "macrophage",
                "monocyte",
                "lymphocyte",
                "t cell",
                "b cell",
                "pbmc",
                "nfkb",
                "defense response",
                "viral",
            ],
        },
    }
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parents[3]
    gtex_root = repo_root / "geneset-extractor-dev" / "GTEx"
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run_root",
        default=str(gtex_root / "outputs" / "pigean_eaggl"),
    )
    parser.add_argument(
        "--tissue",
        default="adipose_subcutaneous",
    )
    parser.add_argument(
        "--top_n",
        type=int,
        default=20,
    )
    parser.add_argument(
        "--model_group",
        choices=["age_binned", "continuous_age", "hz_notebook", "tissue_versus"],
        default=None,
        help="optional model-group filter",
    )
    parser.add_argument(
        "--models",
        default=None,
        help="optional comma-separated model IDs to include",
    )
    parser.add_argument(
        "--output_prefix",
        default=None,
        help="optional output filename prefix; defaults to age_binned_models, continuous_age_models, or tissue_versus_models when model_group is set",
    )
    return parser


def load_tsv_gz(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def load_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv_gz(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with gzip.open(path, "wt", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def tissue_keywords_for(tissue_id: str) -> dict[str, list[str]]:
    if tissue_id in TISSUE_CONFIGS:
        return TISSUE_CONFIGS[tissue_id]["category_keywords"]
    tokens = [token for token in tissue_id.lower().split("_") if token]
    generic = " ".join(tokens)
    return {"tissue_named_signal": tokens + ([generic] if generic else [])}


def expected_categories_for(tissue_id: str, direction: str) -> list[str]:
    if tissue_id in TISSUE_CONFIGS:
        return TISSUE_CONFIGS[tissue_id]["direction_categories"].get(direction, [])
    return list(tissue_keywords_for(tissue_id).keys())


def safe_float(value: str | None) -> float:
    if value in (None, "", "NA"):
        return float("nan")
    return float(value)


def model_sort_key(model_id: str) -> tuple[str, int]:
    prefix = "".join(ch for ch in model_id if not ch.isdigit())
    suffix = "".join(ch for ch in model_id if ch.isdigit())
    return prefix, int(suffix or "0")


def resolve_output_prefix(args: argparse.Namespace) -> str:
    if args.output_prefix:
        return str(args.output_prefix)
    if args.model_group == "age_binned":
        return "age_binned_models"
    if args.model_group == "continuous_age":
        return "continuous_age_models"
    if args.model_group == "hz_notebook":
        return "hz_notebook_models"
    if args.model_group == "tissue_versus":
        return "tissue_versus_models"
    return "all_models"


@dataclass
class QueryAssessment:
    tissue_id: str
    model_id: str
    query_name: str
    comparison: str
    direction: str
    query_dir: Path
    gene_count: int
    pigean_hits: int
    eaggl_hits: int
    factor_hits: int
    score: float
    call: str
    matched_categories: list[str]
    top_pigean_labels: list[str]
    top_eaggl_labels: list[str]
    top_factor_labels: list[str]
    reason: str


def score_matches(
    labels: list[str],
    *,
    expected_categories: list[str],
    category_keywords: dict[str, list[str]],
    base_weight: float,
) -> tuple[float, list[str], int]:
    score = 0.0
    matched_categories: list[str] = []
    matched_label_count = 0
    normalized_labels = [normalize_text(label) for label in labels]
    for label_index, label in enumerate(normalized_labels, start=1):
        label_weight = base_weight / label_index
        hit_any = False
        for category in expected_categories:
            keywords = category_keywords.get(category, [])
            if any(keyword in label for keyword in keywords):
                score += label_weight
                matched_categories.append(category)
                hit_any = True
        if hit_any:
            matched_label_count += 1
    return score, sorted(set(matched_categories)), matched_label_count


def top_pigean_labels(query_dir: Path, top_n: int) -> list[str]:
    path = query_dir / "pigean.gene_set_stats.out"
    if not path.exists():
        return []
    rows = [row for row in load_tsv(path) if row.get("filter_reason") == "kept"]
    rows.sort(
        key=lambda row: (
            -(safe_float(row.get("beta")) if not math.isnan(safe_float(row.get("beta"))) else float("-inf")),
            safe_float(row.get("P")),
            row.get("Gene_Set", ""),
        )
    )
    return [row["Gene_Set"] for row in rows[:top_n]]


def top_eaggl_cluster_labels(query_dir: Path, top_n: int) -> list[str]:
    path = query_dir / "eaggl.gene_set_clusters.out"
    if not path.exists():
        return []
    rows = load_tsv(path)
    rows.sort(
        key=lambda row: (
            -(safe_float(row.get("beta")) if not math.isnan(safe_float(row.get("beta"))) else float("-inf")),
            row.get("Gene_Set", ""),
        )
    )
    return [row["Gene_Set"] for row in rows[:top_n]]


def top_factor_labels(query_dir: Path, top_n: int) -> list[str]:
    path = query_dir / "eaggl.factors.out"
    if not path.exists():
        return []
    rows = load_tsv(path)
    labels: list[str] = []
    for row in rows[:top_n]:
        for field in ("label", "top_gene_sets", "top_genes"):
            value = row.get(field, "")
            if value:
                labels.extend([token.strip() for token in value.split(",") if token.strip()])
    return labels[:top_n]


def assess_query(row: dict[str, str], top_n: int) -> QueryAssessment:
    tissue_id = row["tissue_id"]
    expected_categories = expected_categories_for(tissue_id, row["direction"])
    category_keywords = tissue_keywords_for(tissue_id)
    query_dir = Path(row["query_dir"])
    pigean_labels = top_pigean_labels(query_dir, top_n)
    eaggl_labels = top_eaggl_cluster_labels(query_dir, top_n)
    factor_labels = top_factor_labels(query_dir, top_n)
    pigean_score, pigean_categories, pigean_hits = score_matches(
        pigean_labels,
        expected_categories=expected_categories,
        category_keywords=category_keywords,
        base_weight=3.0,
    )
    eaggl_score, eaggl_categories, eaggl_hits = score_matches(
        eaggl_labels,
        expected_categories=expected_categories,
        category_keywords=category_keywords,
        base_weight=2.0,
    )
    factor_score, factor_categories, factor_hits = score_matches(
        factor_labels,
        expected_categories=expected_categories,
        category_keywords=category_keywords,
        base_weight=1.5,
    )
    total_score = pigean_score + eaggl_score + factor_score
    matched_categories = sorted(set(pigean_categories + eaggl_categories + factor_categories))
    if total_score >= 6:
        call = "strong"
    elif total_score >= 2:
        call = "partial"
    else:
        call = "weak"
    reason_bits = []
    if pigean_categories:
        reason_bits.append("pigean=" + ",".join(pigean_categories))
    if eaggl_categories:
        reason_bits.append("eaggl_clusters=" + ",".join(eaggl_categories))
    if factor_categories:
        reason_bits.append("eaggl_factors=" + ",".join(factor_categories))
    if not reason_bits:
        reason_bits.append("no expected keyword hits")
    return QueryAssessment(
        tissue_id=tissue_id,
        model_id=row["model_id"],
        query_name=row["query_name"],
        comparison=row["comparison"],
        direction=row["direction"],
        query_dir=query_dir,
        gene_count=int(row["gene_count"]),
        pigean_hits=pigean_hits,
        eaggl_hits=eaggl_hits,
        factor_hits=factor_hits,
        score=round(total_score, 4),
        call=call,
        matched_categories=matched_categories,
        top_pigean_labels=pigean_labels[:5],
        top_eaggl_labels=eaggl_labels[:5],
        top_factor_labels=factor_labels[:5],
        reason="; ".join(reason_bits),
    )


def summarize_models(assessments: list[QueryAssessment]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    by_model: dict[str, list[QueryAssessment]] = defaultdict(list)
    for assessment in assessments:
        by_model[assessment.model_id].append(assessment)
    for model_id in sorted(by_model, key=model_sort_key):
        items = by_model[model_id]
        items.sort(key=lambda item: (item.score, item.query_name), reverse=True)
        total_score = sum(item.score for item in items)
        strong_count = sum(1 for item in items if item.call == "strong")
        partial_count = sum(1 for item in items if item.call == "partial")
        weak_count = sum(1 for item in items if item.call == "weak")
        matched_categories = Counter(category for item in items for category in item.matched_categories)
        rows.append(
            {
                "model_id": model_id,
                "num_queries": len(items),
                "total_score": round(total_score, 4),
                "mean_score": round(total_score / len(items), 4),
                "num_strong_queries": strong_count,
                "num_partial_queries": partial_count,
                "num_weak_queries": weak_count,
                "best_query_name": items[0].query_name,
                "best_query_score": items[0].score,
                "best_query_call": items[0].call,
                "top_categories": ",".join(category for category, _ in matched_categories.most_common(4)),
                "best_query_reason": items[0].reason,
            }
        )
    rows.sort(
        key=lambda row: (
            -float(row["total_score"]),
            -int(row["num_strong_queries"]),
            -float(row["mean_score"]),
            model_sort_key(str(row["model_id"])),
        )
    )
    return rows


def write_adipose_summary(
    tissue_dir: Path,
    model_rows: list[dict[str, object]],
    query_rows: list[dict[str, object]],
    top_n: int,
    *,
    output_prefix: str,
    model_group_label: str,
) -> None:
    write_tsv_gz(
        tissue_dir / f"{output_prefix}_biology_model_summary.tsv.gz",
        model_rows,
        [
            "model_id",
            "num_queries",
            "total_score",
            "mean_score",
            "num_strong_queries",
            "num_partial_queries",
            "num_weak_queries",
            "best_query_name",
            "best_query_score",
            "best_query_call",
            "top_categories",
            "best_query_reason",
        ],
    )
    write_tsv_gz(
        tissue_dir / f"{output_prefix}_biology_query_summary.tsv.gz",
        query_rows,
        [
            "tissue_id",
            "model_id",
            "query_name",
            "comparison",
            "direction",
            "gene_count",
            "score",
            "call",
            "matched_categories",
            "pigean_hits",
            "eaggl_hits",
            "factor_hits",
            "top_pigean_labels",
            "top_eaggl_labels",
            "top_factor_labels",
            "reason",
        ],
    )
    top_models = model_rows[:5]
    lines = [
        f"# Adipose Subcutaneous PIGEAN EAGGL Summary: {model_group_label}",
        "",
        f"This summary scores each {model_group_label} model by how often its PIGEAN enrichments and EAGGL labels recover adipose-subcutaneous-relevant biology.",
        "",
        "Directional expectations used:",
        "- positive age contrasts: immune/inflammation and ECM/fibrosis",
        "- negative age contrasts: adipocyte/lipid and mitochondrial/energetic programs",
        "",
        f"- queries summarized: {len(query_rows)}",
        f"- top labels inspected per stage: {top_n}",
        "",
        "Top models:",
    ]
    for row in top_models:
        lines.append(
            f"- `{row['model_id']}`: total_score={row['total_score']}, strong_queries={row['num_strong_queries']}, top_categories={row['top_categories'] or 'none'}"
        )
    lines.extend(
        [
            "",
            "Files:",
            f"- `{output_prefix}_biology_model_summary.tsv.gz`",
            f"- `{output_prefix}_biology_query_summary.tsv.gz`",
        ]
    )
    write_text(tissue_dir / f"{output_prefix}_biology_summary.md", "\n".join(lines) + "\n")
    write_text(
        tissue_dir / f"{output_prefix}_biology_summary_commands.md",
        "# Commands\n\n```bash\npython3 geneset-extractor-dev/GTEx/src/summarize_model_enrichment.py\n```\n",
    )
    write_text(
        tissue_dir / f"{output_prefix}_biology_summary.log",
        f"[{utc_now()}] wrote {output_prefix}_biology_model_summary.tsv.gz, {output_prefix}_biology_query_summary.tsv.gz, and {output_prefix}_biology_summary.md\n",
    )


def write_all_tissues_summary(
    out_dir: Path,
    tissue_model_rows: dict[str, list[dict[str, object]]],
    *,
    output_prefix: str,
    model_group_label: str,
) -> None:
    aggregate_rows: list[dict[str, object]] = []
    by_model: dict[str, list[tuple[str, dict[str, object]]]] = defaultdict(list)
    for tissue_id, rows in tissue_model_rows.items():
        for row in rows:
            by_model[str(row["model_id"])].append((tissue_id, row))
    for model_id in sorted(by_model, key=model_sort_key):
        entries = by_model[model_id]
        tissue_count = len(entries)
        total_score = sum(float(entry["total_score"]) for _, entry in entries)
        mean_score = total_score / tissue_count
        tissue_wins = sum(1 for tissue_id, entry in entries if entry == tissue_model_rows[tissue_id][0])
        top3_count = sum(1 for tissue_id, entry in entries if entry in tissue_model_rows[tissue_id][:3])
        strong_total = sum(int(entry["num_strong_queries"]) for _, entry in entries)
        categories = Counter()
        for _, entry in entries:
            for category in str(entry["top_categories"]).split(","):
                if category:
                    categories[category] += 1
        aggregate_rows.append(
            {
                "model_id": model_id,
                "num_tissues": tissue_count,
                "mean_tissue_score": round(mean_score, 4),
                "total_score_across_tissues": round(total_score, 4),
                "num_tissue_wins": tissue_wins,
                "num_top3_tissue_finishes": top3_count,
                "num_strong_queries_across_tissues": strong_total,
                "top_categories": ",".join(category for category, _ in categories.most_common(4)),
            }
        )
    aggregate_rows.sort(
        key=lambda row: (
            -float(row["mean_tissue_score"]),
            -int(row["num_tissue_wins"]),
            -int(row["num_top3_tissue_finishes"]),
            model_sort_key(str(row["model_id"])),
        )
    )
    write_tsv_gz(
        out_dir / f"{output_prefix}_all_tissues_biology_model_summary.tsv.gz",
        aggregate_rows,
        [
            "model_id",
            "num_tissues",
            "mean_tissue_score",
            "total_score_across_tissues",
            "num_tissue_wins",
            "num_top3_tissue_finishes",
            "num_strong_queries_across_tissues",
            "top_categories",
        ],
    )
    lines = [
        f"# All Tissues PIGEAN EAGGL Summary: {model_group_label}",
        "",
        f"This table ranks {model_group_label} models by how well they recover tissue-relevant biology across all available tissues.",
        "",
        f"- tissues summarized: {len(tissue_model_rows)}",
        "",
        "Top models:",
    ]
    for row in aggregate_rows[:5]:
        lines.append(
            f"- `{row['model_id']}`: mean_tissue_score={row['mean_tissue_score']}, tissue_wins={row['num_tissue_wins']}, top_categories={row['top_categories'] or 'none'}"
        )
    lines.extend(["", "Files:", f"- `{output_prefix}_all_tissues_biology_model_summary.tsv.gz`"])
    write_text(out_dir / f"{output_prefix}_all_tissues_biology_summary.md", "\n".join(lines) + "\n")
    write_text(
        out_dir / f"{output_prefix}_all_tissues_biology_summary_commands.md",
        "# Commands\n\n```bash\npython3 geneset-extractor-dev/GTEx/src/summarize_model_enrichment.py\n```\n",
    )
    write_text(
        out_dir / f"{output_prefix}_all_tissues_biology_summary.log",
        f"[{utc_now()}] wrote {output_prefix}_all_tissues_biology_model_summary.tsv.gz and {output_prefix}_all_tissues_biology_summary.md\n",
    )


def main() -> int:
    args = build_parser().parse_args()
    run_root = Path(args.run_root).resolve()
    tissue_runs_root = run_root / "runs"
    output_prefix = resolve_output_prefix(args)
    model_group_label = args.model_group or "all"
    query_status_path = run_root / "query_status.tsv.gz"
    if not query_status_path.exists():
        raise FileNotFoundError(f"missing query_status.tsv.gz: {query_status_path}")
    status_rows = [row for row in load_tsv_gz(query_status_path) if row.get("status") == "complete"]
    if args.model_group is not None:
        status_rows = [row for row in status_rows if row.get("model_group") == args.model_group]
    if args.models:
        allowed_models = {item.strip() for item in str(args.models).split(",") if item.strip()}
        status_rows = [row for row in status_rows if row.get("model_id") in allowed_models]
    by_tissue: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in status_rows:
        by_tissue[row["tissue_id"]].append(row)

    tissue_model_rows: dict[str, list[dict[str, object]]] = {}
    for tissue_id, rows in sorted(by_tissue.items()):
        assessments = [assess_query(row, args.top_n) for row in rows]
        query_rows = [
            {
                "tissue_id": item.tissue_id,
                "model_id": item.model_id,
                "query_name": item.query_name,
                "comparison": item.comparison,
                "direction": item.direction,
                "gene_count": item.gene_count,
                "score": item.score,
                "call": item.call,
                "matched_categories": ",".join(item.matched_categories),
                "pigean_hits": item.pigean_hits,
                "eaggl_hits": item.eaggl_hits,
                "factor_hits": item.factor_hits,
                "top_pigean_labels": " | ".join(item.top_pigean_labels),
                "top_eaggl_labels": " | ".join(item.top_eaggl_labels),
                "top_factor_labels": " | ".join(item.top_factor_labels),
                "reason": item.reason,
            }
            for item in sorted(assessments, key=lambda item: (-item.score, item.query_name))
        ]
        model_rows = summarize_models(assessments)
        tissue_model_rows[tissue_id] = model_rows
        if tissue_id == args.tissue:
            tissue_dir = tissue_runs_root / tissue_id
            write_adipose_summary(
                tissue_dir,
                model_rows,
                query_rows,
                args.top_n,
                output_prefix=output_prefix,
                model_group_label=model_group_label,
            )

    write_all_tissues_summary(
        run_root,
        tissue_model_rows,
        output_prefix=output_prefix,
        model_group_label=model_group_label,
    )

    commands_lines = [
        "# Summary Commands",
        "",
        "```bash",
        "python3 geneset-extractor-dev/GTEx/src/summarize_model_enrichment.py",
        "```",
        "",
        f"output_prefix={output_prefix}",
        f"model_group={model_group_label}",
        "",
        f"Generated at {utc_now()}",
    ]
    write_text(run_root / f"{output_prefix}_summary_commands.md", "\n".join(commands_lines) + "\n")

    manifest = {
        "run_root": str(run_root),
        "tissue": args.tissue,
        "top_n": args.top_n,
        "model_group": args.model_group,
        "output_prefix": output_prefix,
        "num_tissues_summarized": len(tissue_model_rows),
        "generated_at": utc_now(),
    }
    write_text(run_root / f"{output_prefix}_summary_manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
