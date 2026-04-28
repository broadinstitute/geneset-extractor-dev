#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gzip
import re
from dataclasses import dataclass
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parents[3]
    gtex_root = repo_root / "geneset-extractor-dev" / "GTEx"
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pigean_root",
        default=str(gtex_root / "outputs" / "pigean_eaggl"),
    )
    parser.add_argument(
        "--genesets_root",
        default=str(gtex_root / "outputs" / "genesets"),
    )
    parser.add_argument(
        "--planning_root",
        default=str(gtex_root / "planning"),
    )
    parser.add_argument(
        "--tissue",
        default="adipose_subcutaneous",
    )
    parser.add_argument(
        "--model_groups",
        default="models,tissue_models",
        help="comma-separated list drawn from models,tissue_models",
    )
    parser.add_argument(
        "--top_n",
        type=int,
        default=5,
    )
    parser.add_argument(
        "--out_dir",
        default=None,
    )
    parser.add_argument(
        "--output_prefix",
        default="top_models",
    )
    return parser


def load_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def load_tsv_gz(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv_gz(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def safe_float(value: str | None) -> float:
    if value in (None, "", "NA"):
        return float("-inf")
    return float(value)


def safe_int(value: str | None) -> int:
    if value in (None, "", "NA"):
        return 0
    return int(float(value))


def model_sort_key(model_id: str) -> tuple[str, int]:
    prefix = "".join(ch for ch in model_id if not ch.isdigit())
    digits = "".join(ch for ch in model_id if ch.isdigit())
    return prefix, int(digits or "0")


def parse_model_catalog(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    matches = list(re.finditer(r"^###\s+([A-Z]\d+)\s+`[^`]+`\n", text, flags=re.MULTILINE))
    definitions: dict[str, str] = {}
    for index, match in enumerate(matches):
        model_id = match.group(1)
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[start:end]
        block_lines = [line.rstrip() for line in block.splitlines()]
        intent = ""
        workflow_parts: list[str] = []
        extractor_parts: list[str] = []
        section = None
        for line in block_lines:
            stripped = line.strip()
            if stripped.startswith("- Intent:"):
                intent = stripped.split(":", 1)[1].strip()
            elif stripped == "- Workflow:":
                section = "workflow"
            elif stripped == "- Extractor:":
                section = "extractor"
            elif stripped.startswith("- Expected effect on gene inclusion:"):
                section = None
            elif stripped.startswith("- `") or stripped.startswith("- "):
                if section == "workflow":
                    workflow_parts.append(stripped[2:].strip())
                elif section == "extractor":
                    extractor_parts.append(stripped[2:].strip())
            elif stripped.startswith("  - "):
                value = stripped[4:].strip()
                if section == "workflow":
                    workflow_parts.append(value)
                elif section == "extractor":
                    extractor_parts.append(value)
        pieces: list[str] = []
        if intent:
            pieces.append(intent)
        if workflow_parts:
            pieces.append("workflow: " + "; ".join(workflow_parts))
        if extractor_parts:
            pieces.append("extractor: " + "; ".join(extractor_parts))
        definitions[model_id] = " | ".join(pieces) if pieces else ""
    return definitions


def load_manifest_definitions(path: Path) -> dict[str, str]:
    rows = load_tsv(path)
    definitions: dict[str, str] = {}
    for row in rows:
        model_id = row.get("model_id", "").strip()
        if not model_id:
            continue
        summary = row.get("summary", "").strip()
        rationale = row.get("rationale", "").strip()
        settings = []
        for key in (
            "WORKFLOW_COVARIATES",
            "ANNOTATION_MODE",
            "EXTRACTOR_POSTPROCESS_MODE",
            "EXTRACTOR_SCORE_MODE",
            "EXTRACTOR_SELECT",
            "EXTRACTOR_PADJ_MAX",
            "EXTRACTOR_MIN_SCORE",
            "EXTRACTOR_GMT_BIOTYPE_ALLOWLIST",
        ):
            value = row.get(key, "").strip()
            if value and value != "NA":
                settings.append(f"{key.lower()}={value}")
        parts = [part for part in (summary, "settings: " + "; ".join(settings) if settings else "", "rationale: " + rationale if rationale else "") if part]
        definitions[model_id] = " | ".join(parts)
    return definitions


@dataclass
class GroupInfo:
    cluster_id: str
    representative_model: str
    representative_reason: str
    models: list[str]


def load_group_info(path: Path) -> tuple[dict[str, GroupInfo], dict[str, str]]:
    rows = load_tsv(path)
    by_model: dict[str, GroupInfo] = {}
    label_by_model: dict[str, str] = {}
    for row in rows:
        models = [item.strip() for item in row.get("models", "").split(",") if item.strip()]
        info = GroupInfo(
            cluster_id=row.get("cluster_id", "").strip(),
            representative_model=row.get("representative_model", "").strip(),
            representative_reason=row.get("representative_reason", "").strip(),
            models=models,
        )
        for model_id in models:
            by_model[model_id] = info
        label_by_model[info.representative_model] = f"{info.cluster_id}: {','.join(models)}"
    return by_model, label_by_model


def load_query_map(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    rows = load_tsv_gz(path)
    return {(row.get("model_id", ""), row.get("query_name", "")): row for row in rows}


def ranking_key(row: dict[str, str]) -> tuple[float, int, float, float, tuple[str, int]]:
    return (
        safe_float(row.get("total_score")),
        safe_int(row.get("num_strong_queries")),
        safe_float(row.get("mean_score")),
        safe_float(row.get("best_query_score")),
        model_sort_key(row.get("model_id", "")),
    )


def format_top_reason(model_row: dict[str, str]) -> str:
    return (
        f"ranked by total_score={model_row.get('total_score', 'NA')}, "
        f"num_strong_queries={model_row.get('num_strong_queries', 'NA')}, "
        f"mean_score={model_row.get('mean_score', 'NA')}; "
        f"best query {model_row.get('best_query_name', 'NA')} "
        f"scored {model_row.get('best_query_score', 'NA')} "
        f"({model_row.get('best_query_call', 'NA')}) with {model_row.get('best_query_reason', 'NA')}"
    )


def summarize_group(
    *,
    model_group: str,
    summary_rows: list[dict[str, str]],
    query_rows: dict[tuple[str, str], dict[str, str]],
    group_map: dict[str, GroupInfo],
    definition_map: dict[str, str],
    top_n: int,
) -> tuple[list[dict[str, object]], str]:
    ranked_rows = sorted(summary_rows, key=ranking_key, reverse=True)
    selected_rows = ranked_rows[:top_n]
    report_rows: list[dict[str, object]] = []
    md_lines = [
        f"## {model_group}",
        "",
        f"Top models are ranked by `total_score`, then `num_strong_queries`, then `mean_score`, then `best_query_score`.",
        "",
        "Metric definitions:",
        "- `score` is first computed per query by the existing PIGEAN/EAGGL biology summarizer.",
        "- Per query, the script scans top PIGEAN labels, top EAGGL cluster labels, and top EAGGL factor labels for tissue-expected biology keywords.",
        "- PIGEAN matches contribute base weight `3.0`, EAGGL cluster matches contribute base weight `2.0`, and EAGGL factor matches contribute base weight `1.5`.",
        "- Within each source, earlier ranked labels count more: label rank `r` contributes `base_weight / r` when it matches expected biology.",
        "- `total_score` is the sum of those per-query scores across all queries for the model.",
        "- `num_strong_queries` counts how many model queries had per-query `score >= 6`.",
        "- `mean_score` is `total_score / num_queries` for that model.",
        "- `best_query_score` is the maximum per-query score among that model's queries.",
        "- `best_query_reason` records which biology categories were matched in PIGEAN, EAGGL clusters, and EAGGL factors for that best query.",
        "- The ranking therefore rewards models that repeatedly produce high-scoring, tissue-relevant query labels, not just one isolated hit.",
        "",
    ]
    represented_groups: list[str] = []
    seen_group_keys: set[str] = set()
    for rank, row in enumerate(selected_rows, start=1):
        model_id = row.get("model_id", "").strip()
        info = group_map.get(model_id)
        if info:
            group_key = info.cluster_id
            cluster_id = info.cluster_id
            representative_model = info.representative_model
            representative_reason = info.representative_reason
            group_models = ",".join(info.models)
        else:
            group_key = f"singleton:{model_id}"
            cluster_id = ""
            representative_model = model_id
            representative_reason = "unique model; no identical-model cluster"
            group_models = model_id
        representative_definition = definition_map.get(representative_model, "")
        query_row = query_rows.get((model_id, row.get("best_query_name", "")), {})
        represented_note = ""
        if group_key not in seen_group_keys:
            seen_group_keys.add(group_key)
            if cluster_id:
                represented_groups.append(
                    f"- `{cluster_id}` represented by top model `{model_id}`; representative model `{representative_model}`; members `{group_models}`"
                )
            else:
                represented_groups.append(f"- unique model `{model_id}` is its own represented group")
            represented_note = "new represented group"
        else:
            represented_note = "same represented group as an earlier top model"
        report_rows.append(
            {
                "model_group": model_group,
                "rank": rank,
                "model_id": model_id,
                "cluster_id": cluster_id,
                "group_models": group_models,
                "representative_model": representative_model,
                "representative_reason": representative_reason,
                "representative_definition": representative_definition,
                "total_score": row.get("total_score", ""),
                "mean_score": row.get("mean_score", ""),
                "num_queries": row.get("num_queries", ""),
                "num_strong_queries": row.get("num_strong_queries", ""),
                "num_partial_queries": row.get("num_partial_queries", ""),
                "num_weak_queries": row.get("num_weak_queries", ""),
                "best_query_name": row.get("best_query_name", ""),
                "best_query_score": row.get("best_query_score", ""),
                "best_query_call": row.get("best_query_call", ""),
                "best_query_reason": row.get("best_query_reason", ""),
                "best_query_direction": query_row.get("direction", ""),
                "best_query_matched_categories": query_row.get("matched_categories", ""),
                "best_query_top_pigean_labels": query_row.get("top_pigean_labels", ""),
                "best_query_top_eaggl_labels": query_row.get("top_eaggl_labels", ""),
                "best_query_top_factor_labels": query_row.get("top_factor_labels", ""),
                "top_categories": row.get("top_categories", ""),
                "selection_basis": format_top_reason(row),
                "represented_group_note": represented_note,
            }
        )
        md_lines.extend(
            [
                f"### Rank {rank}: `{model_id}`",
                "",
                f"- Score summary: total `{row.get('total_score', 'NA')}`, mean `{row.get('mean_score', 'NA')}`, strong queries `{row.get('num_strong_queries', 'NA')}` of `{row.get('num_queries', 'NA')}`",
                f"- Why it ranked here: {format_top_reason(row)}",
                f"- Represented group: `{cluster_id}`" if cluster_id else "- Represented group: unique model",
                f"- Group members: `{group_models}`",
                f"- Representative model: `{representative_model}`",
                f"- Representative reason: {representative_reason}",
                f"- Representative definition: {representative_definition or 'definition unavailable'}",
                f"- Best query matched categories: `{query_row.get('matched_categories', '') or row.get('top_categories', '')}`",
                f"- Best query top PIGEAN labels: `{query_row.get('top_pigean_labels', '')}`" if query_row.get("top_pigean_labels") else "- Best query top PIGEAN labels: unavailable",
                f"- Best query top EAGGL labels: `{query_row.get('top_eaggl_labels', '')}`" if query_row.get("top_eaggl_labels") else "- Best query top EAGGL labels: unavailable",
                "",
            ]
        )
    if represented_groups:
        md_lines.extend(["### Represented Model Groups", ""] + represented_groups + [""])
    return report_rows, "\n".join(md_lines)


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(__file__).resolve().parents[3]
    pigean_root = Path(args.pigean_root).resolve()
    genesets_root = Path(args.genesets_root).resolve()
    planning_root = Path(args.planning_root).resolve()
    out_dir = Path(args.out_dir).resolve() if args.out_dir else (pigean_root / "runs" / args.tissue)
    model_groups = [item.strip() for item in args.model_groups.split(",") if item.strip()]

    if not model_groups:
        raise SystemExit("No model_groups requested")

    definition_maps = {
        "models": parse_model_catalog(planning_root / "gtex_model_step1" / "model_catalog.md"),
        "tissue_models": load_manifest_definitions(planning_root / "gtex_tissue_model_step1" / "model_manifest.tsv"),
    }

    group_paths = {
        "models": genesets_root / args.tissue / "identical_model_check" / "identical_model_groups.tsv",
        "tissue_models": genesets_root / args.tissue / "tissue_identical_model_check" / "identical_model_groups.tsv",
    }
    model_summary_paths = {
        "models": pigean_root / "runs" / args.tissue / "comparison_models_biology_model_summary.tsv.gz",
        "tissue_models": pigean_root / "runs" / args.tissue / "tissue_models_biology_model_summary.tsv.gz",
    }
    query_summary_paths = {
        "models": pigean_root / "runs" / args.tissue / "comparison_models_biology_query_summary.tsv.gz",
        "tissue_models": pigean_root / "runs" / args.tissue / "tissue_models_biology_query_summary.tsv.gz",
    }

    fieldnames = [
        "model_group",
        "rank",
        "model_id",
        "cluster_id",
        "group_models",
        "representative_model",
        "representative_reason",
        "representative_definition",
        "total_score",
        "mean_score",
        "num_queries",
        "num_strong_queries",
        "num_partial_queries",
        "num_weak_queries",
        "best_query_name",
        "best_query_score",
        "best_query_call",
        "best_query_reason",
        "best_query_direction",
        "best_query_matched_categories",
        "best_query_top_pigean_labels",
        "best_query_top_eaggl_labels",
        "best_query_top_factor_labels",
        "top_categories",
        "selection_basis",
        "represented_group_note",
    ]

    all_rows: list[dict[str, object]] = []
    md_lines = [
        "# Top GTEx Models Summary",
        "",
        f"- tissue: `{args.tissue}`",
        f"- model_groups: `{','.join(model_groups)}`",
        f"- top_n_per_group: `{args.top_n}`",
        "- ranking rule: `total_score` descending, then `num_strong_queries`, then `mean_score`, then `best_query_score`",
        "- biology score source: existing PIGEAN/EAGGL biology summaries from `summarize_pigean_eaggl_results.py`",
        "- identical-model groups source: existing `identical_model_groups.tsv` outputs",
        "",
    ]

    for model_group in model_groups:
        if model_group not in model_summary_paths:
            raise SystemExit(f"Unsupported model_group: {model_group}")
        model_summary_path = model_summary_paths[model_group]
        query_summary_path = query_summary_paths[model_group]
        group_path = group_paths[model_group]
        if not model_summary_path.exists():
            raise SystemExit(f"Missing biology model summary: {model_summary_path}")
        if not query_summary_path.exists():
            raise SystemExit(f"Missing biology query summary: {query_summary_path}")
        if not group_path.exists():
            raise SystemExit(f"Missing identical-model groups: {group_path}")
        summary_rows = load_tsv_gz(model_summary_path)
        query_rows = load_query_map(query_summary_path)
        group_map, _ = load_group_info(group_path)
        report_rows, md_text = summarize_group(
            model_group=model_group,
            summary_rows=summary_rows,
            query_rows=query_rows,
            group_map=group_map,
            definition_map=definition_maps.get(model_group, {}),
            top_n=args.top_n,
        )
        all_rows.extend(report_rows)
        md_lines.append(md_text)

    out_dir.mkdir(parents=True, exist_ok=True)
    write_tsv_gz(out_dir / f"{args.output_prefix}_summary.tsv.gz", all_rows, fieldnames)
    write_text(out_dir / f"{args.output_prefix}_summary.md", "\n".join(md_lines).rstrip() + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
