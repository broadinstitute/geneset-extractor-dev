from __future__ import annotations

import csv
import os
import re
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def gtex_root() -> Path:
    return repo_root() / "geneset-extractor-dev" / "GTEx"


def config_root() -> Path:
    override = os.environ.get("GTEX_CONFIG_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    planning_override = os.environ.get("GTEX_PLANNING_ROOT", "").strip()
    if planning_override:
        return Path(planning_override).expanduser().resolve()
    return gtex_root() / "config"


def planning_root() -> Path:
    override = os.environ.get("GTEX_PLANNING_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return gtex_root() / "planning"


def default_out_root() -> Path:
    override = os.environ.get("GTEX_OUT_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path.cwd() / "gtex_outputs"


def default_genesets_root() -> Path:
    return default_out_root() / "genesets"


def default_pigean_eaggl_root() -> Path:
    return default_out_root() / "pigean_eaggl"


def default_model_list_path() -> Path:
    override = os.environ.get("GTEX_MODEL_LIST", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return config_root() / "model_list.tsv"


def default_tissue_list_path() -> Path:
    override = os.environ.get("GTEX_TISSUE_LIST", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return config_root() / "tissue_list.tsv"


def default_broad_tissue_list_path() -> Path:
    override = os.environ.get("GTEX_BROAD_TISSUE_LIST", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return config_root() / "broad_tissue_list.tsv"


def default_age_binned_model_manifest_path() -> Path:
    override = os.environ.get("GTEX_AGE_BINNED_MODEL_MANIFEST", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return config_root() / "age_binned_model_manifest.tsv"


def default_continuous_age_model_manifest_path() -> Path:
    override = os.environ.get("GTEX_CONTINUOUS_AGE_MODEL_MANIFEST", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return config_root() / "continuous_age_model_manifest.tsv"


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def normalize_tissue_id(label: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "_", label.strip().lower())
    return re.sub(r"_+", "_", value).strip("_")


def load_model_rows(path: Path | None = None) -> list[dict[str, str]]:
    return read_tsv(path or default_model_list_path())


def load_tissue_rows(path: Path | None = None) -> list[dict[str, str]]:
    return read_tsv(path or default_tissue_list_path())


def ordered_ids(rows: list[dict[str, str]], key_field: str) -> list[str]:
    return [str(row.get(key_field, "")).strip() for row in rows if str(row.get(key_field, "")).strip()]


def enabled_ids(rows: list[dict[str, str]], key_field: str) -> list[str]:
    enabled: list[str] = []
    for row in rows:
        item_id = str(row.get(key_field, "")).strip()
        if not item_id:
            continue
        if str(row.get("enabled", "true")).strip().lower() == "true":
            enabled.append(item_id)
    return enabled


def parse_id_file(path: Path, key_field: str) -> list[str]:
    text = path.read_text(encoding="utf-8")
    rows: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        token = line.split("\t", 1)[0].strip()
        if not token:
            continue
        if token == key_field:
            continue
        rows.append(token)
    return rows


def resolve_requested_ids(
    *,
    csv_text: str | None,
    file_path: str | None,
    rows: list[dict[str, str]],
    key_field: str,
) -> list[str]:
    all_ids = ordered_ids(rows, key_field)
    default_ids = enabled_ids(rows, key_field)
    if csv_text and file_path:
        raise SystemExit(f"Use only one of --{key_field}s or --{key_field}s_file")
    if file_path:
        requested = parse_id_file(Path(file_path), key_field)
    elif csv_text and csv_text.strip().lower() != "all":
        requested = [item.strip() for item in csv_text.split(",") if item.strip()]
    else:
        requested = list(default_ids)
    if not requested:
        raise SystemExit(f"No {key_field} values selected")
    known = set(all_ids)
    unknown = [item for item in requested if item not in known]
    if unknown:
        raise SystemExit(f"Unknown {key_field} values: {', '.join(unknown)}")
    order_index = {item_id: index for index, item_id in enumerate(all_ids)}
    deduped = sorted(set(requested), key=lambda item_id: order_index[item_id])
    return deduped


def row_map(rows: list[dict[str, str]], key_field: str) -> dict[str, dict[str, str]]:
    return {str(row.get(key_field, "")).strip(): row for row in rows if str(row.get(key_field, "")).strip()}


def model_group_for(model_id: str) -> str:
    if model_id.startswith("AB"):
        return "age_binned"
    if model_id.startswith("AC"):
        return "continuous_age"
    if model_id.startswith("HZ"):
        return "hz_notebook"
    if model_id.startswith("TV"):
        return "tissue_versus"
    raise SystemExit(f"Unsupported model prefix for {model_id}")


def relative_or_absolute_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return repo_root() / path
