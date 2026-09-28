"""Thin GTEx dispatch adapter; DIG retains analysis and GMT construction."""
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


def _file_from_environment(name: str) -> str:
    value = os.environ.get(name, "")
    if not value or not Path(value).is_file():
        raise SystemExit(f"missing required input {name}; see reproduction/input_manifest.tsv")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("--smoke", "full"))
    parser.add_argument("--out-root", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    if args.mode == "--smoke":
        inputs = {
            "GTEX_COUNTS_GCT": root / "tests/fixtures/gtex_smoke_expression.gct",
            "GTEX_SAMPLE_ATTRIBUTES_TSV": root / "tests/fixtures/gtex_smoke_sample_attributes.tsv",
            "GTEX_SUBJECT_PHENOTYPES_TSV": root / "tests/fixtures/gtex_smoke_subject_phenotypes.tsv",
            "GTEX_GTF": root / "tests/fixtures/gtex_smoke_annotation.gtf",
        }
        for name, path in inputs.items():
            if not path.is_file():
                raise SystemExit(f"missing committed smoke fixture {name}: {path}")
    else:
        inputs = {name: Path(_file_from_environment(name)) for name in (
            "GTEX_COUNTS_GCT", "GTEX_SAMPLE_ATTRIBUTES_TSV", "GTEX_SUBJECT_PHENOTYPES_TSV", "GTEX_GTF",
        )}
    dig_repo = Path(os.environ.get("DIG_REPO", root.parents[1] / "dig-gene-set-extractors")).resolve()
    if not (dig_repo / "src/geneset_extractors").is_dir():
        raise SystemExit("DIG_REPO must identify a dig-gene-set-extractors checkout")
    command = [
        "bash", str(root / "run/build_genesets.sh"),
        "--models", "AB4", "--tissues", "adipose_subcutaneous",
        "--counts_gct", str(inputs["GTEX_COUNTS_GCT"]),
        "--sample_metadata_tsv", str(inputs["GTEX_SAMPLE_ATTRIBUTES_TSV"]),
        "--subject_metadata_tsv", str(inputs["GTEX_SUBJECT_PHENOTYPES_TSV"]),
        "--gtf", str(inputs["GTEX_GTF"]),
        "--dig_dir", str(dig_repo), "--out_root", str(Path(args.out_root).resolve()),
        "--overwrite",
    ]
    print("$ " + " ".join(command), flush=True)
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
