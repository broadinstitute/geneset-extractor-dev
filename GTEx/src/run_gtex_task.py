"""Thin HZ2 task selector; DIG owns GTEx TPM processing and GMT construction."""
from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
from pathlib import Path


def _task(root: Path, task_id: str) -> dict[str, str]:
    with (root / "config/task_manifest.tsv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if row["task_id"] == task_id and row["enabled"].lower() == "true":
                return row
    raise SystemExit(f"unknown enabled GTEx task: {task_id}")


def _input(name: str) -> str:
    value = os.environ.get(name, "")
    if not value or not Path(value).is_file():
        raise SystemExit(f"missing required input {name}; see reproduction/input_manifest.tsv")
    return value


def _hz2_settings(root: Path) -> dict[str, str]:
    with (root / "config/hz_consensus_model_manifest.tsv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if row.get("model_id") == "HZ2":
                return row
    raise SystemExit("HZ2 settings are missing from config/hz_consensus_model_manifest.tsv")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("--smoke", "full"))
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--out-root", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    task = _task(root, args.task_id)
    if task["model_id"] != "HZ2" or task["dig_identifier"] != "gtex_hz_consensus":
        raise SystemExit("run_gtex_task.py only dispatches the HZ2 consensus extension")
    settings = _hz2_settings(root)
    if args.mode == "--smoke":
        inputs = {
            "expression_gct": root / "tests/fixtures/gtex_hz_consensus_expression.gct",
            "sample_attributes_tsv": root / "tests/fixtures/gtex_hz_consensus_sample_attributes.tsv",
            "subject_phenotypes_tsv": root / "tests/fixtures/gtex_hz_consensus_subject_phenotypes.tsv",
        }
    else:
        inputs = {
            "expression_gct": Path(_input("GTEX_V8_TPM_GCT")),
            "sample_attributes_tsv": Path(_input("GTEX_V8_SAMPLE_ATTRIBUTES_TSV")),
            "subject_phenotypes_tsv": Path(_input("GTEX_V8_SUBJECT_PHENOTYPES_TSV")),
        }
    for label, path in inputs.items():
        if not path.is_file():
            raise SystemExit(f"missing committed smoke fixture {label}: {path}")
    dig_repo = Path(os.environ.get("DIG_REPO", root.parents[1] / "dig-gene-set-extractors")).resolve()
    cli = dig_repo / "src/geneset_extractors/cli.py"
    if not cli.is_file():
        raise SystemExit("DIG_REPO must identify a dig-gene-set-extractors checkout")
    out_dir = Path(args.out_root).resolve() / task["output_relative_path"]
    out_dir = out_dir.parent
    command = [
        os.environ.get("PYTHON_BIN", sys.executable), str(cli), "workflows", "gtex_hz_consensus",
        "--expression_gct", str(inputs["expression_gct"]),
        "--sample_attributes_tsv", str(inputs["sample_attributes_tsv"]),
        "--subject_phenotypes_tsv", str(inputs["subject_phenotypes_tsv"]),
        "--out_dir", str(out_dir),
        "--support_fraction", settings["support_fraction"],
        "--top_n", settings["top_n"],
        "--up_cutoff", settings["up_cutoff"],
        "--min_samples_per_group", settings["min_samples_per_group"],
        "--provenance_overlay_json", str(root / "config/provenance_overlay.json"),
    ]
    if args.mode == "full":
        command.extend(["--expected_group_count", "511"])
    print("$ " + " ".join(command), flush=True)
    environment = dict(os.environ)
    dig_src = str(dig_repo / "src")
    environment["PYTHONPATH"] = dig_src + (os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else "")
    return subprocess.run(command, check=False, env=environment).returncode


if __name__ == "__main__":
    raise SystemExit(main())
