#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sanitize_path_component(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._=-]+", "_", value.strip())


def split_query_name(query_name: str) -> tuple[str, str, str]:
    parts = query_name.split("__")
    if len(parts) != 3:
        raise ValueError(f"unexpected query name format: {query_name}")
    return parts[0], parts[1], parts[2]


@dataclass
class QueryRecord:
    tissue_id: str
    model_id: str
    query_name: str
    comparison: str
    direction: str
    genes: list[str]
    model_group: str

    @property
    def query_slug(self) -> str:
        return sanitize_path_component(f"{self.comparison}__{self.direction}")

    @property
    def gene_count(self) -> int:
        return len(self.genes)


def build_parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parents[3]
    gtex_root = repo_root / "geneset-extractor-dev" / "GTEx"
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--outputs_root",
        default=str(gtex_root / "outputs" / "genesets"),
        help="GTEx gene-set outputs root to scan for tissue directories containing a unified models/ directory",
    )
    parser.add_argument(
        "--out_dir",
        default=str(gtex_root / "outputs" / "pigean_eaggl"),
        help="aggregate GTEx output directory for all PIGEAN/EAGGL run artifacts",
    )
    parser.add_argument(
        "--python_bin",
        default=sys.executable,
    )
    parser.add_argument(
        "--pigean_src",
        default=str(repo_root / "pigean" / "src"),
    )
    parser.add_argument(
        "--bundle_data_dir",
        default=str(repo_root / "pigean" / "bundles" / "model_small-2026.02.22" / "data"),
    )
    parser.add_argument(
        "--pigean_mode",
        choices=["betas", "gibbs"],
        default="betas",
    )
    parser.add_argument(
        "--tissues",
        default=None,
        help="optional comma-separated tissue directory names under GTEx/outputs/genesets/",
    )
    parser.add_argument(
        "--models",
        default=None,
        help="optional comma-separated model IDs such as AB1,AB2 or AC1,AC2",
    )
    parser.add_argument(
        "--comparisons",
        default=None,
        help="optional comma-separated query labels such as age60_20,age70_20 or adipose_subcutaneous",
    )
    parser.add_argument(
        "--query_limit",
        type=int,
        default=None,
        help="optional limit on number of discovered queries to execute",
    )
    parser.add_argument(
        "--force_rerun",
        action="store_true",
        help="rerun queries even if they are already marked complete",
    )
    return parser


def parse_optional_csv(value: str | None) -> set[str] | None:
    if not value:
        return None
    parsed = {item.strip() for item in value.split(",") if item.strip()}
    return parsed or None


def discover_queries(
    outputs_root: Path,
    *,
    allowed_tissues: set[str] | None,
    allowed_models: set[str] | None,
    allowed_comparisons: set[str] | None,
) -> list[QueryRecord]:
    queries: list[QueryRecord] = []
    for tissue_dir in sorted(path for path in outputs_root.iterdir() if path.is_dir()):
        if tissue_dir.name.startswith("pigean_eaggl_"):
            continue
        if allowed_tissues is not None and tissue_dir.name not in allowed_tissues:
            continue
        models_dir = tissue_dir / "models"
        if not models_dir.is_dir():
            continue
        gmt_paths = sorted(models_dir.glob("AB*/extractor/genesets.gmt"))
        gmt_paths.extend(sorted(models_dir.glob("AC*/tissue_extractor/genesets.gmt")))
        gmt_paths.extend(sorted(models_dir.glob("CFDE*/extractor/genesets.gmt")))
        gmt_paths.extend(sorted(models_dir.glob("TV*/tissue_extractor/genesets.gmt")))
        for gmt_path in gmt_paths:
            model_id = gmt_path.parent.parent.name
            if model_id.startswith("AB"):
                model_group = "age_binned"
            elif model_id.startswith("AC"):
                model_group = "continuous_age"
            elif model_id.startswith("CFDE"):
                model_group = "cfde_notebook"
            elif model_id.startswith("TV"):
                model_group = "tissue_versus"
            else:
                continue
            if allowed_models is not None and model_id not in allowed_models:
                continue
            with gmt_path.open(encoding="utf-8") as input_fh:
                for raw_line in input_fh:
                    line = raw_line.strip()
                    if not line:
                        continue
                    query_name, genes_blob = line.split("\t", 1)
                    _, comparison, direction = split_query_name(query_name)
                    if allowed_comparisons is not None and comparison not in allowed_comparisons:
                        continue
                    genes = [gene for gene in genes_blob.split() if gene]
                    queries.append(
                        QueryRecord(
                            tissue_id=tissue_dir.name,
                            model_id=model_id,
                            query_name=query_name,
                            comparison=comparison,
                            direction=direction,
                            genes=genes,
                            model_group=model_group,
                        )
                    )
    return queries


