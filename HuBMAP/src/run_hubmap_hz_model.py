#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pandas as pd

from hubmap_selection_io import default_model_manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one HuBMAP HZ model and emit dig-authored GMT outputs in pipeline layout."
    )
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--run_root", required=True)
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument("--dig_dir", required=True)
    parser.add_argument("--raw_asctb_dir")
    parser.add_argument("--asctb_dir")
    parser.add_argument("--input_matrix")
    parser.add_argument("--human_gene_info", required=True)
    parser.add_argument("--model_manifest", default=str(default_model_manifest_path()))
    parser.add_argument("--provenance_mirror_local_prefix")
    parser.add_argument("--provenance_mirror_remote_prefix")
    parser.add_argument("--write_commands_only", action="store_true")
    return parser.parse_args()


def load_model_settings(manifest_path: Path) -> dict[str, dict[str, str]]:
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    settings: dict[str, dict[str, str]] = {}
    for row in rows:
        model_id = str(row.get("model_id", "")).strip()
        if model_id:
            settings[model_id] = {str(key): str(value) for key, value in row.items()}
    if not settings:
        raise SystemExit(f"No model settings found in {manifest_path}")
    return settings


def shell_join(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def log_line(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(text.rstrip("\n") + "\n")


def require_existing_file(path_text: str | None, label: str) -> Path:
    if not path_text:
        raise SystemExit(f"Missing required argument for {label}")
    path = Path(path_text).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"Missing {label}: {path}")
    if not path.is_file():
        raise SystemExit(f"Expected {label} to be a file: {path}")
    return path


def require_existing_dir(path_text: str | None, label: str) -> Path:
    if not path_text:
        raise SystemExit(f"Missing required argument for {label}")
    path = Path(path_text).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"Missing {label}: {path}")
    if not path.is_dir():
        raise SystemExit(f"Expected {label} to be a directory: {path}")
    return path


def manifest_value(settings: dict[str, str], key: str, default: str) -> str:
    value = str(settings.get(key, "")).strip()
    if not value or value == "NA":
        return default
    return value


