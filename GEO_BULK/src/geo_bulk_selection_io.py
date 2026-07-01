from __future__ import annotations

import csv
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
