from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models_root", required=True)
    parser.add_argument("--out_dir", required=True)
    parser.add_argument("--model_manifest")
    return parser.parse_args()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def model_sort_key(model_id: str) -> tuple[int, str]:
    digits = "".join(ch for ch in model_id if ch.isdigit())
    if digits:
        return (int(digits), model_id)
    return (10**9, model_id)


def read_model_manifest(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return {str(row.get("model_id", "")).strip(): {str(k): str(v) for k, v in row.items()} for row in reader}


def representative_model_key(model_id: str, manifest_row: dict[str, str] | None) -> tuple[int, ... | str]:
    row = manifest_row or {}
    proposal_rank = {
        "anchor": 0,
        "defensible_alternative": 1,
        "parameter_sweep": 2,
    }.get(row.get("family", ""), 3)
    complexity = 0
    if row.get("workflow_backend") not in {"", "auto"}:
        complexity += 2
    if row.get("annotation_mode") not in {"", "gct_symbols_only"}:
        complexity += 2
    if row.get("workflow_gene_filter_scope") not in {"", "contrast"}:
        complexity += 1
    if row.get("workflow_balance_groups") not in {"", "false"}:
        complexity += 1
    if row.get("extractor_postprocess_mode") not in {"", "harmonizome"}:
        complexity += 1
    if row.get("extractor_score_mode") not in {"", "auto"}:
        complexity += 1
    if row.get("extractor_select") not in {"", "top_k"}:
        complexity += 1
    if row.get("extractor_disable_default_excludes") not in {"", "false"}:
        complexity += 1
    if row.get("extractor_emit_small_gene_sets") not in {"", "false"}:
        complexity += 1
    if row.get("extractor_gmt_source") not in {"", "full"}:
        complexity += 1
    if row.get("extractor_gmt_biotype_allowlist") not in {"", "protein_coding"}:
        complexity += 1
    for field_name in (
        "extractor_padj_max",
        "extractor_pvalue_max",
        "extractor_min_abs_logfc",
        "extractor_top_k",
        "extractor_min_score",
        "extractor_gmt_topk_list",
        "extractor_gmt_min_genes",
        "extractor_gmt_max_genes",
    ):
        if row.get(field_name) not in {"", "NA"}:
            complexity += 1
    return (proposal_rank, complexity, *model_sort_key(model_id))


def representative_reason(model_id: str, manifest_row: dict[str, str] | None) -> str:
    row = manifest_row or {}
    reasons: list[str] = []
    family = row.get("family", "")
    if family == "anchor":
        reasons.append("anchor model")
    elif family == "defensible_alternative":
        reasons.append("defensible alternative")
    elif family == "parameter_sweep":
        reasons.append("parameter sweep")
    if row.get("workflow_backend") in {"", "auto"}:
        reasons.append("auto backend")
    else:
        reasons.append(f"forced backend={row.get('workflow_backend')}")
    if row.get("annotation_mode") == "gct_symbols_only":
        reasons.append("standard gct_symbols_only annotation")
    elif row.get("annotation_mode"):
        reasons.append(f"annotation_mode={row.get('annotation_mode')}")
    if row.get("extractor_postprocess_mode") == "harmonizome" and row.get("extractor_score_mode") == "auto":
        reasons.append("canonical harmonizome-style extractor defaults")
    elif row.get("extractor_postprocess_mode") or row.get("extractor_score_mode"):
        reasons.append(
            f"extractor={row.get('extractor_postprocess_mode', '')}/{row.get('extractor_score_mode', '')}".strip("/")
        )
    if row.get("workflow_balance_groups") == "false":
        reasons.append("no balancing")
    elif row.get("workflow_balance_groups") == "true":
        reasons.append("balanced groups")
    return "; ".join(reasons) if reasons else "lowest-complexity manifest profile"


def write_tsv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_reports(
    models_root: Path,
    *,
    model_manifest: dict[str, dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    geneset_rows: list[dict[str, str]] = []
    by_geneset_hash: dict[str, list[tuple[str, str]]] = defaultdict(list)

    for model_dir in sorted(path for path in models_root.iterdir() if path.is_dir()):
        extractor_dir = model_dir / "extractor"
        if not extractor_dir.exists():
            continue
        for comparison_dir in sorted(path for path in extractor_dir.iterdir() if path.is_dir() and path.name.startswith("age")):
            geneset_path = comparison_dir / "geneset.tsv"
            if not geneset_path.exists():
                continue
            geneset_hash = sha256_path(geneset_path)
            by_geneset_hash[geneset_hash].append((model_dir.name, comparison_dir.name))

    duplicate_geneset_rows: list[dict[str, str]] = []
    cluster_id = 0
    for geneset_hash, members in sorted(by_geneset_hash.items(), key=lambda item: (-len(item[1]), item[1])):
        if len(members) < 2:
            continue
        cluster_id += 1
        cluster_label = f"GS{cluster_id}"
        member_pairs = [f"{model_id}/{comparison}" for model_id, comparison in members]
        for model_id, comparison in members:
            duplicate_geneset_rows.append(
                {
                    "cluster_id": cluster_label,
                    "cluster_size": str(len(members)),
                    "comparison": comparison,
                    "model_id": model_id,
                    "geneset_sha256": geneset_hash,
                    "cluster_members": ",".join(member_pairs),
                }
            )

    model_signature_members: dict[tuple[tuple[str, str], ...], list[str]] = defaultdict(list)
    for model_dir in sorted(path for path in models_root.iterdir() if path.is_dir()):
        extractor_dir = model_dir / "extractor"
        signature_parts: list[tuple[str, str]] = []
        for comparison_dir in sorted(path for path in extractor_dir.iterdir() if path.is_dir() and path.name.startswith("age")):
            geneset_path = comparison_dir / "geneset.tsv"
            if not geneset_path.exists():
                continue
            signature_parts.append((comparison_dir.name, sha256_path(geneset_path)))
        if signature_parts:
            model_signature_members[tuple(signature_parts)].append(model_dir.name)

    duplicate_model_rows: list[dict[str, str]] = []
    cluster_id = 0
    for signature, model_ids in sorted(model_signature_members.items(), key=lambda item: (-len(item[1]), item[1])):
        if len(model_ids) < 2:
            continue
        cluster_id += 1
        cluster_label = f"MG{cluster_id}"
        comparisons = [comparison for comparison, _ in signature]
        signature_digest = hashlib.sha256(
            "\n".join(f"{comparison}\t{geneset_hash}" for comparison, geneset_hash in signature).encode("utf-8")
        ).hexdigest()
        sorted_model_ids = sorted(model_ids, key=lambda model_id: representative_model_key(model_id, model_manifest.get(model_id)))
        representative_id = sorted_model_ids[0]
        duplicate_model_rows.append(
            {
                "cluster_id": cluster_label,
                "cluster_size": str(len(model_ids)),
                "representative_model": representative_id,
                "representative_reason": representative_reason(representative_id, model_manifest.get(representative_id)),
                "models": ",".join(sorted_model_ids),
                "comparisons": ",".join(comparisons),
                "comparison_count": str(len(comparisons)),
                "signature_sha256": signature_digest,
            }
        )

    return duplicate_geneset_rows, duplicate_model_rows


def write_summary(
    path: Path,
    *,
    models_root: Path,
    duplicate_geneset_rows: list[dict[str, str]],
    duplicate_model_rows: list[dict[str, str]],
) -> None:
    total_duplicate_genesets = len(duplicate_geneset_rows)
    total_duplicate_clusters = len({row["cluster_id"] for row in duplicate_geneset_rows})
    lines = [
        "# Identical GTEx Model Report",
        "",
        f"- models_root: `{models_root}`",
        f"- duplicate comparison-level clusters: `{total_duplicate_clusters}`",
        f"- duplicate comparison-level memberships: `{total_duplicate_genesets}`",
        f"- duplicate model-level clusters: `{len(duplicate_model_rows)}`",
        "",
        "## Model-Level Duplicate Clusters",
        "",
    ]
    if not duplicate_model_rows:
        lines.append("No model-level duplicate clusters were detected.")
    else:
        for row in duplicate_model_rows:
            lines.append(
                f"- `{row['cluster_id']}`: representative `{row['representative_model']}` "
                f"({row['representative_reason']}) for `{row['models']}` "
                f"across `{row['comparison_count']}` comparisons "
                f"({row['comparisons']})"
            )
    lines.extend(["", "## Comparison-Level Duplicate Clusters", ""])
    if not duplicate_geneset_rows:
        lines.append("No comparison-level duplicate clusters were detected.")
    else:
        seen_clusters: set[str] = set()
        for row in duplicate_geneset_rows:
            cluster_id = row["cluster_id"]
            if cluster_id in seen_clusters:
                continue
            seen_clusters.add(cluster_id)
            lines.append(
                f"- `{cluster_id}`: comparison `{row['comparison']}` with `{row['cluster_size']}` identical members: "
                f"`{row['cluster_members']}`"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    args = parse_args()
    models_root = Path(args.models_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    model_manifest = read_model_manifest(Path(args.model_manifest) if args.model_manifest else None)

    duplicate_geneset_rows, duplicate_model_rows = build_reports(models_root, model_manifest=model_manifest)

    geneset_tsv = out_dir / "identical_genesets.tsv"
    write_tsv(
        geneset_tsv,
        duplicate_geneset_rows,
        [
            "cluster_id",
            "cluster_size",
            "comparison",
            "model_id",
            "geneset_sha256",
            "cluster_members",
        ],
    )

    models_tsv = out_dir / "identical_model_groups.tsv"
    write_tsv(
        models_tsv,
        duplicate_model_rows,
        [
            "cluster_id",
            "cluster_size",
            "representative_model",
            "representative_reason",
            "models",
            "comparisons",
            "comparison_count",
            "signature_sha256",
        ],
    )

    write_summary(
        out_dir / "identical_model_report.md",
        models_root=models_root,
        duplicate_geneset_rows=duplicate_geneset_rows,
        duplicate_model_rows=duplicate_model_rows,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
