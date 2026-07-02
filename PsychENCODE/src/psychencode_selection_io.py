from __future__ import annotations

import csv
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def psychencode_root() -> Path:
    return repo_root() / "geneset-extractor-dev" / "PsychENCODE"


def config_root() -> Path:
    return psychencode_root() / "config"


def default_out_root() -> Path:
    return Path.cwd() / "psychencode_outputs"


def default_model_list_path() -> Path:
    return config_root() / "model_list.tsv"


def default_model_manifest_path() -> Path:
    return config_root() / "model_manifest.tsv"


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


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
    rows: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        token = line.split("\t", 1)[0].strip()
        if not token or token == key_field:
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
    return sorted(set(requested), key=lambda item_id: order_index[item_id])


def row_map(rows: list[dict[str, str]], key_field: str) -> dict[str, dict[str, str]]:
    return {str(row.get(key_field, "")).strip(): row for row in rows if str(row.get(key_field, "")).strip()}
