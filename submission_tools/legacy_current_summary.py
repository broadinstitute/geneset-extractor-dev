#!/usr/bin/env python3
"""Summarize paired legacy/current GMT inventories from a manifest.

The manifest may retain paths from the environment in which it was created.
When those paths are unavailable, GMTs and optional mappings are resolved by
basename beneath explicit roots (or sibling directories next to the manifest).
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .postrun_report import _markdown_table, _write_tsv_gz


LOG = logging.getLogger(__name__)
REQUIRED_COLUMNS = {"library_id", "model_id", "legacy_gmt", "current_gmt"}


def _resolve(recorded_path: str, root: Path | None) -> Path:
    """Use an existing recorded path, otherwise resolve its unique basename."""
    recorded = Path(recorded_path)
    if recorded.is_file():
        return recorded.resolve()
    if root is None:
        raise ValueError(f"missing file {recorded_path!r}; no search root was supplied")
    matches = sorted(root.rglob(recorded.name))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {recorded.name!r} beneath {root}, found {len(matches)}")
    return matches[0].resolve()


def _optional_resolve(recorded_path: str, root: Path | None) -> Path | None:
    if not recorded_path.strip():
        return None
    try:
        return _resolve(recorded_path, root)
    except ValueError:
        return None


def _read_manifest(path: Path, legacy_root: Path | None, current_root: Path | None, mapping_root: Path | None) -> list[dict[str, str | Path | None]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not reader.fieldnames or not REQUIRED_COLUMNS <= set(reader.fieldnames):
            raise ValueError("manifest must contain library_id, model_id, legacy_gmt, and current_gmt columns")
        entries: list[dict[str, str | Path | None]] = []
        seen: set[tuple[str, str]] = set()
        for line_number, row in enumerate(reader, 2):
            library_id = str(row["library_id"] or "").strip()
            model_id = str(row["model_id"] or "").strip()
            if not library_id or not model_id:
                raise ValueError(f"blank library_id or model_id at {path}:{line_number}")
            if (library_id, model_id) in seen:
                raise ValueError(f"duplicate library/model pair {library_id!r}/{model_id!r}")
            seen.add((library_id, model_id))
            entries.append({
                "library_id": library_id,
                "model_id": model_id,
                "legacy_gmt": _resolve(str(row["legacy_gmt"] or ""), legacy_root),
                "current_gmt": _resolve(str(row["current_gmt"] or ""), current_root),
                "name_mapping": _optional_resolve(str(row.get("name_mapping", "") or ""), mapping_root),
            })
    if not entries:
        raise ValueError("manifest contains no library/model pairs")
    return entries


def _gmt_inventory(path: Path) -> tuple[dict[str, int], set[str]]:
    names: set[str] = set()
    genes: set[str] = set()
    membership_count = 0
    empty_set_count = 0
    malformed_record_count = 0
    duplicate_name_count = 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        for line in handle:
            fields = line.rstrip("\r\n").split("\t")
            if not line.strip():
                continue
            if len(fields) < 3 or not fields[0].strip():
                malformed_record_count += 1
                continue
            name = fields[0].strip()
            if name in names:
                duplicate_name_count += 1
                continue
            names.add(name)
            members = {gene.strip() for gene in fields[2:] if gene.strip()}
            if not members:
                empty_set_count += 1
            membership_count += len(members)
            genes.update(members)
    return {
        "gene_set_count": len(names),
        "membership_count": membership_count,
        "unique_gene_count": len(genes),
        "empty_set_count": empty_set_count,
        "malformed_record_count": malformed_record_count,
        "duplicate_name_count": duplicate_name_count,
    }, names


def _mapping_count(path: Path | None) -> tuple[int, str]:
    if path is None:
        return 0, "not_supplied"
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = set(reader.fieldnames or [])
        current_column = "regenerated_set_name" if "regenerated_set_name" in fields else "generated_set_name"
        if not {"legacy_set_name", current_column} <= fields:
            return 0, "invalid_columns"
        count = sum(1 for row in reader if str(row["legacy_set_name"] or "").strip() and str(row[current_column] or "").strip())
    return count, "available" if count else "no_overlap"


def _library_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["library_id"])].append(row)
    result: list[dict[str, object]] = []
    for library_id, library_rows in sorted(grouped.items()):
        result.append({
            "library_id": library_id,
            "model_count": len(library_rows),
            "legacy_gene_set_count": sum(int(row["legacy_gene_set_count"]) for row in library_rows),
            "current_gene_set_count": sum(int(row["current_gene_set_count"]) for row in library_rows),
            "gene_set_count_delta": sum(int(row["gene_set_count_delta"]) for row in library_rows),
            "legacy_membership_count": sum(int(row["legacy_membership_count"]) for row in library_rows),
            "current_membership_count": sum(int(row["current_membership_count"]) for row in library_rows),
            "membership_count_delta": sum(int(row["membership_count_delta"]) for row in library_rows),
            "mapped_set_count": sum(int(row["mapped_set_count"]) for row in library_rows),
            "compared_set_count": sum(int(row["compared_set_count"]) for row in library_rows),
            "direct_name_match_count": sum(int(row["direct_name_match_count"]) for row in library_rows),
            "legacy_only_set_name_count": sum(int(row["legacy_only_set_name_count"]) for row in library_rows),
            "current_only_set_name_count": sum(int(row["current_only_set_name_count"]) for row in library_rows),
        })
    return result


def create_legacy_current_summary(manifest_path: Path, output_dir: Path, *, legacy_root: Path | None = None, current_root: Path | None = None, mapping_root: Path | None = None, command: str = "") -> dict[str, object]:
    """Write model-, library-, and collection-level GMT inventory statistics."""
    manifest_path = manifest_path.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"output directory must be empty: {output_dir}")
    legacy_root = (legacy_root or manifest_path.parent / "legacy_gmts").resolve()
    current_root = (current_root or manifest_path.parent / "current_gmts").resolve()
    mapping_root = (mapping_root or manifest_path.parent / "reference_mappings").resolve()
    entries = _read_manifest(manifest_path, legacy_root, current_root, mapping_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=output_dir / "run.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", force=True)
    rows: list[dict[str, object]] = []
    for entry in entries:
        legacy, legacy_names = _gmt_inventory(Path(entry["legacy_gmt"]))
        current, current_names = _gmt_inventory(Path(entry["current_gmt"]))
        mapped_set_count, mapping_status = _mapping_count(entry["name_mapping"] if isinstance(entry["name_mapping"], Path) else None)
        direct_name_match_count = len(legacy_names & current_names)
        if mapping_status == "no_overlap":
            comparison_method = "direct_set_name"
            compared_set_count = direct_name_match_count
        elif mapping_status == "available":
            comparison_method = "name_mapping"
            compared_set_count = mapped_set_count
        else:
            comparison_method = "not_compared"
            compared_set_count = 0
        row: dict[str, object] = {
            "library_id": entry["library_id"], "model_id": entry["model_id"],
            "legacy_gmt": str(entry["legacy_gmt"]), "current_gmt": str(entry["current_gmt"]),
            "name_mapping": str(entry["name_mapping"] or ""), "mapping_status": mapping_status,
            "mapped_set_count": mapped_set_count, "comparison_method": comparison_method,
            "compared_set_count": compared_set_count, "direct_name_match_count": direct_name_match_count,
            "legacy_only_set_name_count": len(legacy_names - current_names),
            "current_only_set_name_count": len(current_names - legacy_names),
            **{f"legacy_{key}": value for key, value in legacy.items()},
            **{f"current_{key}": value for key, value in current.items()},
        }
        row["gene_set_count_delta"] = int(row["current_gene_set_count"]) - int(row["legacy_gene_set_count"])
        row["membership_count_delta"] = int(row["current_membership_count"]) - int(row["legacy_membership_count"])
        row["unique_gene_count_delta"] = int(row["current_unique_gene_count"]) - int(row["legacy_unique_gene_count"])
        rows.append(row)
        LOG.info("summarized %s/%s", entry["library_id"], entry["model_id"])
    library_rows = _library_summary(rows)
    summary: dict[str, object] = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "library_count": len(library_rows), "pair_count": len(rows),
        "legacy_gene_set_count": sum(int(row["legacy_gene_set_count"]) for row in rows),
        "current_gene_set_count": sum(int(row["current_gene_set_count"]) for row in rows),
        "gene_set_count_delta": sum(int(row["gene_set_count_delta"]) for row in rows),
        "legacy_membership_count": sum(int(row["legacy_membership_count"]) for row in rows),
        "current_membership_count": sum(int(row["current_membership_count"]) for row in rows),
        "membership_count_delta": sum(int(row["membership_count_delta"]) for row in rows),
        "mapped_set_count": sum(int(row["mapped_set_count"]) for row in rows),
        "compared_set_count": sum(int(row["compared_set_count"]) for row in rows),
        "direct_name_match_count": sum(int(row["direct_name_match_count"]) for row in rows),
        "legacy_only_set_name_count": sum(int(row["legacy_only_set_name_count"]) for row in rows),
        "current_only_set_name_count": sum(int(row["current_only_set_name_count"]) for row in rows), "command": command,
    }
    _write_tsv_gz(output_dir / "model_summary.tsv.gz", rows)
    _write_tsv_gz(output_dir / "library_summary.tsv.gz", library_rows)
    _write_tsv_gz(output_dir / "summary.tsv.gz", [summary])
    (output_dir / "report.md").write_text("\n".join([
        "# Legacy/current GMT inventory summary", "", "## Overall summary", "",
        _markdown_table([summary], ["library_count", "pair_count", "legacy_gene_set_count", "current_gene_set_count", "gene_set_count_delta", "legacy_membership_count", "current_membership_count", "membership_count_delta", "mapped_set_count", "compared_set_count", "direct_name_match_count", "legacy_only_set_name_count", "current_only_set_name_count"]),
        "## Library summary", "", _markdown_table(library_rows, ["library_id", "model_count", "legacy_gene_set_count", "current_gene_set_count", "gene_set_count_delta", "legacy_membership_count", "current_membership_count", "membership_count_delta", "mapped_set_count", "compared_set_count", "direct_name_match_count", "legacy_only_set_name_count", "current_only_set_name_count"]),
        "## Model summary", "", _markdown_table(rows, ["library_id", "model_id", "legacy_gene_set_count", "current_gene_set_count", "gene_set_count_delta", "legacy_membership_count", "current_membership_count", "membership_count_delta", "comparison_method", "compared_set_count", "direct_name_match_count", "legacy_only_set_name_count", "current_only_set_name_count", "mapping_status"]), "",
    ]), encoding="utf-8")
    (output_dir / "commands.md").write_text(f"# Command\n\n```bash\n{command or 'command unavailable'}\n```\n", encoding="utf-8")
    (output_dir / "MANIFEST.md").write_text("# Output manifest\n\n- `report.md`: aggregate Markdown summary.\n- `model_summary.tsv.gz`: one row per library/model pair.\n- `library_summary.tsv.gz`: aggregate counts by library.\n- `summary.tsv.gz`: overall counts.\n- `run.log`: processing log.\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize legacy/current GMT inventories from a paired-GMT manifest.")
    parser.add_argument("--manifest", type=Path, required=True, help="TSV with library_id, model_id, legacy_gmt, current_gmt; name_mapping is optional.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--legacy-root", type=Path, help="Fallback basename search root; defaults to legacy_gmts next to the manifest.")
    parser.add_argument("--current-root", type=Path, help="Fallback basename search root; defaults to current_gmts next to the manifest.")
    parser.add_argument("--mapping-root", type=Path, help="Fallback mapping basename search root; defaults to reference_mappings next to the manifest.")
    args = parser.parse_args(argv)
    try:
        result = create_legacy_current_summary(args.manifest, args.output_dir, legacy_root=args.legacy_root, current_root=args.current_root, mapping_root=args.mapping_root, command=" ".join(sys.argv))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
