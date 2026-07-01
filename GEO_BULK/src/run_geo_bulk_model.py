#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.request import Request, urlopen

from geo_bulk_selection_io import (
    default_dataset_list_path,
    default_description_templates_path,
    default_model_manifest_path,
    read_tsv,
    row_map,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_id", required=True)
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--dataset_list", default=str(default_dataset_list_path()))
    parser.add_argument("--model_manifest", default=str(default_model_manifest_path()))
    parser.add_argument("--description_templates", default=str(default_description_templates_path()))
    parser.add_argument("--dig_dir", required=True)
    parser.add_argument("--input_root", required=True)
    parser.add_argument("--out_root", required=True)
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument("--backend")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--offline", action="store_true")
    return parser


def run_command(command: list[str], *, cwd: Path, env: dict[str, str], log_path: Path) -> None:
    print("$ " + " ".join(command), flush=True)
    with log_path.open("a", encoding="utf-8") as log:
        log.write("$ " + " ".join(command) + "\n")
        subprocess.run(command, cwd=str(cwd), env=env, stdout=log, stderr=subprocess.STDOUT, check=True)


def download(url: str, destination: Path, *, offline: bool, retries: int = 3) -> Path:
    if destination.exists() and destination.stat().st_size > 0:
        return destination
    if offline:
        raise FileNotFoundError(f"Offline mode requires existing input: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    request = Request(url, headers={"User-Agent": "geneset-extractor-dev/geo-bulk"})
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urlopen(request, timeout=120) as response, partial.open("wb") as handle:
                shutil.copyfileobj(response, handle)
            if partial.stat().st_size == 0:
                raise ValueError(f"Downloaded empty file from {url}")
            partial.replace(destination)
            return destination
        except Exception as exc:
            last_error = exc
            if partial.exists():
                partial.unlink()
            if attempt < retries:
                time.sleep(float(attempt))
    raise RuntimeError(f"Unable to download {url}: {last_error}")


def write_model_sidecars(extractor_dir: Path, payload: dict[str, object]) -> int:
    metadata_paths = sorted(extractor_dir.rglob("geneset.meta.json"))
    if not metadata_paths:
        raise RuntimeError(f"No geneset.meta.json files found under {extractor_dir}")
    for metadata_path in metadata_paths:
        metadata_path.with_name("geneset.model.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return len(metadata_paths)


def write_signature_summary(extractor_dir: Path) -> int:
    gmt_path = extractor_dir / "genesets.gmt"
    if not gmt_path.exists():
        return 0
    rows: list[dict[str, object]] = []
    for line in gmt_path.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) >= 2:
            rows.append({"set_name": fields[0], "description": fields[1], "gene_count": max(0, len(fields) - 2)})
    with (extractor_dir / "signature_summary.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=["set_name", "description", "gene_count"])
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def promote_single_comparison_artifacts(extractor_dir: Path) -> Path:
    metadata_paths = sorted(
        path for path in extractor_dir.glob("*/geneset.meta.json") if path.parent != extractor_dir
    )
    if len(metadata_paths) != 1:
        raise RuntimeError(
            "GEO bulk models require exactly one comparison directory so canonical artifacts can be "
            f"published directly under extractor/; found {len(metadata_paths)}"
        )
    comparison_dir = metadata_paths[0].parent
    for name in (
        "geneset.tsv",
        "geneset.full.tsv",
        "geneset.meta.json",
        "geneset.provenance.json",
        "geneset.model.json",
        "run_summary.json",
        "run_summary.txt",
    ):
        source = comparison_dir / name
        if not source.exists():
            raise RuntimeError(f"Missing canonical comparison artifact: {source}")
        shutil.copy2(source, extractor_dir / name)
    return comparison_dir


def main() -> int:
    args = build_parser().parse_args()
    dataset = row_map(read_tsv(Path(args.dataset_list)), "dataset_id").get(args.dataset_id)
    model = row_map(read_tsv(Path(args.model_manifest)), "model_id").get(args.model_id)
    if dataset is None:
        raise SystemExit(f"Unknown GEO dataset: {args.dataset_id}")
    if model is None:
        raise SystemExit(f"Unknown GEO model: {args.model_id}")

    dig_dir = Path(args.dig_dir).resolve()
    input_dir = Path(args.input_root).resolve() / args.dataset_id
    model_dir = Path(args.out_root).resolve() / "genesets" / args.dataset_id / "models" / args.model_id
    workflow_dir = model_dir / "workflow"
    prepared_dir = workflow_dir / "prepared"
    de_dir = workflow_dir / "de"
    extractor_dir = model_dir / "extractor"
    if model_dir.exists() and any(model_dir.iterdir()):
        if not args.overwrite:
            raise SystemExit(f"Output exists; pass --overwrite to replace it: {model_dir}")
        shutil.rmtree(model_dir)
    workflow_dir.mkdir(parents=True, exist_ok=True)
    extractor_dir.mkdir(parents=True, exist_ok=True)

    counts_file = download(
        dataset["counts_url"], input_dir / dataset["counts_filename"], offline=args.offline
    )
    miniml_file = download(
        dataset["miniml_url"], input_dir / dataset["miniml_filename"], offline=args.offline
    )
    annotation_file = download(
        dataset["annotation_url"], input_dir / dataset["annotation_filename"], offline=args.offline
    )

    python_bin = str(Path(args.python_bin).resolve())
    env = dict(os.environ)
    env["PYTHONPATH"] = str(dig_dir / "src")
    log_path = model_dir / "run.log"
    prepare_command = [
        python_bin,
        "-m",
        "geneset_extractors.cli",
        "workflows",
        "geo_bulk_prepare",
        "--counts_file",
        str(counts_file),
        "--miniml_file",
        str(miniml_file),
        "--annotation_file",
        str(annotation_file),
        "--out_dir",
        str(prepared_dir),
        "--study_id",
        args.dataset_id,
        "--sample_id_field",
        dataset.get("sample_id_field", "title") or "title",
        "--group_characteristic",
        dataset["group_characteristic"],
        "--condition_a_values",
        dataset["condition_a_values"],
        "--condition_b_values",
        dataset["condition_b_values"],
        "--condition_a_label",
        dataset["condition_a_label"],
        "--condition_b_label",
        dataset["condition_b_label"],
        "--annotation_source_column",
        dataset["annotation_source_column"],
        "--annotation_target_column",
        dataset["annotation_target_column"],
        "--counts_source_url",
        dataset["counts_url"],
        "--miniml_source_url",
        dataset["miniml_url"],
        "--annotation_source_url",
        dataset["annotation_url"],
        "--landing_page_url",
        dataset["landing_page_url"],
    ]
    backend = args.backend or model["workflow_backend"]
    de_command = [
        python_bin,
        "-m",
        "geneset_extractors.cli",
        "workflows",
        "rna_de_prepare",
        "--modality",
        "bulk",
        "--counts_tsv",
        str(prepared_dir / "counts.tsv"),
        "--matrix_orientation",
        "gene_by_sample",
        "--feature_id_column",
        dataset["feature_id_column"],
        "--sample_id_column",
        "sample_id",
        "--sample_metadata_tsv",
        str(prepared_dir / "sample_metadata.tsv"),
        "--group_column",
        "condition",
        "--comparison_mode",
        "condition_a_vs_b",
        "--condition_a",
        dataset["condition_a_label"],
        "--condition_b",
        dataset["condition_b_label"],
        "--feature_mapping_tsv",
        str(prepared_dir / "feature_mapping.tsv"),
        "--feature_mapping_from_column",
        "source_feature_id",
        "--feature_mapping_to_column",
        "gene_symbol",
        "--feature_mapping_strip_version",
        "true",
        "--drop_unmapped_features",
        "true",
        "--de_mode",
        model["workflow_de_mode"],
        "--backend",
        backend,
        "--out_dir",
        str(de_dir),
        "--organism",
        dataset["organism"],
        "--genome_build",
        dataset["genome_build"],
        "--run_extractor",
        "true",
        "--extractor_out_dir",
        str(extractor_dir),
        "--extractor_signature_name",
        dataset["signature_name"],
        "--extractor_top_k",
        model["extractor_top_k"],
        "--extractor_padj_max",
        model["extractor_padj_max"],
        "--extractor_min_abs_logfc",
        model["extractor_min_abs_logfc"],
        "--extractor_gmt_min_genes",
        model["extractor_gmt_min_genes"],
        "--extractor_gmt_max_genes",
        model["extractor_gmt_max_genes"],
        "--extractor_gmt_topk_list",
        model["extractor_top_k"],
        "--upstream_provenance_graph_json",
        str(prepared_dir / "geo_bulk_inputs.provenance_graph.json"),
    ]
    covariates = str(dataset.get("covariates", "") or "").strip()
    if covariates:
        de_command.extend(["--covariates", covariates])
    (model_dir / "commands.json").write_text(
        json.dumps({"prepare": prepare_command, "rna_de": de_command}, indent=2) + "\n",
        encoding="utf-8",
    )
    run_command(prepare_command, cwd=dig_dir, env=env, log_path=log_path)
    run_command(de_command, cwd=dig_dir, env=env, log_path=log_path)
    de_summary = json.loads((de_dir / "prepare_summary.json").read_text(encoding="utf-8"))
    resolved_backend = str(de_summary.get("resolved_backend") or backend)
    sidecar_payload = {
        "model_id": args.model_id,
        "model_family": "bulk_rna_de",
        "dataset_id": args.dataset_id,
        "source_repository": "NCBI GEO",
        "landing_page_url": dataset["landing_page_url"],
        "comparison": {
            "group_characteristic": dataset["group_characteristic"],
            "condition_a_values": dataset["condition_a_values"].split(","),
            "condition_b_values": dataset["condition_b_values"].split(","),
            "condition_a_label": dataset["condition_a_label"],
            "condition_b_label": dataset["condition_b_label"],
            "covariates": [value.strip() for value in covariates.split(",") if value.strip()],
        },
        "parameters": {**model, "requested_backend": backend, "resolved_backend": resolved_backend},
    }
    n_extractor_groups = write_model_sidecars(extractor_dir, sidecar_payload)
    n_gmt_sets = write_signature_summary(extractor_dir)

    refresh_script = Path(__file__).resolve().parents[2] / "src" / "refresh_model_metadata_and_provenance.py"
    refresh_command = [
        python_bin,
        str(refresh_script),
        "--model_id",
        args.model_id,
        "--model_dir",
        str(model_dir),
        "--description_template_tsv",
        str(Path(args.description_templates).resolve()),
        "--python_bin",
        python_bin,
        "--dig_dir",
        str(dig_dir),
    ]
    run_command(refresh_command, cwd=dig_dir, env=env, log_path=log_path)
    canonical_comparison_dir = promote_single_comparison_artifacts(extractor_dir)
    (model_dir / "run_summary.json").write_text(
        json.dumps(
            {
                "dataset_id": args.dataset_id,
                "model_id": args.model_id,
                "requested_backend": backend,
                "resolved_backend": resolved_backend,
                "n_extractor_groups": n_extractor_groups,
                "n_gmt_sets": n_gmt_sets,
                "extractor_dir": str(extractor_dir),
                "canonical_comparison_dir": str(canonical_comparison_dir),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
