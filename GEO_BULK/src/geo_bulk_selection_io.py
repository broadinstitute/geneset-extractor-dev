from __future__ import annotations

import csv
import re
from pathlib import Path


def library_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_dataset_list_path() -> Path:
    return library_root() / "config" / "dataset_list.tsv"


def default_model_list_path() -> Path:
    return library_root() / "config" / "model_list.tsv"


def default_model_manifest_path() -> Path:
    return library_root() / "config" / "model_manifest.tsv"


def default_description_templates_path() -> Path:
    return library_root() / "config" / "model_description_templates.tsv"


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle, delimiter="\t")]


def row_map(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    mapping: dict[str, dict[str, str]] = {}
    for row in rows:
        value = str(row.get(key, "")).strip()
        if not value:
            raise ValueError(f"Missing {key} in config row")
        if value in mapping:
            raise ValueError(f"Duplicate {key}: {value}")
        mapping[value] = row
    return mapping


def enabled_ids(rows: list[dict[str, str]], key: str) -> list[str]:
    return [
        str(row[key]).strip()
        for row in rows
        if str(row.get("enabled", "")).strip().lower() in {"1", "true", "yes"}
    ]


def resolve_ids(requested: str, rows: list[dict[str, str]], key: str) -> list[str]:
    available = row_map(rows, key)
    if requested.strip().lower() == "all":
        selected = enabled_ids(rows, key)
    else:
        selected = [item.strip() for item in requested.split(",") if item.strip()]
    missing = [item for item in selected if item not in available]
    if missing:
        raise ValueError(f"Unknown {key} values: {', '.join(missing)}")
    if not selected:
        raise ValueError(f"No {key} values selected")
    return selected


def camel_case(label: str) -> str:
    parts = [part for part in re.split(r"[^0-9A-Za-z]+", str(label)) if part]
    return "".join(part[:1].upper() + part[1:] for part in parts)


def comparison_labels(condition_a_label: str, condition_b_label: str) -> tuple[str, str]:
    camel = f"{camel_case(condition_a_label)}Vs{camel_case(condition_b_label)}"
    human = (
        f"{str(condition_a_label).replace('_', ' ')} relative to "
        f"{str(condition_b_label).replace('_', ' ')}"
    )
    return camel, human


def build_model_sidecar(
    *,
    dataset: dict[str, str],
    model: dict[str, str],
    dataset_id: str,
    model_id: str,
    requested_backend: str | None = None,
    resolved_backend: str | None = None,
) -> dict[str, object]:
    """Assemble the branch-standard geneset.model.json payload from config rows.

    Derived purely from dataset_list.tsv + model_manifest.tsv, so it can be
    regenerated for existing outputs without rerunning differential expression.
    """
    a_label = dataset["condition_a_label"]
    b_label = dataset["condition_b_label"]
    comparison_label, comparison_label_human = comparison_labels(a_label, b_label)
    signature_name = f"GEO_BULK_{dataset_id}_{comparison_label}"
    covariates = [value.strip() for value in str(dataset.get("covariates", "") or "").split(",") if value.strip()]
    requested = requested_backend or model.get("workflow_backend")
    resolved = resolved_backend or requested
    return {
        "schema_version": "1",
        "library": "GEO_BULK",
        "model_id": model_id,
        "model_family": "bulk_rna_de",
        "model_group": "GB",
        "model_label": "bulk_rna_de",
        "workflow_name": "geo_bulk",
        "extractor_name": "rna_deg_multi",
        "dataset_id": dataset_id,
        "source_repository": "NCBI GEO",
        "landing_page_url": dataset["landing_page_url"],
        "inputs": {
            "dataset_id": dataset_id,
            "landing_page_url": dataset["landing_page_url"],
            "counts_url": dataset["counts_url"],
            "miniml_url": dataset["miniml_url"],
            "annotation_url": dataset["annotation_url"],
            "organism": dataset["organism"],
            "genome_build": dataset["genome_build"],
            "group_characteristic": dataset["group_characteristic"],
            "condition_a_label": a_label,
            "condition_b_label": b_label,
            "covariates": covariates,
        },
        "comparison": {
            "group_characteristic": dataset["group_characteristic"],
            "condition_a_values": dataset["condition_a_values"].split(","),
            "condition_b_values": dataset["condition_b_values"].split(","),
            "condition_a_label": a_label,
            "condition_b_label": b_label,
            "covariates": covariates,
        },
        "naming": {
            "signature_name": signature_name,
            "comparison_label": comparison_label,
            "comparison_label_human": comparison_label_human,
            "comparison_style": "single_contrast",
            "gene_set_pattern": "GEO_BULK_<dataset_id>_<comparison>_up|dn",
            "direction_labels": ["up", "dn"],
        },
        "parameters": {**model, "requested_backend": requested, "resolved_backend": resolved},
    }
