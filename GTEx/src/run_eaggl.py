#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

from run_model_enrichment import (
    QueryRecord,
    build_eaggl_command,
    discover_queries,
    load_existing_status,
    parse_optional_csv,
    query_dir_for,
    run_command,
    utc_now,
    write_gene_list,
)
from selection_io import (
    default_model_list_path,
    default_out_root,
    default_tissue_list_path,
    load_model_rows,
    load_tissue_rows,
    repo_root,
    resolve_requested_ids,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="all")
    parser.add_argument("--models_file")
    parser.add_argument("--tissues", default="all")
    parser.add_argument("--tissues_file")
    parser.add_argument("--model_list", default=str(default_model_list_path()))
    parser.add_argument("--tissue_list", default=str(default_tissue_list_path()))
    parser.add_argument("--out_root", default=str(default_out_root()))
    parser.add_argument("--outputs_root")
    parser.add_argument("--out_dir")
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument("--pigean_src", required=True)
    parser.add_argument("--bundle_data_dir", required=True)
    parser.add_argument("--comparisons", default=None)
    parser.add_argument("--query_limit", type=int, default=None)
    parser.add_argument("--force_rerun", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def write_tsv_gz(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with gzip.open(path, "wt", encoding="utf-8", newline="\n") as output_fh:
        writer = csv.DictWriter(output_fh, delimiter="\t", fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_unified_query_status(out_dir: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = [
        "tissue_id", "model_id", "query_name", "comparison", "direction", "model_group",
        "query_slug", "gene_count", "query_dir", "status", "started_at", "completed_at",
        "pigean_return_code", "eaggl_return_code", "skipped_existing", "error_step", "error_message",
    ]
    write_tsv_gz(out_dir / "query_status.tsv.gz", rows, fieldnames)


def dir_nonempty(path: Path) -> bool:
    return path.exists() and path.is_dir() and any(path.iterdir())


def existing_query_output_message(query: QueryRecord, query_dir: Path) -> str:
    return (
        "Output already exists for "
        f"tissue={query.tissue_id} model={query.model_id} comparison={query.comparison} direction={query.direction}:\n"
        f"{query_dir}\n\n"
        "Refusing to continue because --overwrite was not provided.\n"
        "Re-run with --overwrite to replace this output."
    )


def execute_eaggl(
    query: QueryRecord,
    *,
    out_dir: Path,
    env: dict[str, str],
    python_bin: str,
    bundle_data_dir: Path,
    force_rerun: bool,
    overwrite: bool,
) -> dict[str, object]:
    query_dir = query_dir_for(out_dir, query)
    if overwrite and query_dir.exists():
        shutil.rmtree(query_dir)
    query_dir.mkdir(parents=True, exist_ok=True)
    status_path = query_dir / "eaggl_status.json"
    existing_status = load_existing_status(status_path)
    expected_outputs = [
        query_dir / "eaggl.factors.out",
        query_dir / "eaggl.gene_set_clusters.out",
        query_dir / "eaggl.gene_clusters.out",
        query_dir / "eaggl.gene_set_stats.out",
        query_dir / "eaggl.gene_stats.out",
        query_dir / "eaggl.params.out",
    ]
    if (
        not force_rerun
        and existing_status
        and existing_status.get("status") == "complete"
        and all(path.exists() for path in expected_outputs)
    ):
        status_payload = dict(existing_status)
        status_payload["skipped_existing"] = True
        return status_payload
    if not (query_dir / "gene_list.tsv").exists():
        write_gene_list(query_dir / "gene_list.tsv", query.genes)
    eaggl_command = build_eaggl_command(query_dir, python_bin=python_bin, bundle_data_dir=bundle_data_dir)
    (query_dir / "commands.eaggl.sh").write_text("#!/usr/bin/env bash\nset -euo pipefail\n\n" + " ".join(eaggl_command) + "\n", encoding="utf-8", newline="\n")
    pigean_status = load_existing_status(query_dir / "pigean_status.json") or {}
    status_payload: dict[str, object] = {
        **asdict(query),
        "query_slug": query.query_slug,
        "gene_count": query.gene_count,
        "query_dir": str(query_dir),
        "status": "running",
        "started_at": utc_now(),
        "completed_at": None,
        "pigean_return_code": pigean_status.get("pigean_return_code"),
        "eaggl_return_code": None,
        "skipped_existing": False,
        "error_step": None,
        "error_message": None,
    }
    write_json(status_path, status_payload)
    return_code = run_command(eaggl_command, env=env, log_path=query_dir / "eaggl.log")
    status_payload["eaggl_return_code"] = return_code
    status_payload["completed_at"] = utc_now()
    if return_code != 0:
        status_payload["status"] = "failed"
        status_payload["error_step"] = "eaggl"
        status_payload["error_message"] = f"eaggl returned {return_code}"
    else:
        status_payload["status"] = "complete"
    write_json(status_path, status_payload)
    return status_payload


def main() -> int:
    args = build_parser().parse_args()
    model_rows = load_model_rows(Path(args.model_list))
    tissue_rows = load_tissue_rows(Path(args.tissue_list))
    selected_models = resolve_requested_ids(csv_text=args.models, file_path=args.models_file, rows=model_rows, key_field="model_id")
    selected_tissues = resolve_requested_ids(csv_text=args.tissues, file_path=args.tissues_file, rows=tissue_rows, key_field="tissue_id")
    out_root = Path(args.out_root).resolve()
    outputs_root = Path(args.outputs_root).resolve() if args.outputs_root else (out_root / "genesets")
    out_dir = Path(args.out_dir).resolve() if args.out_dir else (out_root / "pigean_eaggl")
    bundle_data_dir = Path(args.bundle_data_dir).resolve()
    pigean_src = Path(args.pigean_src).resolve()
    if not pigean_src.exists():
        raise SystemExit(f"Missing pigean src directory: {pigean_src}")
    if not pigean_src.is_dir():
        raise SystemExit(f"Expected pigean src path to be a directory: {pigean_src}")
    if not bundle_data_dir.exists():
        raise SystemExit(f"Missing bundle data directory: {bundle_data_dir}")
    if not bundle_data_dir.is_dir():
        raise SystemExit(f"Expected bundle data path to be a directory: {bundle_data_dir}")
    allowed_comparisons = parse_optional_csv(args.comparisons)
    out_dir.mkdir(parents=True, exist_ok=True)

    queries = discover_queries(
        outputs_root,
        allowed_tissues=set(selected_tissues),
        allowed_models=set(selected_models),
        allowed_comparisons=allowed_comparisons,
    )
    if args.query_limit is not None:
        queries = queries[: args.query_limit]
    if not args.overwrite:
        conflicts = [
            existing_query_output_message(query, query_dir_for(out_dir, query))
            for query in queries
            if dir_nonempty(query_dir_for(out_dir, query))
        ]
        if conflicts:
            raise SystemExit("\n\n".join(conflicts))

    env = os.environ.copy()
    env["PYTHONPATH"] = str(pigean_src)
    python_bin = str(Path(args.python_bin).resolve())
    status_rows: list[dict[str, object]] = []
    for query in queries:
        status_rows.append(
            execute_eaggl(
                query,
                out_dir=out_dir,
                env=env,
                python_bin=python_bin,
                bundle_data_dir=bundle_data_dir,
                force_rerun=args.force_rerun,
                overwrite=args.overwrite,
            )
        )

    manifest = {
        "out_root": str(out_root),
        "outputs_root": str(outputs_root),
        "out_dir": str(out_dir),
        "stage": "eaggl",
        "python_bin": python_bin,
        "pigean_src": str(pigean_src),
        "bundle_data_dir": str(bundle_data_dir),
        "models": selected_models,
        "tissues": selected_tissues,
        "comparisons": sorted(allowed_comparisons) if allowed_comparisons is not None else None,
        "query_limit": args.query_limit,
        "force_rerun": bool(args.force_rerun),
        "num_queries": len(status_rows),
        "generated_at": utc_now(),
    }
    write_json(out_dir / "eaggl_run_manifest.json", manifest)
    fieldnames = [
        "tissue_id", "model_id", "query_name", "comparison", "direction", "model_group",
        "query_slug", "gene_count", "query_dir", "status", "started_at", "completed_at",
        "pigean_return_code", "eaggl_return_code", "skipped_existing", "error_step", "error_message",
    ]
    write_tsv_gz(out_dir / "eaggl_query_status.tsv.gz", status_rows, fieldnames)
    write_unified_query_status(out_dir, status_rows)
    (out_dir / "eaggl_run_summary.md").write_text(
        "\n".join(
            [
                "# EAGGL Run Summary",
                "",
                f"- queries: {len(status_rows)}",
                f"- complete: {sum(1 for row in status_rows if row.get('status') == 'complete')}",
                f"- failed: {sum(1 for row in status_rows if row.get('status') == 'failed')}",
                f"- skipped_existing: {sum(1 for row in status_rows if row.get('skipped_existing') is True)}",
            ]
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (out_dir / "eaggl_commands.md").write_text(
        "# EAGGL Commands\n\n```bash\n"
        + " ".join([python_bin, str(Path(__file__).resolve()), *sys.argv[1:]])
        + "\n```\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