def write_gene_list(path: Path, genes: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as output_fh:
        output_fh.write("gene_symbol\n")
        for gene in genes:
            output_fh.write(f"{gene}\n")


def write_json(path: Path, payload: dict[str, object]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as output_fh:
        json.dump(payload, output_fh, indent=2, sort_keys=True)
        output_fh.write("\n")


def run_command(command: list[str], *, env: dict[str, str], log_path: Path) -> int:
    with log_path.open("w", encoding="utf-8", newline="\n") as log_fh:
        log_fh.write("$ " + " ".join(command) + "\n\n")
        log_fh.flush()
        result = subprocess.run(
            command,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            env=env,
            check=False,
            text=True,
        )
    return int(result.returncode)


def expected_complete_outputs(query_dir: Path) -> list[Path]:
    return [
        query_dir / "pigean.gene_stats.out",
        query_dir / "pigean.gene_set_stats.out",
        query_dir / "pigean.params.out",
        query_dir / "eaggl.params.out",
    ]


def load_existing_status(status_path: Path) -> dict[str, object] | None:
    if not status_path.exists():
        return None
    with status_path.open(encoding="utf-8") as input_fh:
        return json.load(input_fh)


def is_complete_status(status_payload: dict[str, object] | None, query_dir: Path) -> bool:
    if not status_payload:
        return False
    if status_payload.get("status") != "complete":
        return False
    return all(path.exists() for path in expected_complete_outputs(query_dir))


def query_dir_for(out_dir: Path, query: QueryRecord) -> Path:
    if query.model_group not in {"age_binned", "continuous_age", "cfde_notebook", "tissue_versus"}:
        raise ValueError(f"unexpected model_group: {query.model_group}")
    return out_dir / "runs" / query.tissue_id / "models" / query.model_id / query.query_slug


def build_pigean_command(
    query_dir: Path,
    query: QueryRecord,
    *,
    python_bin: str,
    bundle_data_dir: Path,
    pigean_mode: str,
) -> list[str]:
    command = [
        python_bin,
        "-m",
        "pigean",
        pigean_mode,
        "--X-in",
        str(bundle_data_dir / "gene_set_list_mouse_2024.txt"),
        "--X-in",
        str(bundle_data_dir / "gene_set_list_msigdb_nohp.txt"),
        "--gene-map-in",
        str(bundle_data_dir / "portal_gencode.gene.map"),
        "--gene-loc-file",
        str(bundle_data_dir / "NCBI37.3.plink.gene.loc"),
        "--gene-loc-file-huge",
        str(bundle_data_dir / "NCBI37.3.plink.gene.exons.loc"),
        "--gene-list-in",
        str(query_dir / "gene_list.tsv"),
        "--gene-list-id-col",
        "gene_symbol",
        "--gene-universe-in",
        str(bundle_data_dir / "NCBI37.3.plink.gene.loc"),
        "--gene-universe-id-col",
        "6",
        "--gene-universe-no-header",
        "--gene-stats-out",
        str(query_dir / "pigean.gene_stats.out"),
        "--gene-set-stats-out",
        str(query_dir / "pigean.gene_set_stats.out"),
        "--params-out",
        str(query_dir / "pigean.params.out"),
        "--deterministic",
    ]
    if pigean_mode == "gibbs":
        command.extend(["--num-chains", "1", "--max-num-restarts", "0"])
    return command


def build_eaggl_command(
    query_dir: Path,
    *,
    python_bin: str,
    bundle_data_dir: Path,
) -> list[str]:
    return [
        python_bin,
        "-m",
        "eaggl",
        "factor",
        "--X-in",
        str(bundle_data_dir / "gene_set_list_mouse_2024.txt"),
        "--X-in",
        str(bundle_data_dir / "gene_set_list_msigdb_nohp.txt"),
        "--gene-list-in",
        str(query_dir / "gene_list.tsv"),
        "--gene-list-id-col",
        "gene_symbol",
        "--factors-out",
        str(query_dir / "eaggl.factors.out"),
        "--gene-set-clusters-out",
        str(query_dir / "eaggl.gene_set_clusters.out"),
        "--gene-clusters-out",
        str(query_dir / "eaggl.gene_clusters.out"),
        "--gene-set-stats-out",
        str(query_dir / "eaggl.gene_set_stats.out"),
        "--gene-stats-out",
        str(query_dir / "eaggl.gene_stats.out"),
        "--params-out",
        str(query_dir / "eaggl.params.out"),
        "--deterministic",
        "--factor-runs",
        "1",
        "--gene-filter-value",
        "0",
        "--gene-set-filter-value",
        "0",
        "--min-gene-set-size",
        "1",
    ]


def write_query_commands(query_dir: Path, pigean_command: list[str], eaggl_command: list[str]) -> None:
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        " ".join(pigean_command),
        " ".join(eaggl_command),
        "",
    ]
    (query_dir / "commands.sh").write_text("\n".join(lines), encoding="utf-8")


def execute_query(
    query: QueryRecord,
    *,
    out_dir: Path,
    env: dict[str, str],
    python_bin: str,
    bundle_data_dir: Path,
    pigean_mode: str,
    force_rerun: bool,
) -> dict[str, object]:
    query_dir = query_dir_for(out_dir, query)
    query_dir.mkdir(parents=True, exist_ok=True)
    status_path = query_dir / "query_status.json"
    existing_status = load_existing_status(status_path)
    if not force_rerun and is_complete_status(existing_status, query_dir):
        status_payload = dict(existing_status)
        status_payload["skipped_existing"] = True
        return status_payload

    write_gene_list(query_dir / "gene_list.tsv", query.genes)
    pigean_command = build_pigean_command(
        query_dir,
        query,
        python_bin=python_bin,
        bundle_data_dir=bundle_data_dir,
        pigean_mode=pigean_mode,
    )
    eaggl_command = build_eaggl_command(
        query_dir,
        python_bin=python_bin,
        bundle_data_dir=bundle_data_dir,
    )
    write_query_commands(query_dir, pigean_command, eaggl_command)

    status_payload: dict[str, object] = {
        **asdict(query),
        "query_slug": query.query_slug,
        "gene_count": query.gene_count,
        "query_dir": str(query_dir),
        "pigean_mode": pigean_mode,
        "status": "running",
        "started_at": utc_now(),
        "completed_at": None,
        "pigean_return_code": None,
        "eaggl_return_code": None,
        "skipped_existing": False,
        "error_step": None,
        "error_message": None,
    }
    write_json(status_path, status_payload)

    pigean_return_code = run_command(pigean_command, env=env, log_path=query_dir / "pigean.log")
    status_payload["pigean_return_code"] = pigean_return_code
    if pigean_return_code != 0:
        status_payload["status"] = "failed"
        status_payload["completed_at"] = utc_now()
        status_payload["error_step"] = "pigean"
        status_payload["error_message"] = f"pigean returned {pigean_return_code}"
        write_json(status_path, status_payload)
        return status_payload

    eaggl_return_code = run_command(eaggl_command, env=env, log_path=query_dir / "eaggl.log")
    status_payload["eaggl_return_code"] = eaggl_return_code
    status_payload["completed_at"] = utc_now()
    if eaggl_return_code != 0:
        status_payload["status"] = "failed"
        status_payload["error_step"] = "eaggl"
        status_payload["error_message"] = f"eaggl returned {eaggl_return_code}"
    else:
        status_payload["status"] = "complete"
    write_json(status_path, status_payload)
    return status_payload


def write_tsv_gz(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with gzip.open(path, "wt", encoding="utf-8", newline="\n") as output_fh:
        writer = csv.DictWriter(output_fh, delimiter="\t", fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def format_command(command: list[str]) -> str:
    return " ".join(subprocess.list2cmdline([part]) if " " in part else part for part in command)


def main() -> int:
    args = build_parser().parse_args()

    outputs_root = Path(args.outputs_root).resolve()
    out_dir = Path(args.out_dir).resolve()
    bundle_data_dir = Path(args.bundle_data_dir).resolve()
    pigean_src = Path(args.pigean_src).resolve()
    python_bin = str(Path(args.python_bin).resolve())
    allowed_tissues = parse_optional_csv(args.tissues)
    allowed_models = parse_optional_csv(args.models)
    allowed_comparisons = parse_optional_csv(args.comparisons)

    out_dir.mkdir(parents=True, exist_ok=True)

    queries = discover_queries(
        outputs_root,
        allowed_tissues=allowed_tissues,
        allowed_models=allowed_models,
        allowed_comparisons=allowed_comparisons,
    )
    if args.query_limit is not None:
        queries = queries[: args.query_limit]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(pigean_src)

    status_rows: list[dict[str, object]] = []
    for query in queries:
        status_rows.append(
            execute_query(
                query,
                out_dir=out_dir,
                env=env,
                python_bin=python_bin,
                bundle_data_dir=bundle_data_dir,
                pigean_mode=args.pigean_mode,
                force_rerun=args.force_rerun,
            )
        )

    aggregate_dir = out_dir
    aggregate_dir.mkdir(parents=True, exist_ok=True)
    complete_count = sum(1 for row in status_rows if row.get("status") == "complete")
    failed_count = sum(1 for row in status_rows if row.get("status") == "failed")
    skipped_count = sum(1 for row in status_rows if row.get("skipped_existing") is True)
    running_count = sum(1 for row in status_rows if row.get("status") == "running")

    manifest = {
        "outputs_root": str(outputs_root),
        "out_dir": str(aggregate_dir),
        "python_bin": python_bin,
        "pigean_src": str(pigean_src),
        "bundle_data_dir": str(bundle_data_dir),
        "pigean_mode": args.pigean_mode,
        "tissues": sorted(allowed_tissues) if allowed_tissues is not None else None,
        "models": sorted(allowed_models) if allowed_models is not None else None,
        "comparisons": sorted(allowed_comparisons) if allowed_comparisons is not None else None,
        "query_limit": args.query_limit,
        "force_rerun": bool(args.force_rerun),
        "num_queries_discovered": len(queries),
        "num_complete": complete_count,
        "num_failed": failed_count,
        "num_skipped_existing": skipped_count,
        "num_running": running_count,
        "updated_at": utc_now(),
    }
    write_json(aggregate_dir / "run_manifest.json", manifest)

    fieldnames = [
        "tissue_id",
        "model_id",
        "query_name",
        "comparison",
        "direction",
        "model_group",
        "query_slug",
        "gene_count",
        "query_dir",
        "pigean_mode",
        "status",
        "started_at",
        "completed_at",
        "pigean_return_code",
        "eaggl_return_code",
        "skipped_existing",
        "error_step",
        "error_message",
    ]
    write_tsv_gz(aggregate_dir / "query_status.tsv.gz", status_rows, fieldnames)

    commands_lines = [
        "# PIGEAN EAGGL Run Commands",
        "",
        "Top-level command:",
        "```bash",
        format_command([python_bin, str(Path(__file__).resolve())] + sys.argv[1:]),
        "```",
        "",
        "Each query directory under `runs/` contains a `commands.sh`, `pigean.log`, `eaggl.log`, and `query_status.json`.",
    ]
    (aggregate_dir / "commands.md").write_text("\n".join(commands_lines) + "\n", encoding="utf-8")

    summary_lines = [
        "# PIGEAN EAGGL Run Summary",
        "",
        "This workflow only runs PIGEAN and EAGGL on discovered GTEx model/tissue gene lists.",
        "It does not perform any downstream biological relevance scoring or interpretation.",
        "",
        f"- queries discovered: {len(queries)}",
        f"- complete: {complete_count}",
        f"- failed: {failed_count}",
        f"- skipped_existing: {skipped_count}",
        f"- still marked running: {running_count}",
        f"- PIGEAN mode: `{args.pigean_mode}`",
    ]
    (aggregate_dir / "run_summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    output_manifest_lines = [
        "# Output Manifest",
        "",
        "- `query_status.tsv.gz`: per-query execution status and return codes",
        "- `run_manifest.json`: resolved settings and aggregate counts",
        "- `run_summary.md`: execution-only summary",
        "- `commands.md`: top-level invocation",
        "- `runs/`: per-tissue, per-model-group, per-model, per-query inputs, logs, commands, and raw PIGEAN/EAGGL outputs",
    ]
    (aggregate_dir / "output_manifest.md").write_text("\n".join(output_manifest_lines) + "\n", encoding="utf-8")

    return 1 if failed_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
