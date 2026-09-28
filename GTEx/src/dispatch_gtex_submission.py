"""Thin GTEx submission adapter; DIG retains analysis and GMT construction."""
from __future__ import annotations

import argparse
import csv
import os
import subprocess
from pathlib import Path


def _file_from_environment(name: str) -> str:
    value = os.environ.get(name, "")
    if not value or not Path(value).is_file():
        raise SystemExit(f"missing required input {name}; see reproduction/input_manifest.tsv")
    return value


def _enabled_models(root: Path, family: str) -> list[str]:
    with (root / "config/model_list.tsv").open(encoding="utf-8", newline="") as handle:
        return [
            row["model_id"]
            for row in csv.DictReader(handle, delimiter="\t")
            if row.get("model_family") == family and row.get("enabled", "").lower() == "true"
        ]


def _build_command(
    root: Path,
    dig_repo: Path,
    out_root: Path,
    model_ids: list[str],
    inputs: dict[str, Path],
    *,
    broad: bool,
    human_gene_info: Path | None = None,
) -> list[str]:
    command = [
        "bash", str(root / "run/build_genesets.sh"),
        "--models", ",".join(model_ids),
        "--tissues", "all",
        "--counts_gct", str(inputs["counts"]),
        "--sample_metadata_tsv", str(inputs["sample"]),
        "--subject_metadata_tsv", str(inputs["subject"]),
        "--gtf", str(inputs["gtf"]),
        "--dig_dir", str(dig_repo), "--out_root", str(out_root), "--overwrite",
    ]
    if broad:
        command.extend(["--tissue_granularity", "broad"])
    if human_gene_info is not None:
        command.extend(["--human_gene_info", str(human_gene_info)])
    return command


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("--smoke", "full"))
    parser.add_argument("--out-root", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.mode == "--smoke":
        smoke_inputs = {
            "counts": root / "tests/fixtures/gtex_smoke_expression.gct",
            "sample": root / "tests/fixtures/gtex_smoke_sample_attributes.tsv",
            "subject": root / "tests/fixtures/gtex_smoke_subject_phenotypes.tsv",
            "gtf": root / "tests/fixtures/gtex_smoke_annotation.gtf",
        }
        for name, path in smoke_inputs.items():
            if not path.is_file():
                raise SystemExit(f"missing committed smoke fixture {name}: {path}")
    else:
        v10_inputs = {
            "counts": Path(_file_from_environment("GTEX_V10_COUNTS_GCT")),
            "sample": Path(_file_from_environment("GTEX_V10_SAMPLE_ATTRIBUTES_TSV")),
            "subject": Path(_file_from_environment("GTEX_V10_SUBJECT_PHENOTYPES_TSV")),
            "gtf": Path(_file_from_environment("GTEX_GTF")),
        }
        v8_inputs = {
            "counts": Path(_file_from_environment("GTEX_V8_COUNTS_GCT")),
            "sample": Path(_file_from_environment("GTEX_V8_SAMPLE_ATTRIBUTES_TSV")),
            "subject": Path(_file_from_environment("GTEX_V8_SUBJECT_PHENOTYPES_TSV")),
            "gtf": v10_inputs["gtf"],
        }
        human_gene_info = Path(_file_from_environment("GTEX_V8_HUMAN_GENE_INFO"))
    dig_repo = Path(os.environ.get("DIG_REPO", root.parents[0].parent / "dig-gene-set-extractors")).resolve()
    if not (dig_repo / "src/geneset_extractors").is_dir():
        raise SystemExit("DIG_REPO must identify a dig-gene-set-extractors checkout")
    out_root = Path(args.out_root).resolve()
    if args.mode == "--smoke":
        command = _build_command(root, dig_repo, out_root, ["AB4"], smoke_inputs, broad=False)
        command[command.index("--tissues") + 1] = "adipose_subcutaneous"
        print("$ " + " ".join(command), flush=True)
        return subprocess.run(command, check=False).returncode

    for families, inputs, hgi in (
        (("age_binned", "continuous_age"), v10_inputs, None),
        (("hz_notebook",), v8_inputs, human_gene_info),
    ):
        model_ids = [model_id for family in families for model_id in _enabled_models(root, family)]
        command = _build_command(root, dig_repo, out_root, model_ids, inputs, broad=True, human_gene_info=hgi)
        print("$ " + " ".join(command), flush=True)
        completed = subprocess.run(command, check=False)
        if completed.returncode:
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
