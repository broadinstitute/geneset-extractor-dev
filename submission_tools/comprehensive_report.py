#!/usr/bin/env python3
"""Selection-aware, wrapper-side gene-set reporting contract and renderer.

This module deliberately consumes final GMTs and optional DAPPER sidecars.  It
does not construct gene sets or mutate DIG.  Its on-disk metric artifacts are
versioned so ``render`` can combine completed library runs without rereading
the GMT inputs.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import html
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

from .gmt_compile import compile_gmts, discover_model_gmts
from .postrun_report import read_gmt


SCHEMA_VERSION = "1.0"
STREAMING_MIN_BYTES = 128 * 1024 * 1024
LOG = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _json_dump(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _write_tsv_gz(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0]) if rows else []
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _path(value: str, manifest_dir: Path) -> Path:
    candidate = Path(value)
    return (candidate if candidate.is_absolute() else manifest_dir / candidate).resolve()


def _resolve_tsv_path(recorded: str, root: Path | None, label: str) -> Path:
    """Resolve a current path or its unique basename below an explicit root."""
    candidate = Path(recorded)
    if candidate.is_file():
        return candidate.resolve()
    if root is None:
        raise ValueError(f"{label} does not exist and no fallback root was provided: {recorded}")
    matches = sorted(root.rglob(candidate.name))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {candidate.name!r} beneath {root} for {label}, found {len(matches)}")
    return matches[0].resolve()


def _portable_path(path: Path, manifest_dir: Path) -> str:
    try:
        return str(path.relative_to(manifest_dir))
    except ValueError:
        return str(path)


def _filename_id(path: Path, fallback: str) -> str:
    """Make a stable human-readable identifier from a filename."""
    candidate = path.name
    for suffix in (".gmt.gz", ".gmt", ".tsv.gz", ".tsv", ".txt"):
        if candidate.endswith(suffix):
            candidate = candidate[: -len(suffix)]
            break
    normalized = "".join(character if character.isalnum() or character in "_.-" else "_" for character in candidate).strip("_.-")
    return normalized or fallback


def _discover_model_ids(run_root: Path) -> list[str]:
    models: set[str] = set()
    for path in run_root.rglob("genesets.gmt"):
        if not path.is_file() or not any(part in {"extractor", "tissue_extractor"} for part in path.parts):
            continue
        parts = path.parts
        for index, part in enumerate(parts[:-1]):
            if part in {"models", "tissue_models"} and index + 1 < len(parts):
                models.add(parts[index + 1])
    return sorted(models)


def _unique_provenance_for_model(run_root: Path, model_id: str) -> str | None:
    """Return a sidecar only when all selected GMTs identify one candidate."""
    candidates: set[Path] = set()
    for source in discover_model_gmts(run_root, model_id):
        for name in ("geneset.provenance.dapper.yaml", "geneset.provenance.yaml"):
            candidate = source.parent / name
            if candidate.is_file():
                candidates.add(candidate.resolve())
    return str(next(iter(candidates))) if len(candidates) == 1 else None


def discover_run_root_manifest(run_root: Path, legacy_tsv: Path | None, output_path: Path, *, library_id: str, legacy_root: Path | None = None, mapping_root: Path | None = None, duplicate_policy: str = "prefix_source") -> dict[str, Any]:
    """Build a report manifest whose outputs compile from one completed run root.

    ``current_gmt`` is intentionally not part of this contract: the current
    comparison artifact is compiled from the selected model's final GMTs.
    """
    run_root, output_path = run_root.resolve(), output_path.resolve()
    if not run_root.is_dir():
        raise ValueError(f"run root is not a directory: {run_root}")
    selected_library = _safe_id(library_id, "library_id")
    references_by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if legacy_tsv is not None:
        legacy_tsv = legacy_tsv.resolve()
        root = legacy_tsv.parent
        legacy_root = (legacy_root or root / "legacy_gmts").resolve()
        mapping_root = (mapping_root or root / "reference_mappings").resolve()
        with legacy_tsv.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            required = {"library_id", "model_id", "legacy_gmt"}
            if not reader.fieldnames or not required <= set(reader.fieldnames):
                raise ValueError("legacy TSV must contain library_id, model_id, and legacy_gmt columns; current_gmt is not needed")
            for line_number, row in enumerate(reader, 2):
                if str(row.get("library_id") or "").strip() != selected_library:
                    continue
                model_id = _safe_id(row.get("model_id"), "model_id")
                legacy = _resolve_tsv_path(str(row.get("legacy_gmt") or ""), legacy_root, f"legacy_gmt at line {line_number}")
                mapping_text = str(row.get("name_mapping") or "").strip()
                mapping = _resolve_tsv_path(mapping_text, mapping_root, f"name_mapping at line {line_number}") if mapping_text else None
                reference = {"reference_id": _filename_id(legacy, f"legacy{len(references_by_model[model_id]) + 1}"), "gmt": _portable_path(legacy, output_path.parent)}
                if mapping:
                    reference["name_mapping"] = _portable_path(mapping, output_path.parent)
                if any(item["reference_id"] == reference["reference_id"] for item in references_by_model[model_id]):
                    raise ValueError(f"duplicate legacy reference ID for {selected_library}/{model_id}: {reference['reference_id']}")
                references_by_model[model_id].append(reference)
    discovered_models = _discover_model_ids(run_root)
    if not discovered_models:
        raise ValueError(f"no final genesets.gmt files found beneath {run_root}")
    models: list[dict[str, Any]] = []
    for model_id in discovered_models:
        output: dict[str, Any] = {"output_id": f"{selected_library}.{model_id}.compiled", "run_root": _portable_path(run_root, output_path.parent), "compile": {"duplicate_policy": duplicate_policy}, "legacy_references": references_by_model.get(model_id, [])}
        provenance = _unique_provenance_for_model(run_root, model_id)
        if provenance:
            output["provenance"] = _portable_path(Path(provenance), output_path.parent)
        models.append({"model_id": model_id, "outputs": [output]})
    manifest = {"schema_version": SCHEMA_VERSION, "generated_from": str(legacy_tsv) if legacy_tsv else "", "run_root": str(run_root), "libraries": [{"library_id": selected_library, "models": models}]}
    _json_dump(output_path, manifest)
    return {"manifest": str(output_path), "library_id": selected_library, "model_count": len(models), "legacy_reference_count": sum(len(item["legacy_references"]) for model in models for item in model["outputs"])}


def convert_legacy_current_tsv(input_path: Path, output_path: Path, *, legacy_root: Path | None = None, current_root: Path | None = None, mapping_root: Path | None = None) -> dict[str, Any]:
    """Convert the established legacy/current TSV into a report JSON manifest."""
    input_path, output_path = input_path.resolve(), output_path.resolve()
    root = input_path.parent
    legacy_root = (legacy_root or root / "legacy_gmts").resolve()
    current_root = (current_root or root / "current_gmts").resolve()
    mapping_root = (mapping_root or root / "reference_mappings").resolve()
    with input_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = {"library_id", "model_id", "legacy_gmt", "current_gmt"}
        if not reader.fieldnames or not required <= set(reader.fieldnames):
            raise ValueError("TSV must contain library_id, model_id, legacy_gmt, and current_gmt columns")
        groups: dict[tuple[str, str, str], dict[str, Any]] = {}
        for line_number, row in enumerate(reader, 2):
            library_id, model_id = _safe_id(row.get("library_id"), "library_id"), _safe_id(row.get("model_id"), "model_id")
            legacy = _resolve_tsv_path(str(row.get("legacy_gmt") or ""), legacy_root, f"legacy_gmt at line {line_number}")
            current = _resolve_tsv_path(str(row.get("current_gmt") or ""), current_root, f"current_gmt at line {line_number}")
            mapping_text = str(row.get("name_mapping") or "").strip()
            mapping = _resolve_tsv_path(mapping_text, mapping_root, f"name_mapping at line {line_number}") if mapping_text else None
            key = (library_id, model_id, str(current))
            group = groups.setdefault(key, {"library_id": library_id, "model_id": model_id, "gmt": current, "references": []})
            reference = {"reference_id": f"legacy{len(group['references']) + 1}", "gmt": legacy}
            if mapping is not None:
                reference["name_mapping"] = mapping
            if any(str(existing["gmt"]) == str(legacy) for existing in group["references"]):
                raise ValueError(f"duplicate legacy/current pairing at {input_path}:{line_number}")
            group["references"].append(reference)
    libraries: dict[str, dict[str, Any]] = {}
    for index, group in enumerate(sorted(groups.values(), key=lambda item: (item["library_id"], item["model_id"], str(item["gmt"]))), 1):
        library = libraries.setdefault(group["library_id"], {"library_id": group["library_id"], "models": {}})
        model = library["models"].setdefault(group["model_id"], {"model_id": group["model_id"], "outputs": []})
        output = {"output_id": _filename_id(group["gmt"], f"output{len(model['outputs']) + 1}"), "gmt": _portable_path(group["gmt"], output_path.parent), "legacy_references": []}
        for reference in group["references"]:
            item = {"reference_id": _filename_id(reference["gmt"], reference["reference_id"]), "gmt": _portable_path(reference["gmt"], output_path.parent)}
            if reference.get("name_mapping"):
                item["name_mapping"] = _portable_path(reference["name_mapping"], output_path.parent)
            output["legacy_references"].append(item)
        model["outputs"].append(output)
    manifest = {"schema_version": SCHEMA_VERSION, "generated_from": str(input_path), "libraries": [{"library_id": library["library_id"], "models": list(library["models"].values())} for _, library in sorted(libraries.items())]}
    _json_dump(output_path, manifest)
    return {"manifest": str(output_path), "library_count": len(libraries), "model_output_count": len(groups)}


def _load_manifest(path: Path) -> dict[str, Any]:
    """Load JSON, with YAML available only when PyYAML is already installed."""
    text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ValueError("manifest must be JSON; install PyYAML to use YAML") from exc
        payload = yaml.safe_load(text)
    if not isinstance(payload, dict) or not isinstance(payload.get("libraries"), list):
        raise ValueError("manifest must be an object with a libraries list")
    return payload


def _safe_id(value: object, label: str) -> str:
    text = str(value or "").strip()
    if not text or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-" for character in text):
        raise ValueError(f"{label} must contain only letters, digits, dot, underscore, or hyphen")
    return text


def _mapping(path: Path | None) -> tuple[dict[str, str], int]:
    if path is None:
        return {}, 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = set(reader.fieldnames or [])
        target = "regenerated_set_name" if "regenerated_set_name" in fields else "generated_set_name"
        if not {"legacy_set_name", target} <= fields:
            raise ValueError(f"mapping {path} must contain legacy_set_name and regenerated_set_name (or generated_set_name)")
        pairs: dict[str, str] = {}
        generated_names: set[str] = set()
        unmapped_count = 0
        for row in reader:
            legacy, generated = str(row["legacy_set_name"] or "").strip(), str(row[target] or "").strip()
            if not legacy or not generated:
                unmapped_count += 1
                continue
            if legacy in pairs or generated in generated_names:
                raise ValueError(f"mapping {path} must be one-to-one among nonblank names")
            pairs[legacy] = generated
            generated_names.add(generated)
    return pairs, unmapped_count


def _tasks(manifest_path: Path, libraries: set[str] | None, models: set[str] | None) -> list[dict[str, Any]]:
    manifest = _load_manifest(manifest_path)
    root = manifest_path.parent.resolve()
    tasks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for library in manifest["libraries"]:
        if not isinstance(library, dict):
            raise ValueError("each library must be an object")
        library_id = _safe_id(library.get("library_id", library.get("id")), "library_id")
        if libraries is not None and library_id not in libraries:
            continue
        for model in library.get("models", []):
            if not isinstance(model, dict):
                raise ValueError(f"{library_id}: each model must be an object")
            model_id = _safe_id(model.get("model_id", model.get("id")), "model_id")
            if models is not None and model_id not in models:
                continue
            outputs = model.get("outputs", [])
            if not outputs:
                raise ValueError(f"{library_id}/{model_id} has no outputs")
            for output_index, output in enumerate(outputs, 1):
                if not isinstance(output, dict) or (not output.get("gmt") and not output.get("run_root")):
                    raise ValueError(f"{library_id}/{model_id}: each output requires gmt or run_root")
                output_id = _safe_id(output.get("output_id", f"output{output_index}"), "output_id")
                current = _path(str(output["gmt"]), root) if output.get("gmt") else None
                compile_root = _path(str(output["run_root"]), root) if output.get("run_root") else None
                compile_options = output.get("compile", {}) if compile_root else {}
                if compile_root and not isinstance(compile_options, dict):
                    raise ValueError(f"{library_id}/{model_id}/{output_id}: compile must be an object")
                provenance_value = output.get("provenance", model.get("provenance"))
                provenance = _path(str(provenance_value), root) if provenance_value else None
                references = output.get("legacy_references", model.get("legacy_references", []))
                if references is None:
                    references = []
                if not isinstance(references, list):
                    raise ValueError(f"{library_id}/{model_id}/{output_id}: legacy_references must be a list")
                # A model without a legacy reference still needs one inventory task.
                references = references or [None]
                for reference_index, reference in enumerate(references, 1):
                    if reference is not None and (not isinstance(reference, dict) or not reference.get("gmt")):
                        raise ValueError(f"{library_id}/{model_id}/{output_id}: each legacy reference requires gmt")
                    reference_id = "none" if reference is None else _safe_id(reference.get("reference_id", f"reference{reference_index}"), "reference_id")
                    task_id = f"{library_id}.{model_id}.{output_id}.{reference_id}"
                    if task_id in seen:
                        raise ValueError(f"duplicate task identity {task_id}")
                    seen.add(task_id)
                    tasks.append({
                        "task_id": task_id, "library_id": library_id, "model_id": model_id, "output_id": output_id,
                        # Keep this separately from task_id: reference identifiers may
                        # legitimately contain periods (for example a GMT filename).
                        "reference_id": reference_id,
                        "generated_gmt": str(current) if current else None,
                        "compile_run_root": str(compile_root) if compile_root else None,
                        "compile_duplicate_policy": str(compile_options.get("duplicate_policy", "fail")),
                        "legacy_gmt": str(_path(str(reference["gmt"]), root)) if reference else None,
                        "name_mapping": str(_path(str(reference["name_mapping"]), root)) if reference and reference.get("name_mapping") else None,
                        "provenance": str(provenance) if provenance else None,
                    })
    if not tasks:
        raise ValueError("selection contains no outputs")
    return sorted(tasks, key=lambda item: item["task_id"])


def _inventory(sets: dict[str, set[str]], warning_count: int) -> dict[str, Any]:
    sizes = sorted(len(genes) for genes in sets.values())
    return {
        "gene_set_count": len(sets), "membership_count": sum(sizes), "unique_gene_count": len(set().union(*sets.values())) if sets else 0,
        "empty_set_count": sum(size == 0 for size in sizes), "min_set_size": min(sizes) if sizes else None,
        "median_set_size": median(sizes) if sizes else None, "max_set_size": max(sizes) if sizes else None,
        "warning_count": warning_count,
    }


def _compare(legacy: dict[str, set[str]], generated: dict[str, set[str]], mapping: dict[str, str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    direct_names = set(legacy) & set(generated)
    pairs = mapping if mapping else {name: name for name in direct_names}
    unknown_legacy = set(pairs) - set(legacy)
    unknown_generated = set(pairs.values()) - set(generated)
    if unknown_legacy or unknown_generated:
        raise ValueError(f"mapping names do not match GMTs: legacy={sorted(unknown_legacy)[:3]}, generated={sorted(unknown_generated)[:3]}")
    details: list[dict[str, Any]] = []
    compared: list[dict[str, Any]] = []
    for legacy_name, generated_name in sorted(pairs.items()):
        left, right = legacy[legacy_name], generated[generated_name]
        shared, union = left & right, left | right
        row = {"legacy_set_name": legacy_name, "generated_set_name": generated_name, "status": "matched", "legacy_size": len(left), "generated_size": len(right), "intersection": len(shared), "legacy_only": len(left - right), "generated_only": len(right - left), "recall": _ratio(len(shared), len(left)), "precision": _ratio(len(shared), len(right)), "jaccard": _ratio(len(shared), len(union)), "exact_match": left == right}
        details.append(row); compared.append(row)
    mapped_legacy, mapped_generated = set(pairs), set(pairs.values())
    for name in sorted(set(legacy) - mapped_legacy):
        details.append({"legacy_set_name": name, "generated_set_name": "", "status": "legacy_only", "legacy_size": len(legacy[name]), "generated_size": None, "intersection": 0, "legacy_only": len(legacy[name]), "generated_only": None, "recall": None, "precision": None, "jaccard": None, "exact_match": None})
    for name in sorted(set(generated) - mapped_generated):
        details.append({"legacy_set_name": "", "generated_set_name": name, "status": "generated_only", "legacy_size": None, "generated_size": len(generated[name]), "intersection": 0, "legacy_only": None, "generated_only": len(generated[name]), "recall": None, "precision": None, "jaccard": None, "exact_match": None})
    legacy_pairs = {(legacy_name, gene) for legacy_name, generated_name in pairs.items() for gene in legacy[legacy_name]}
    generated_pairs = {(legacy_name, gene) for legacy_name, generated_name in pairs.items() for gene in generated[generated_name]}
    overlap = legacy_pairs & generated_pairs
    jaccards = [float(row["jaccard"]) for row in compared if row["jaccard"] is not None]
    exact_count = sum(bool(row["exact_match"]) for row in compared)
    return {
        "comparison_status": "available", "comparison_method": "name_mapping" if mapping else "direct_set_name",
        "legacy_set_count": len(legacy), "generated_set_count": len(generated), "matched_set_count": len(compared),
        "legacy_only_set_count": len(set(legacy) - mapped_legacy), "generated_only_set_count": len(set(generated) - mapped_generated),
        "direct_name_match_count": len(direct_names), "set_name_recall": _ratio(len(direct_names), len(legacy)), "set_name_precision": _ratio(len(direct_names), len(generated)),
        "legacy_membership_count": len(legacy_pairs), "generated_membership_count": len(generated_pairs), "membership_intersection": len(overlap),
        "membership_recall": _ratio(len(overlap), len(legacy_pairs)), "membership_precision": _ratio(len(overlap), len(generated_pairs)), "membership_jaccard": _ratio(len(overlap), len(legacy_pairs | generated_pairs)),
        "mean_set_jaccard": mean(jaccards) if jaccards else None, "median_set_jaccard": median(jaccards) if jaccards else None,
        "exact_match_count": exact_count, "exact_match_rate": _ratio(exact_count, len(compared)), "valid_jaccard_count": len(jaccards),
    }, details


def _scan_gmt_to_sqlite(database: sqlite3.Connection, table: str, path: Path, *, collect_genes: bool) -> int:
    """Index GMT term offsets and sizes using disk, not Python term objects."""
    database.execute(f"CREATE TABLE {table} (name TEXT PRIMARY KEY, offset INTEGER NOT NULL, size INTEGER NOT NULL)")
    if collect_genes:
        database.execute("CREATE TABLE generated_genes (gene TEXT PRIMARY KEY)")
    malformed = 0
    entries: list[tuple[str, int, int]] = []
    genes_batch: list[tuple[str]] = []
    with path.open("rb") as handle:
        while True:
            offset = handle.tell()
            line = handle.readline()
            if not line:
                break
            if not line.strip():
                continue
            fields = line.decode("utf-8").rstrip("\r\n").split("\t")
            if len(fields) < 3 or not fields[0].strip():
                malformed += 1
                continue
            members = {gene.strip() for gene in fields[2:] if gene.strip()}
            entries.append((fields[0].strip(), offset, len(members)))
            if collect_genes:
                genes_batch.extend((gene,) for gene in members)
            if len(entries) >= 10_000:
                database.executemany(f"INSERT OR IGNORE INTO {table} VALUES (?, ?, ?)", entries); entries.clear()
                if genes_batch:
                    database.executemany("INSERT OR IGNORE INTO generated_genes VALUES (?)", genes_batch); genes_batch.clear()
                database.commit()
    if entries:
        database.executemany(f"INSERT OR IGNORE INTO {table} VALUES (?, ?, ?)", entries)
    if genes_batch:
        database.executemany("INSERT OR IGNORE INTO generated_genes VALUES (?)", genes_batch)
    database.commit()
    return malformed


def _sqlite_inventory(database: sqlite3.Connection, table: str, malformed: int, *, generated: bool) -> dict[str, Any]:
    count, memberships, empty, minimum, maximum = database.execute(f"SELECT COUNT(*), COALESCE(SUM(size), 0), COALESCE(SUM(size = 0), 0), MIN(size), MAX(size) FROM {table}").fetchone()
    median_size: float | None = None
    if count:
        middle = (count - 1) // 2
        values = [row[0] for row in database.execute(f"SELECT size FROM {table} ORDER BY size LIMIT ? OFFSET ?", (2 if count % 2 == 0 else 1, middle))]
        median_size = sum(values) / len(values)
    unique_gene_count = database.execute("SELECT COUNT(*) FROM generated_genes").fetchone()[0] if generated else None
    return {"gene_set_count": count, "membership_count": memberships, "unique_gene_count": unique_gene_count, "empty_set_count": empty, "min_set_size": minimum, "median_set_size": median_size, "max_set_size": maximum, "warning_count": malformed + (database.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] - count)}


def _read_record_at(handle: Any, offset: int) -> tuple[str, set[str]]:
    handle.seek(offset)
    fields = handle.readline().decode("utf-8").rstrip("\r\n").split("\t")
    return fields[0].strip(), {gene.strip() for gene in fields[2:] if gene.strip()}


def _streaming_comparison(legacy_path: Path, generated_path: Path, mapping_path: Path | None, metrics_dir: Path, task_id: str) -> tuple[dict[str, Any], dict[str, Any], int]:
    """Compute a large GMT comparison with SQLite indexes and streamed rows."""
    with tempfile.TemporaryDirectory(prefix="comprehensive_report_") as temporary:
        database = sqlite3.connect(Path(temporary) / "comparison.sqlite")
        database.execute("PRAGMA journal_mode=OFF"); database.execute("PRAGMA synchronous=OFF")
        legacy_malformed = _scan_gmt_to_sqlite(database, "legacy", legacy_path, collect_genes=False)
        generated_malformed = _scan_gmt_to_sqlite(database, "generated", generated_path, collect_genes=True)
        legacy_inventory = _sqlite_inventory(database, "legacy", legacy_malformed, generated=False)
        generated_inventory = _sqlite_inventory(database, "generated", generated_malformed, generated=True)
        with gzip.open(metrics_dir / f"{task_id}.genes.txt.gz", "wt", encoding="utf-8") as handle:
            for (gene,) in database.execute("SELECT gene FROM generated_genes ORDER BY gene"):
                handle.write(gene + "\n")
        database.execute("CREATE TABLE mapping (legacy_name TEXT PRIMARY KEY, generated_name TEXT UNIQUE)")
        unmapped_mapping_rows = 0
        if mapping_path is not None:
            with mapping_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle, delimiter="\t")
                fields = set(reader.fieldnames or [])
                target = "regenerated_set_name" if "regenerated_set_name" in fields else "generated_set_name"
                if not {"legacy_set_name", target} <= fields:
                    raise ValueError(f"mapping {mapping_path} must contain legacy_set_name and regenerated_set_name (or generated_set_name)")
                batch: list[tuple[str, str]] = []
                for row in reader:
                    legacy_name, generated_name = str(row["legacy_set_name"] or "").strip(), str(row[target] or "").strip()
                    if not legacy_name or not generated_name:
                        unmapped_mapping_rows += 1; continue
                    batch.append((legacy_name, generated_name))
                    if len(batch) >= 10_000:
                        try: database.executemany("INSERT INTO mapping VALUES (?, ?)", batch)
                        except sqlite3.IntegrityError as exc: raise ValueError(f"mapping {mapping_path} must be one-to-one among nonblank names") from exc
                        batch.clear(); database.commit()
                if batch:
                    try: database.executemany("INSERT INTO mapping VALUES (?, ?)", batch)
                    except sqlite3.IntegrityError as exc: raise ValueError(f"mapping {mapping_path} must be one-to-one among nonblank names") from exc
        mapped_count = database.execute("SELECT COUNT(*) FROM mapping").fetchone()[0]
        database.execute("CREATE TABLE pairs (legacy_name TEXT PRIMARY KEY, generated_name TEXT UNIQUE)")
        if mapped_count:
            unknown_legacy, unknown_generated = database.execute("SELECT SUM(l.name IS NULL), SUM(g.name IS NULL) FROM mapping m LEFT JOIN legacy l ON l.name = m.legacy_name LEFT JOIN generated g ON g.name = m.generated_name").fetchone()
            if unknown_legacy or unknown_generated:
                raise ValueError(f"mapping {mapping_path} contains names absent from the compared GMTs: legacy={unknown_legacy or 0}, generated={unknown_generated or 0}")
            database.execute("INSERT INTO pairs SELECT m.legacy_name, m.generated_name FROM mapping m")
            method = "name_mapping"
        else:
            database.execute("INSERT INTO pairs SELECT l.name, l.name FROM legacy l INNER JOIN generated g ON g.name = l.name")
            method = "direct_set_name"
        database.execute("CREATE TABLE jaccards (value REAL)")
        per_term_path = metrics_dir / f"{task_id}.per_term.tsv.gz"
        fields = ["legacy_set_name", "generated_set_name", "status", "legacy_size", "generated_size", "intersection", "legacy_only", "generated_only", "recall", "precision", "jaccard", "exact_match"]
        matched = exact = legacy_memberships = generated_memberships = intersection_total = 0
        jaccard_sum = 0.0; valid_jaccards = 0; jaccard_batch: list[tuple[float]] = []
        with gzip.open(per_term_path, "wt", encoding="utf-8", newline="") as output, legacy_path.open("rb") as legacy_handle, generated_path.open("rb") as generated_handle:
            writer = csv.DictWriter(output, fieldnames=fields, delimiter="\t", lineterminator="\n"); writer.writeheader()
            query = "SELECT p.legacy_name, p.generated_name, l.offset, g.offset FROM pairs p JOIN legacy l ON l.name=p.legacy_name JOIN generated g ON g.name=p.generated_name ORDER BY p.legacy_name"
            for legacy_name, generated_name, legacy_offset, generated_offset in database.execute(query):
                _, left = _read_record_at(legacy_handle, legacy_offset); _, right = _read_record_at(generated_handle, generated_offset)
                shared, union = left & right, left | right
                recall, precision, jaccard = _ratio(len(shared), len(left)), _ratio(len(shared), len(right)), _ratio(len(shared), len(union))
                writer.writerow({"legacy_set_name": legacy_name, "generated_set_name": generated_name, "status": "matched", "legacy_size": len(left), "generated_size": len(right), "intersection": len(shared), "legacy_only": len(left - right), "generated_only": len(right - left), "recall": recall, "precision": precision, "jaccard": jaccard, "exact_match": left == right})
                matched += 1; exact += int(left == right); legacy_memberships += len(left); generated_memberships += len(right); intersection_total += len(shared)
                if jaccard is not None:
                    jaccard_sum += jaccard; valid_jaccards += 1; jaccard_batch.append((jaccard,))
                if len(jaccard_batch) >= 10_000:
                    database.executemany("INSERT INTO jaccards VALUES (?)", jaccard_batch); jaccard_batch.clear(); database.commit()
            if jaccard_batch: database.executemany("INSERT INTO jaccards VALUES (?)", jaccard_batch); database.commit()
            for name, size in database.execute("SELECT l.name, l.size FROM legacy l LEFT JOIN pairs p ON p.legacy_name=l.name WHERE p.legacy_name IS NULL ORDER BY l.name"):
                writer.writerow({"legacy_set_name": name, "generated_set_name": "", "status": "legacy_only", "legacy_size": size, "generated_size": None, "intersection": 0, "legacy_only": size, "generated_only": None, "recall": None, "precision": None, "jaccard": None, "exact_match": None})
            for name, size in database.execute("SELECT g.name, g.size FROM generated g LEFT JOIN pairs p ON p.generated_name=g.name WHERE p.generated_name IS NULL ORDER BY g.name"):
                writer.writerow({"legacy_set_name": "", "generated_set_name": name, "status": "generated_only", "legacy_size": None, "generated_size": size, "intersection": 0, "legacy_only": None, "generated_only": size, "recall": None, "precision": None, "jaccard": None, "exact_match": None})
        direct_name_matches = database.execute("SELECT COUNT(*) FROM legacy l INNER JOIN generated g ON g.name=l.name").fetchone()[0]
        if valid_jaccards:
            offset = (valid_jaccards - 1) // 2
            values = [row[0] for row in database.execute("SELECT value FROM jaccards ORDER BY value LIMIT ? OFFSET ?", (2 if valid_jaccards % 2 == 0 else 1, offset))]
            median_jaccard: float | None = sum(values) / len(values)
        else:
            median_jaccard = None
        comparison = {"comparison_status": "available", "comparison_method": method, "legacy_set_count": legacy_inventory["gene_set_count"], "generated_set_count": generated_inventory["gene_set_count"], "matched_set_count": matched, "legacy_only_set_count": legacy_inventory["gene_set_count"] - matched, "generated_only_set_count": generated_inventory["gene_set_count"] - matched, "direct_name_match_count": direct_name_matches, "set_name_recall": _ratio(direct_name_matches, legacy_inventory["gene_set_count"]), "set_name_precision": _ratio(direct_name_matches, generated_inventory["gene_set_count"]), "legacy_membership_count": legacy_memberships, "generated_membership_count": generated_memberships, "membership_intersection": intersection_total, "membership_recall": _ratio(intersection_total, legacy_memberships), "membership_precision": _ratio(intersection_total, generated_memberships), "membership_jaccard": _ratio(intersection_total, legacy_memberships + generated_memberships - intersection_total), "mean_set_jaccard": jaccard_sum / valid_jaccards if valid_jaccards else None, "median_set_jaccard": median_jaccard, "exact_match_count": exact, "exact_match_rate": _ratio(exact, matched), "valid_jaccard_count": valid_jaccards, "unmapped_mapping_row_count": unmapped_mapping_rows}
        database.close()
    return generated_inventory, comparison, legacy_malformed


def _provenance(path_text: str | None, validator: str | None) -> dict[str, Any]:
    if not path_text:
        return {"provenance_status": "NOT_RUN", "provenance_present": False, "provenance_path": "", "provenance_message": "no sidecar declared"}
    path = Path(path_text)
    if not path.is_file():
        return {"provenance_status": "ERROR", "provenance_present": False, "provenance_path": str(path), "provenance_message": "declared sidecar is missing"}
    if not validator:
        return {"provenance_status": "NOT_RUN", "provenance_present": True, "provenance_path": str(path), "provenance_message": "no DAPPER validator configured"}
    try:
        completed = subprocess.run([validator, str(path)], check=False, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"provenance_status": "ERROR", "provenance_present": True, "provenance_path": str(path), "provenance_message": str(exc)}
    return {"provenance_status": "PASS" if completed.returncode == 0 else "FAIL", "provenance_present": True, "provenance_path": str(path), "provenance_message": (completed.stdout + completed.stderr).strip()[:2000]}


def _compute(task: dict[str, Any], metrics_dir: Path, validator: str | None) -> dict[str, Any]:
    compile_manifest: list[dict[str, object]] | None = None
    if task.get("compile_run_root"):
        generated_path = metrics_dir / f"{task['task_id']}.compiled.gmt"
        compile_manifest, _ = compile_gmts(Path(str(task["compile_run_root"])), str(task["model_id"]), generated_path, duplicate_policy=str(task.get("compile_duplicate_policy", "fail")))
    else:
        generated_path = Path(str(task["generated_gmt"]))
    if not generated_path.is_file():
        raise ValueError(f"generated GMT does not exist: {generated_path}")
    legacy_path = Path(str(task["legacy_gmt"])) if task.get("legacy_gmt") else None
    if legacy_path is not None and not legacy_path.is_file():
        raise ValueError(f"legacy GMT does not exist: {legacy_path}")
    streaming = generated_path.stat().st_size >= STREAMING_MIN_BYTES or (legacy_path is not None and legacy_path.stat().st_size >= STREAMING_MIN_BYTES)
    if streaming and legacy_path is not None:
        generated_inventory, comparison, legacy_warning_count = _streaming_comparison(legacy_path, generated_path, Path(str(task["name_mapping"])) if task.get("name_mapping") else None, metrics_dir, str(task["task_id"]))
        warnings = ["large-GMT streaming mode used"]
        comparison.update({"legacy_gmt": str(legacy_path), "legacy_sha256": _sha256(legacy_path), "legacy_bytes": legacy_path.stat().st_size, "legacy_warning_count": legacy_warning_count, "name_mapping": str(task.get("name_mapping") or "")})
    elif streaming:
        generated_inventory, generated_warning_count = _streaming_generated_inventory(generated_path, metrics_dir, str(task["task_id"]))
        warnings = ["large-GMT streaming mode used"]
        comparison = {"comparison_status": "not_applicable", "comparison_method": "none"}
    else:
        generated, warnings = read_gmt(generated_path)
        generated_inventory = _inventory(generated, len(warnings))
        if legacy_path is not None:
            legacy, legacy_warnings = read_gmt(legacy_path)
            mapping_path = Path(str(task["name_mapping"])) if task.get("name_mapping") else None
            mapping, unmapped_mapping_row_count = _mapping(mapping_path)
            comparison, details = _compare(legacy, generated, mapping)
            comparison.update({"legacy_gmt": str(legacy_path), "legacy_sha256": _sha256(legacy_path), "legacy_bytes": legacy_path.stat().st_size, "legacy_warning_count": len(legacy_warnings), "name_mapping": str(mapping_path or ""), "unmapped_mapping_row_count": unmapped_mapping_row_count})
            _write_tsv_gz(metrics_dir / f"{task['task_id']}.per_term.tsv.gz", details)
        else:
            comparison = {"comparison_status": "not_applicable", "comparison_method": "none"}
    result: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "status": "success", "completed_at_utc": _now(), **task,
        "generated_sha256": _sha256(generated_path), "generated_bytes": generated_path.stat().st_size,
        "generated_inventory": generated_inventory, "warnings": warnings,
        "provenance": _provenance(task.get("provenance"), validator)}
    result["generated_gmt"] = str(generated_path)
    if compile_manifest is not None:
        result["compile_source_manifest"] = compile_manifest
        result["compiled_duplicate_term_count"] = sum(int(row["duplicate_term_count"]) for row in compile_manifest)
        result["compiled_renamed_term_count"] = sum(int(row["renamed_term_count"]) for row in compile_manifest)
    if not streaming:
        genes_path = metrics_dir / f"{task['task_id']}.genes.txt.gz"
        with gzip.open(genes_path, "wt", encoding="utf-8") as handle:
            for gene in sorted(set().union(*generated.values()) if generated else set()):
                handle.write(gene + "\n")
    result["comparison"] = comparison
    return result


def _write_status(path: Path, task: dict[str, Any], status: str, message: str = "") -> None:
    _json_dump(path, {"schema_version": SCHEMA_VERSION, "task_id": task["task_id"], "status": status, "updated_at_utc": _now(), "message": message})


def plan(manifest: Path, output_dir: Path, libraries: set[str] | None, models: set[str] | None) -> list[dict[str, Any]]:
    tasks = _tasks(manifest.resolve(), libraries, models)
    output_dir.mkdir(parents=True, exist_ok=True)
    _json_dump(output_dir / "manifest.json", {"schema_version": SCHEMA_VERSION, "created_at_utc": _now(), "source_manifest": str(manifest.resolve()), "tasks": tasks})
    tasks_dir = output_dir / "tasks"; tasks_dir.mkdir(exist_ok=True)
    for index, task in enumerate(tasks, 1):
        _json_dump(tasks_dir / f"{index:05d}.json", task)
    return tasks


def run(manifest: Path, output_dir: Path, libraries: set[str] | None, models: set[str] | None, validator: str | None, *, resume: bool = False) -> list[dict[str, Any]]:
    tasks = plan(manifest, output_dir, libraries, models)
    metrics_dir, status_dir = output_dir / "metrics", output_dir / "status"
    metrics_dir.mkdir(exist_ok=True); status_dir.mkdir(exist_ok=True)
    results: list[dict[str, Any]] = []
    for task in tasks:
        metric_path = metrics_dir / f"{task['task_id']}.json"
        if resume and metric_path.is_file():
            existing = json.loads(metric_path.read_text(encoding="utf-8"))
            if existing.get("schema_version") == SCHEMA_VERSION and existing.get("status") == "success":
                results.append(existing); continue
        _write_status(status_dir / f"{task['task_id']}.json", task, "running")
        try:
            result = _compute(task, metrics_dir, validator)
            _json_dump(metric_path, result)
            _write_status(status_dir / f"{task['task_id']}.json", task, "success")
            results.append(result)
        except (OSError, ValueError) as exc:
            _write_status(status_dir / f"{task['task_id']}.json", task, "failed", str(exc))
            raise
    render(output_dir, libraries, models, allow_partial=False)
    return results


def _load_results(results_root: Path, libraries: set[str] | None, models: set[str] | None, allow_partial: bool) -> list[dict[str, Any]]:
    manifest_path = results_root / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"missing run manifest: {manifest_path}")
    run_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tasks = [task for task in run_manifest.get("tasks", []) if (libraries is None or task["library_id"] in libraries) and (models is None or task["model_id"] in models)]
    results: list[dict[str, Any]] = []
    missing: list[str] = []
    for task in tasks:
        path = results_root / "metrics" / f"{task['task_id']}.json"
        if not path.is_file():
            missing.append(task["task_id"]); continue
        result = json.loads(path.read_text(encoding="utf-8"))
        if result.get("schema_version") != SCHEMA_VERSION or result.get("status") != "success":
            missing.append(task["task_id"]); continue
        results.append(result)
    if missing and not allow_partial:
        raise ValueError(f"missing or incompatible metric artifacts: {', '.join(missing[:8])}")
    return results


def _format(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _table(rows: list[dict[str, Any]], fields: list[str]) -> str:
    head = "".join(f"<th>{html.escape(field.replace('_', ' '))}</th>" for field in fields)
    body = "".join("<tr>" + "".join(f"<td>{html.escape(_format(row.get(field)))}</td>" for field in fields) + "</tr>" for row in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render(results_root: Path, libraries: set[str] | None, models: set[str] | None, allow_partial: bool) -> dict[str, Any]:
    results_root = results_root.resolve()
    results = _load_results(results_root, libraries, models, allow_partial)
    rendered = results_root / "rendered"; rendered.mkdir(exist_ok=True)
    rows: list[dict[str, Any]] = []
    union_genes: set[str] = set()
    for result in results:
        with gzip.open(results_root / "metrics" / f"{result['task_id']}.genes.txt.gz", "rt", encoding="utf-8") as handle:
            union_genes.update(line.rstrip("\n") for line in handle)
        inventory, comparison, provenance = result["generated_inventory"], result["comparison"], result["provenance"]
        rows.append({"library_id": result["library_id"], "model_id": result["model_id"], "output_id": result["output_id"], "reference_id": result.get("reference_id", result["task_id"].rsplit(".", 1)[1]), "gene_set_count": inventory["gene_set_count"], "membership_count": inventory["membership_count"], "unique_gene_count": inventory["unique_gene_count"], "compiled_duplicate_term_count": result.get("compiled_duplicate_term_count", 0), "compiled_renamed_term_count": result.get("compiled_renamed_term_count", 0), "comparison_status": comparison["comparison_status"], "unmapped_mapping_row_count": comparison.get("unmapped_mapping_row_count", 0), "set_name_recall": comparison.get("set_name_recall"), "membership_jaccard": comparison.get("membership_jaccard"), "median_set_jaccard": comparison.get("median_set_jaccard"), "exact_match_rate": comparison.get("exact_match_rate"), "provenance_status": provenance["provenance_status"]})
    rows.sort(key=lambda row: (str(row["library_id"]), str(row["model_id"]), str(row["output_id"]), str(row["reference_id"])))
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows: grouped[str(row["library_id"])].append(row)
    library_rows = [{"library_id": library, "model_output_reference_count": len(values), "gene_set_count_sum": sum(int(value["gene_set_count"]) for value in values), "membership_count_sum": sum(int(value["membership_count"]) for value in values), "legacy_comparison_count": sum(value["comparison_status"] == "available" for value in values)} for library, values in sorted(grouped.items())]
    summary = {"schema_version": SCHEMA_VERSION, "rendered_at_utc": _now(), "library_count": len(library_rows), "model_output_reference_count": len(rows), "gene_set_count_sum": sum(int(row["gene_set_count"]) for row in rows), "membership_count_sum": sum(int(row["membership_count"]) for row in rows), "unique_gene_union_count": len(union_genes), "legacy_comparison_count": sum(row["comparison_status"] == "available" for row in rows), "provenance_present_count": sum(row["provenance_status"] != "NOT_RUN" for row in rows), "allow_partial": allow_partial}
    _json_dump(rendered / "summary.json", summary); _write_tsv_gz(rendered / "model_output_summary.tsv.gz", rows); _write_tsv_gz(rendered / "library_summary.tsv.gz", library_rows)
    fields = ["library_id", "model_id", "output_id", "reference_id", "gene_set_count", "membership_count", "unique_gene_count", "compiled_duplicate_term_count", "compiled_renamed_term_count", "comparison_status", "unmapped_mapping_row_count", "set_name_recall", "membership_jaccard", "median_set_jaccard", "exact_match_rate", "provenance_status"]
    column_definitions = {
        "library_id": "Wrapper library identifier.",
        "model_id": "Model identifier within the library.",
        "output_id": "Declared output identity; compiled run-root outputs end in `.compiled`.",
        "reference_id": "Explicit legacy-reference identity, or `none` when no legacy reference applies.",
        "gene_set_count": "Number of distinct generated term names; duplicate later records are skipped.",
        "membership_count": "Sum of unique nonblank genes within each generated gene set; the same gene in different sets is counted repeatedly.",
        "unique_gene_count": "Distinct nonblank genes across this generated output.",
        "compiled_duplicate_term_count": "Gene-set names that collided while compiling separate extractor GMTs for this output.",
        "compiled_renamed_term_count": "Colliding compiled terms renamed with a source-path prefix to preserve all source gene sets.",
        "comparison_status": "`available` for an explicit legacy comparison; `not_applicable` when no legacy reference was declared.",
        "unmapped_mapping_row_count": "Mapping rows with a blank legacy or generated name; these rows are excluded from mapped-term comparison.",
        "set_name_recall": "Exact shared term names divided by all legacy term names. This does not use renamed mappings.",
        "membership_jaccard": "Shared `(mapped legacy term, gene)` memberships divided by their union, considering only compared term pairs.",
        "median_set_jaccard": "Median per-term gene-membership Jaccard among compared pairs with a defined union.",
        "exact_match_rate": "Exactly equal gene memberships divided by compared term pairs.",
        "provenance_status": "DAPPER validation result: `PASS`, `FAIL`, `ERROR`, or `NOT_RUN`; `NOT_RUN` is not a validity claim.",
    }
    glossary_rows = [{"column": field, "meaning": column_definitions[field]} for field in fields]
    markdown = ["# Gene-set comprehensive report", "", "## Executive summary", "", *[f"- {key}: {_format(value)}" for key, value in summary.items() if key not in {"schema_version", "rendered_at_utc"}], "", "## Cross-library inventory", "", "| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    markdown.extend("| " + " | ".join(_format(row.get(field)) for field in fields) + " |" for row in rows)
    markdown.extend(["", "## Column definitions", "", "| column | meaning |", "| --- | --- |"])
    markdown.extend(f"| {row['column']} | {row['meaning']} |" for row in glossary_rows)
    markdown.extend(["", "## Method", "", "Gene-set counts and memberships are summed across output/reference task rows; `unique_gene_union_count` is deduplicated across generated outputs. Name agreement is based on exact names. Membership metrics use only explicitly mapped terms, or exact shared names when no mapping is supplied. Undefined ratios are `N/A`."])
    (rendered / "report.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    html_document = "<!doctype html><html><head><meta charset=\"utf-8\"><title>Gene-set comprehensive report</title><style>body{font:14px system-ui,sans-serif;max-width:1400px;margin:2rem auto;padding:0 1rem}table{border-collapse:collapse;width:100%;margin:1rem 0}th,td{border:1px solid #bbb;padding:.35rem;text-align:left}th{background:#eef}tr:nth-child(even){background:#fafafa}</style></head><body><h1>Gene-set comprehensive report</h1><h2>Executive summary</h2>" + _table([summary], ["library_count", "model_output_reference_count", "gene_set_count_sum", "membership_count_sum", "unique_gene_union_count", "legacy_comparison_count", "provenance_present_count"]) + "<h2>Cross-library inventory</h2>" + _table(rows, fields) + "<h2>Column definitions</h2>" + _table(glossary_rows, ["column", "meaning"]) + "<h2>Method</h2><p>Name agreement uses exact names. Membership agreement uses explicitly mapped names when supplied, otherwise exact shared names. Undefined ratios are shown as N/A.</p></body></html>"
    (rendered / "report.html").write_text(html_document, encoding="utf-8")
    for library_id, values in grouped.items():
        library_dir = rendered / "libraries" / library_id
        library_dir.mkdir(parents=True, exist_ok=True)
        library_summary = {"schema_version": SCHEMA_VERSION, "library_id": library_id, "model_output_reference_count": len(values), "gene_set_count_sum": sum(int(value["gene_set_count"]) for value in values), "membership_count_sum": sum(int(value["membership_count"]) for value in values), "legacy_comparison_count": sum(value["comparison_status"] == "available" for value in values)}
        _json_dump(library_dir / "summary.json", library_summary)
        _write_tsv_gz(library_dir / "model_output_summary.tsv.gz", values)
        library_markdown = "# " + library_id + " gene-set report\n\n" + "## Summary\n\n" + "\n".join(f"- {key}: {_format(value)}" for key, value in library_summary.items() if key != "schema_version") + "\n\n## Model/output inventory\n\n| " + " | ".join(fields) + " |\n| " + " | ".join("---" for _ in fields) + " |\n" + "\n".join("| " + " | ".join(_format(row.get(field)) for field in fields) + " |" for row in values) + "\n"
        (library_dir / "report.md").write_text(library_markdown, encoding="utf-8")
        library_html = "<!doctype html><meta charset=\"utf-8\"><title>" + html.escape(library_id) + " report</title><style>body{font:14px system-ui,sans-serif;margin:2rem}table{border-collapse:collapse;width:100%}th,td{border:1px solid #bbb;padding:.35rem;text-align:left}th{background:#eef}</style><h1>" + html.escape(library_id) + "</h1>" + _table([library_summary], ["model_output_reference_count", "gene_set_count_sum", "membership_count_sum", "legacy_comparison_count"]) + _table(values, fields)
        (library_dir / "report.html").write_text(library_html, encoding="utf-8")
        # Compatibility link for readers opening a library report from rendered/.
        (rendered / f"{library_id}.html").write_text(library_html, encoding="utf-8")
    return summary


def combine(results_roots: list[Path], output_dir: Path, libraries: set[str] | None, models: set[str] | None, allow_partial: bool) -> dict[str, Any]:
    """Combine completed run roots without re-reading GMTs or recomputing metrics."""
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"combined output directory must be empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir = output_dir / "metrics"; metrics_dir.mkdir()
    selected_tasks: list[dict[str, Any]] = []
    seen_task_ids: set[str] = set()
    source_roots: list[str] = []
    for source_root in results_roots:
        source_root = source_root.resolve()
        source_manifest_path = source_root / "manifest.json"
        if not source_manifest_path.is_file():
            raise ValueError(f"missing run manifest: {source_manifest_path}")
        source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
        tasks = [task for task in source_manifest.get("tasks", []) if (libraries is None or task["library_id"] in libraries) and (models is None or task["model_id"] in models)]
        # Validate all selected tasks before copying any artifacts.
        completed = {result["task_id"]: result for result in _load_results(source_root, libraries, models, allow_partial)}
        for task in tasks:
            task_id = str(task.get("task_id", ""))
            if not task_id:
                raise ValueError(f"invalid task without task_id in {source_manifest_path}")
            if task_id in seen_task_ids:
                raise ValueError(f"duplicate task identity across result roots: {task_id}")
            seen_task_ids.add(task_id)
            selected_tasks.append(task)
            result = completed.get(task_id)
            if result is None:
                continue
            for suffix in (".json", ".genes.txt.gz", ".per_term.tsv.gz"):
                source = source_root / "metrics" / f"{task_id}{suffix}"
                if source.is_file():
                    shutil.copy2(source, metrics_dir / source.name)
        source_roots.append(str(source_root))
    if not selected_tasks:
        raise ValueError("selection contains no task artifacts to combine")
    _json_dump(output_dir / "manifest.json", {"schema_version": SCHEMA_VERSION, "created_at_utc": _now(), "combined_from": source_roots, "tasks": selected_tasks})
    return render(output_dir, libraries, models, allow_partial)


def _task_command(output_dir: Path, index: int, validator: str | None) -> list[str]:
    command = [sys.executable, "-m", "submission_tools.comprehensive_report", "task", "--output-dir", str(output_dir), "--task-index", str(index)]
    if validator: command.extend(["--dapper-validator", validator])
    return command


def submit(manifest: Path, output_dir: Path, libraries: set[str] | None, models: set[str] | None, args: argparse.Namespace) -> dict[str, Any]:
    tasks = plan(manifest, output_dir, libraries, models)
    script = output_dir / "run_task.sh"
    wrapper_root = Path(__file__).resolve().parents[1]
    # The worker reads SGE_TASK_ID at runtime; the script itself is a real executable qsub target.
    task_args = ["-m", "submission_tools.comprehensive_report", "task", "--output-dir", str(output_dir.resolve()), "--task-index", "${SGE_TASK_ID}"] + (["--dapper-validator", args.dapper_validator] if args.dapper_validator else [])
    if args.apptainer_image:
        binds = [f"{wrapper_root}:/wrapper:ro", *args.bind]
        # ``--cleanenv`` intentionally removes the host's PYTHONPATH, so set
        # the wrapper package location *inside* the container instead.
        worker = [args.apptainer_bin, "exec", "--cleanenv", "--env", "PYTHONPATH=/wrapper"] + [item for bind in binds for item in ("--bind", bind)] + [args.apptainer_image, args.python_bin, *task_args]
        prefix = ""
    else:
        worker = [args.python_bin, *task_args]
        prefix = f"export PYTHONPATH={shlex_quote(str(wrapper_root))}${{PYTHONPATH:+:${{PYTHONPATH}}}}\n"
    script.write_text("#!/usr/bin/env bash\nset -euo pipefail\n: \"${SGE_TASK_ID:?SGE_TASK_ID is required}\"\n" + prefix + "exec " + " ".join(shlex_quote(part) for part in worker) + "\n", encoding="utf-8")
    script.chmod(0o755)
    qsub = [args.qsub_bin, "-cwd", "-t", f"1-{len(tasks)}", "-o", str((output_dir / "logs").resolve()), "-e", str((output_dir / "logs").resolve())]
    if args.memory: qsub.extend(["-l", f"h_vmem={args.memory}"])
    if args.walltime: qsub.extend(["-l", f"h_rt={args.walltime}"])
    if args.queue: qsub.extend(["-q", args.queue])
    if args.project: qsub.extend(["-P", args.project])
    qsub.append(str(script.resolve()))
    (output_dir / "logs").mkdir(exist_ok=True)
    payload = {"tasks": len(tasks), "qsub_command": qsub, "script": str(script.resolve()), "dry_run": args.dry_run}
    if not args.dry_run:
        completed = subprocess.run(qsub, check=True, capture_output=True, text=True)
        payload["qsub_output"] = completed.stdout.strip()
    _json_dump(output_dir / "submission.json", payload)
    return payload


def shlex_quote(value: str) -> str:
    # ``${SGE_TASK_ID}`` must expand in the generated worker shell.
    return value if value == "${SGE_TASK_ID}" else __import__("shlex").quote(value)


def _select(args: argparse.Namespace) -> tuple[set[str] | None, set[str] | None]:
    if bool(args.library) == bool(args.all_libraries):
        raise ValueError("select one or more --library values, or pass --all-libraries")
    return (set(args.library) if args.library else None), (set(args.model) if args.model else None)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan, compute, render, and submit comprehensive wrapper-side GMT reports.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    def selection(command: argparse.ArgumentParser, manifest: bool = True) -> None:
        if manifest: command.add_argument("--manifest", type=Path, required=True)
        command.add_argument("--output-dir", type=Path, required=True)
        command.add_argument("--library", action="append", default=[])
        command.add_argument("--all-libraries", action="store_true")
        command.add_argument("--model", action="append", default=[])
    plan_parser = subparsers.add_parser("plan"); selection(plan_parser)
    run_parser = subparsers.add_parser("run"); selection(run_parser); run_parser.add_argument("--dapper-validator"); run_parser.add_argument("--resume", action="store_true")
    render_parser = subparsers.add_parser("render"); selection(render_parser, manifest=False); render_parser.add_argument("--allow-partial", action="store_true")
    combine_parser = subparsers.add_parser("combine", help="Render an aggregate report from independently completed report roots.")
    selection(combine_parser, manifest=False)
    combine_parser.add_argument("--results-root", type=Path, action="append", required=True, help="Completed report root; repeat for each independent library run.")
    combine_parser.add_argument("--allow-partial", action="store_true")
    submit_parser = subparsers.add_parser("submit"); selection(submit_parser); submit_parser.add_argument("--dapper-validator"); submit_parser.add_argument("--qsub-bin", default="qsub"); submit_parser.add_argument("--memory"); submit_parser.add_argument("--walltime"); submit_parser.add_argument("--queue"); submit_parser.add_argument("--project"); submit_parser.add_argument("--apptainer-image"); submit_parser.add_argument("--apptainer-bin", default="apptainer"); submit_parser.add_argument("--python-bin", default=sys.executable); submit_parser.add_argument("--bind", action="append", default=[]); submit_parser.add_argument("--dry-run", action="store_true")
    convert_parser = subparsers.add_parser("convert-tsv", help="Convert a legacy/current mapping TSV into a comprehensive-report JSON manifest.")
    convert_parser.add_argument("--input", type=Path, required=True)
    convert_parser.add_argument("--output", type=Path, required=True)
    convert_parser.add_argument("--legacy-root", type=Path)
    convert_parser.add_argument("--current-root", type=Path)
    convert_parser.add_argument("--mapping-root", type=Path)
    discover_parser = subparsers.add_parser("discover-run-root", help="Create a manifest that compiles model GMTs from a completed run root.")
    discover_parser.add_argument("--run-root", type=Path, required=True)
    discover_parser.add_argument("--legacy-current-tsv", type=Path, help="Optional explicit legacy/reference associations; omit for a new library with no legacy comparison.")
    discover_parser.add_argument("--library", required=True)
    discover_parser.add_argument("--output", type=Path, required=True)
    discover_parser.add_argument("--legacy-root", type=Path)
    discover_parser.add_argument("--mapping-root", type=Path)
    discover_parser.add_argument("--duplicate-policy", choices=["fail", "prefix_source"], default="prefix_source", help="How run-root compilation handles colliding term names; prefix_source is the default.")
    task_parser = subparsers.add_parser("task"); task_parser.add_argument("--output-dir", type=Path, required=True); task_parser.add_argument("--task-index", type=int, required=True); task_parser.add_argument("--dapper-validator")
    args = parser.parse_args(argv)
    try:
        if args.command == "discover-run-root":
            result = discover_run_root_manifest(args.run_root, args.legacy_current_tsv, args.output, library_id=args.library, legacy_root=args.legacy_root, mapping_root=args.mapping_root, duplicate_policy=args.duplicate_policy)
        elif args.command == "convert-tsv":
            result = convert_legacy_current_tsv(args.input, args.output, legacy_root=args.legacy_root, current_root=args.current_root, mapping_root=args.mapping_root)
        elif args.command == "task":
            task = json.loads((args.output_dir / "tasks" / f"{args.task_index:05d}.json").read_text(encoding="utf-8"))
            metrics, statuses = args.output_dir / "metrics", args.output_dir / "status"; metrics.mkdir(exist_ok=True); statuses.mkdir(exist_ok=True)
            _write_status(statuses / f"{task['task_id']}.json", task, "running")
            result = _compute(task, metrics, args.dapper_validator); _json_dump(metrics / f"{task['task_id']}.json", result); _write_status(statuses / f"{task['task_id']}.json", task, "success")
        else:
            libraries, models = _select(args)
            if args.command == "plan": result = {"task_count": len(plan(args.manifest, args.output_dir, libraries, models))}
            elif args.command == "run": result = {"task_count": len(run(args.manifest, args.output_dir, libraries, models, args.dapper_validator, resume=args.resume))}
            elif args.command == "render": result = render(args.output_dir, libraries, models, args.allow_partial)
            elif args.command == "combine": result = combine(args.results_root, args.output_dir, libraries, models, args.allow_partial)
            else: result = submit(args.manifest, args.output_dir, libraries, models, args)
        print(json.dumps(result, sort_keys=True))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
