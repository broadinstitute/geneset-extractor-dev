#!/usr/bin/env python3
"""Generate declarative GTEx submission manifests from existing model configs."""
from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FULL_FAMILIES = {
    "age_binned": "gtex_age_binned",
    "continuous_age": "gtex_continuous_age",
    "hz_notebook": "gtex_aging_signatures",
}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_rows(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    models = [
        row for row in read_rows(ROOT / "config/model_list.tsv")
        if row.get("enabled", "").lower() == "true" and row.get("model_family") in FULL_FAMILIES
    ]
    tissues = read_rows(ROOT / "config/broad_tissue_list.tsv")
    partitions = [
        {"partition_id": row["tissue_id"], "tissue_id": row["tissue_id"], "tissue_name": row["tissue_name"]}
        for row in tissues
    ]
    partitions.append({"partition_id": "adipose_subcutaneous", "tissue_id": "adipose_subcutaneous", "tissue_name": "Adipose - Subcutaneous"})
    write_rows(ROOT / "config/partition_list.tsv", ["partition_id", "tissue_id", "tissue_name"], partitions)

    tasks: list[dict[str, str]] = []
    outputs: list[dict[str, str]] = []
    for tissue in tissues:
        for model in models:
            model_id = model["model_id"]
            tissue_id = tissue["tissue_id"]
            relative = f"genesets/{tissue_id}/models/{model_id}/extractor/genesets.gmt"
            tasks.append({
                "task_id": f"gtex_{model_id.lower()}_{tissue_id}",
                "model_id": model_id,
                "partition_id": tissue_id,
                "enabled": "true",
                "dig_identifier": FULL_FAMILIES[model["model_family"]],
                "output_relative_path": relative,
            })
            outputs.append({
                "output_id": f"gtex_{model_id.lower()}_{tissue_id}_gmt",
                "relative_path": relative,
                "role": "gmt",
                "required": "true",
                "model_id": model_id,
                "partition_id": tissue_id,
            })
    tasks.append({
        "task_id": "gtex_smoke_ab4_adipose_subcutaneous",
        "model_id": "AB4",
        "partition_id": "adipose_subcutaneous",
        "enabled": "true",
        "dig_identifier": "gtex_age_binned",
        "output_relative_path": "genesets/adipose_subcutaneous/models/AB4/extractor/genesets.gmt",
    })
    write_rows(ROOT / "config/task_manifest.tsv", ["task_id", "model_id", "partition_id", "enabled", "dig_identifier", "output_relative_path"], tasks)
    write_rows(ROOT / "expected/output_manifest.tsv", ["output_id", "relative_path", "role", "required", "model_id", "partition_id"], outputs)
    write_rows(
        ROOT / "expected/smoke_output_manifest.tsv",
        ["output_id", "relative_path", "role", "required", "model_id", "partition_id"],
        [{
            "output_id": "gtex_smoke_ab4_adipose_subcutaneous_gmt",
            "relative_path": "genesets/adipose_subcutaneous/models/AB4/extractor/genesets.gmt",
            "role": "gmt",
            "required": "true",
            "model_id": "AB4",
            "partition_id": "adipose_subcutaneous",
        }],
    )
    print(f"Wrote {len(tasks)} tasks, {len(outputs)} full outputs, and {len(partitions)} partitions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