def load_source_module(script_path: Path):
    spec = importlib.util.spec_from_file_location(script_path.stem, script_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Unable to load source script: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_tsv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def parse_gmt(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8", newline="") as handle:
        for line in handle:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 2:
                continue
            rows.append(
                {
                    "set_name": parts[0],
                    "description": parts[1] if len(parts) > 1 else "",
                    "gene_count": str(max(0, len(parts) - 2)),
                }
            )
    return rows


def write_manifest(
    *,
    manifest_path: Path,
    model_id: str,
    workflow_out: Path,
    extractor_out: Path,
    provenance_mirror_local_prefix: str | None,
    provenance_mirror_remote_prefix: str | None,
) -> None:
    payload = {
        "model_id": model_id,
        "workflow_dir": str(workflow_out),
        "tissue_extractor_dir": str(extractor_out),
        "provenance_mirror_local_prefix": provenance_mirror_local_prefix,
        "provenance_mirror_remote_prefix": provenance_mirror_remote_prefix,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def model_source_info(model_id: str) -> tuple[str, Path]:
    repo = Path(__file__).resolve().parents[3]
    if model_id == "HZ1":
        return ("asctb", repo / "notebooks_adapted" / "build_hubmap_asctb_gmt.py")
    if model_id == "HZ2":
        return ("asctb_augmented", repo / "notebooks_adapted" / "build_hubmap_asctb_augmented_gmt.py")
    raise SystemExit(f"Unsupported HuBMAP HZ model_id: {model_id}")


def build_workflow_cmd(
    *,
    python_bin: str,
    runner_script: Path,
    model_id: str,
    workflow_out: Path,
    human_gene_info: Path,
    raw_asctb_dir: Path | None,
    asctb_dir: Path | None,
    input_matrix: Path | None,
    settings: dict[str, str],
) -> list[str]:
    cmd = [
        python_bin,
        str(runner_script),
        "--output-dir",
        str(workflow_out),
        "--human-gene-info",
        str(human_gene_info),
    ]
    if model_id == "HZ1":
        if raw_asctb_dir is not None:
            cmd.extend(["--raw-asctb-dir", str(raw_asctb_dir)])
        resolved_asctb_dir = asctb_dir if asctb_dir is not None else (workflow_out / "ASCTB_Tables")
        cmd.extend(["--asctb-dir", str(resolved_asctb_dir)])
        cmd.extend(["--min-gmt-size", manifest_value(settings, "workflow_min_gmt_size", "5")])
    else:
        if input_matrix is None:
            raise SystemExit("HZ2 requires --input_matrix")
        cmd.extend(
            [
                "--input-matrix",
                str(input_matrix),
                "--gmt-min-size",
                manifest_value(settings, "workflow_min_gmt_size", "5"),
                "--augmentation-threshold",
                manifest_value(settings, "workflow_augmentation_threshold", "0.67"),
                "--cap-multiplier",
                manifest_value(settings, "workflow_cap_multiplier", "4"),
            ]
        )
        limit_terms = manifest_value(settings, "workflow_limit_terms", "NA")
        if limit_terms != "NA":
            cmd.extend(["--limit-terms", limit_terms])
    return cmd


def build_extractor_cmd(
    *,
    python_bin: str,
    unsigned_term_tsv: Path,
    extractor_out: Path,
    provenance_mirror_local_prefix: str | None,
    provenance_mirror_remote_prefix: str | None,
) -> list[str]:
    cmd = [
        python_bin,
        "-m",
        "geneset_extractors.cli",
        "convert",
        "unsigned_term_gene",
        "--table_tsv",
        str(unsigned_term_tsv),
        "--out_dir",
        str(extractor_out),
        "--organism",
        "human",
        "--genome_build",
        "hg38",
        "--term_column",
        "term",
        "--gene_id_column",
        "gene_id",
        "--gene_symbol_column",
        "gene_symbol",
        "--score_column",
        "score",
        "--gmt_min_genes",
        "5",
        "--gmt_require_symbol",
        "true",
        "--emit_small_gene_sets",
        "false",
    ]
    if provenance_mirror_local_prefix:
        cmd.extend(["--provenance_mirror_local_prefix", provenance_mirror_local_prefix])
    if provenance_mirror_remote_prefix:
        cmd.extend(["--provenance_mirror_remote_prefix", provenance_mirror_remote_prefix])
    return cmd


def run_command(cmd: list[str], *, cwd: Path, log_path: Path) -> None:
    log_line(log_path, f"$ {shell_join(cmd)}")
    completed = subprocess.run(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if completed.stdout:
        log_line(log_path, completed.stdout.rstrip("\n"))
    if completed.returncode != 0:
        raise subprocess.CalledProcessError(completed.returncode, cmd)


def write_model_commands(
    *,
    model_out: Path,
    model_id: str,
    workflow_cmd: list[str],
    extractor_cmd: list[str],
    dig_dir: Path,
) -> None:
    text = "\n".join(
        [
            f"# Commands For {model_id}",
            "",
            "## Workflow",
            "",
            "```bash",
            shell_join(workflow_cmd),
            "```",
            "",
            "## Extractor",
            "",
            "```bash",
            f"cd {shlex.quote(str(dig_dir))}",
            f"PYTHONPATH={shlex.quote(str(dig_dir / 'src'))} {shell_join(extractor_cmd)}",
            "```",
            "",
            "## Notes",
            "",
            "The authoritative GMT outputs are written by dig-gene-set-extractors from the processed notebook-style term-gene table.",
            "",
        ]
    )
    write_text(model_out / "commands.md", text)


def build_asctb_unsigned_table(workflow_out: Path) -> Path:
    edge_path = workflow_out / "gene_attribute_edges.txt.gz"
    if not edge_path.exists():
        raise SystemExit(f"Expected workflow edge table: {edge_path}")
    frame = pd.read_csv(edge_path, sep="\t", compression="infer")
    rows = [
        {
            "term": str(row["Cell Type"]),
            "gene_id": str(row["Gene"]),
            "gene_symbol": str(row["Gene"]),
            "score": "1",
        }
        for _, row in frame.iterrows()
    ]
    out_tsv = workflow_out / "hubmap_unsigned_term_gene.tsv"
    write_tsv(out_tsv, rows, ["term", "gene_id", "gene_symbol", "score"])
    return out_tsv


def build_augmented_unsigned_table(*, module, workflow_out: Path, input_matrix: Path, human_gene_info: Path, settings: dict[str, str]) -> Path:
    _raw_human_gene_info, human_gene_info_df = module.load_human_gene_info(human_gene_info)
    _matrix, asctb_full_gmt = module.load_base_matrix(input_matrix)
    asctb_augmented = module.build_or_load_geneshot_augmented(
        asctb_full_gmt=asctb_full_gmt,
        augmented_tsv=workflow_out / "asctb_geneshot_augmented_genes.tsv",
        geneshot_url=manifest_value(settings, "workflow_geneshot_url", module.GENESHOT_URL_DEFAULT),
        use_existing_augmented_tsv=True,
        force_query=False,
        limit_terms=(None if manifest_value(settings, "workflow_limit_terms", "NA") == "NA" else int(manifest_value(settings, "workflow_limit_terms", "NA"))),
        timeout=int(manifest_value(settings, "workflow_request_timeout", "120")),
        retries=int(manifest_value(settings, "workflow_request_retries", "2")),
        pause_seconds=float(manifest_value(settings, "workflow_pause_seconds", "0.1")),
    )
    asctb_augmented = asctb_augmented[asctb_augmented.index.isin(human_gene_info_df.index)]
    augmented_gmt = module.create_augmented_gmt(
        asctb_full_gmt=asctb_full_gmt,
        asctb_augmented=asctb_augmented,
        threshold=float(manifest_value(settings, "workflow_augmentation_threshold", "0.67")),
        cap_multiplier=int(manifest_value(settings, "workflow_cap_multiplier", "4")),
    )
    asctbaug = module.create_asctbaug_dataframe(augmented_gmt)
    rows = [
        {
            "term": str(row["Cell Type"]),
            "gene_id": str(row["Gene"]),
            "gene_symbol": str(row["Gene"]),
            "score": "1",
        }
        for _, row in asctbaug.iterrows()
    ]
    out_tsv = workflow_out / "hubmap_unsigned_term_gene.tsv"
    write_tsv(out_tsv, rows, ["term", "gene_id", "gene_symbol", "score"])
    return out_tsv


def main() -> int:
    args = parse_args()
    settings_by_model = load_model_settings(Path(args.model_manifest))
    if args.model_id not in settings_by_model:
        raise SystemExit(f"Unsupported model_id: {args.model_id}")
    settings = settings_by_model[args.model_id]

    human_gene_info = require_existing_file(args.human_gene_info, "human_gene_info")
    raw_asctb_dir = require_existing_dir(args.raw_asctb_dir, "raw ASCT+B directory") if args.raw_asctb_dir else None
    asctb_dir = Path(args.asctb_dir).expanduser().resolve() if args.asctb_dir else None
    input_matrix = require_existing_file(args.input_matrix, "input matrix") if args.input_matrix else None

    kind, source_script = model_source_info(args.model_id)
    if not source_script.exists():
        raise SystemExit(f"Missing source script for {args.model_id}: {source_script}")
    module = load_source_module(source_script)

    run_root = Path(args.run_root).resolve()
    model_out = run_root / args.model_id
    workflow_out = model_out / "workflow"
    extractor_out = model_out / "tissue_extractor"
    dig_dir = Path(args.dig_dir).resolve()
    if not dig_dir.exists() or not dig_dir.is_dir():
        raise SystemExit(f"Missing dig-gene-set-extractors directory: {dig_dir}")

    runner_script = (
        Path(__file__).resolve().parent / "build_hubmap_asctb_hz1.py"
        if args.model_id == "HZ1"
        else Path(__file__).resolve().parent / "build_hubmap_asctb_augmented_hz2.py"
    )

    model_out.mkdir(parents=True, exist_ok=True)
    workflow_out.mkdir(parents=True, exist_ok=True)
    extractor_out.mkdir(parents=True, exist_ok=True)

    workflow_cmd = build_workflow_cmd(
        python_bin=str(Path(args.python_bin).resolve()),
        runner_script=runner_script,
        model_id=args.model_id,
        workflow_out=workflow_out,
        human_gene_info=human_gene_info,
        raw_asctb_dir=raw_asctb_dir,
        asctb_dir=asctb_dir,
        input_matrix=input_matrix,
        settings=settings,
    )
    unsigned_term_tsv = workflow_out / "hubmap_unsigned_term_gene.tsv"
    extractor_cmd = build_extractor_cmd(
        python_bin=str(Path(args.python_bin).resolve()),
        unsigned_term_tsv=unsigned_term_tsv,
        extractor_out=extractor_out,
        provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
        provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
    )
    write_model_commands(
        model_out=model_out,
        model_id=args.model_id,
        workflow_cmd=workflow_cmd,
        extractor_cmd=extractor_cmd,
        dig_dir=dig_dir,
    )
    if args.write_commands_only:
        return 0

    model_log = model_out / "run.log"
    run_command(workflow_cmd, cwd=model_out, log_path=model_log)

    if kind == "asctb":
        build_asctb_unsigned_table(workflow_out)
    else:
        if input_matrix is None:
            raise SystemExit("HZ2 requires --input_matrix")
        build_augmented_unsigned_table(
            module=module,
            workflow_out=workflow_out,
            input_matrix=input_matrix,
            human_gene_info=human_gene_info,
            settings=settings,
        )

    run_command(extractor_cmd, cwd=dig_dir, log_path=model_log)

    summary_rows = [{"source_gmt": "genesets.gmt", **row} for row in parse_gmt(extractor_out / "genesets.gmt")]
    write_tsv(
        extractor_out / "signature_summary.tsv",
        summary_rows,
        ["source_gmt", "set_name", "description", "gene_count"],
    )
    write_manifest(
        manifest_path=extractor_out / "run_manifest.json",
        model_id=args.model_id,
        workflow_out=workflow_out,
        extractor_out=extractor_out,
        provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
        provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
