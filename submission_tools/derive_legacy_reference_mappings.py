#!/usr/bin/env python3
"""Derive conservative per-model legacy/current GMT name mappings.

This wrapper-side utility uses only paired, final GMT artifacts.  It never
guesses semantic correspondences: a mapping is emitted only for unique exact
name, normalized-format name, or exact gene-membership matches.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import re
import sqlite3
import tempfile
from pathlib import Path


def _canonical_name(name: str) -> str:
    text = name.casefold().replace("down", "dn")
    return re.sub(r"[^a-z0-9]+", "", text)


def _fingerprint(genes: list[str]) -> str:
    return hashlib.sha256("\x1f".join(sorted(set(genes))).encode()).hexdigest()


def _records(path: Path):
    seen_record = False
    with path.open("r", encoding="utf-8", newline="") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            fields = line.rstrip("\r\n").split("\t")
            if not seen_record and len(fields) < 3:
                # XMT exports may carry a YAML-like descriptive preamble before
                # their tab-delimited gene-set records.
                continue
            if len(fields) < 3 or not fields[0].strip():
                raise ValueError(f"malformed GMT record at {path}:{number}")
            seen_record = True
            yield fields[0].strip(), [gene.strip() for gene in fields[2:] if gene.strip()]


def _single(connection: sqlite3.Connection, column: str, value: str) -> str | None:
    rows = connection.execute(f"SELECT legacy_name FROM legacy_sets WHERE {column} = ? LIMIT 2", (value,)).fetchall()
    return rows[0][0] if len(rows) == 1 else None


def derive_mapping(legacy_gmt: Path, current_gmt: Path, mapping_path: Path, audit_path: Path, *, name_only: bool = False) -> dict[str, int]:
    """Write a two-column mapping plus a full, reviewable legacy-name audit."""
    if mapping_path.exists() or audit_path.exists():
        raise ValueError(f"refusing to overwrite existing mapping artifacts beneath {mapping_path.parent}")
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="legacy_mapping_") as temporary:
        database = sqlite3.connect(Path(temporary) / "sets.sqlite")
        database.execute("CREATE TABLE legacy_sets (legacy_name TEXT PRIMARY KEY, canonical TEXT NOT NULL, fingerprint TEXT NOT NULL, current_name TEXT, method TEXT)")
        batch: list[tuple[str, str, str]] = []
        for name, genes in _records(legacy_gmt):
            batch.append((name, _canonical_name(name), "" if name_only else _fingerprint(genes)))
            if len(batch) >= 10_000:
                database.executemany("INSERT INTO legacy_sets (legacy_name, canonical, fingerprint) VALUES (?, ?, ?)", batch); batch = []
        if batch:
            database.executemany("INSERT INTO legacy_sets (legacy_name, canonical, fingerprint) VALUES (?, ?, ?)", batch)
        database.execute("CREATE INDEX legacy_canonical ON legacy_sets(canonical)")
        database.execute("CREATE INDEX legacy_fingerprint ON legacy_sets(fingerprint)")
        database.commit()
        counts = {"legacy_total": database.execute("SELECT COUNT(*) FROM legacy_sets").fetchone()[0], "current_total": 0, "exact_name": 0, "canonical_name": 0, "exact_membership": 0}
        for current_name, genes in _records(current_gmt):
            counts["current_total"] += 1
            methods = [("legacy_name", current_name, "exact_name"), ("canonical", _canonical_name(current_name), "canonical_name")]
            if not name_only:
                methods.append(("fingerprint", _fingerprint(genes), "exact_membership"))
            for column, value, method in methods:
                legacy_name = _single(database, column, value)
                if legacy_name is None:
                    continue
                changed = database.execute("UPDATE legacy_sets SET current_name = ?, method = ? WHERE legacy_name = ? AND current_name IS NULL", (current_name, method, legacy_name)).rowcount
                if changed:
                    counts[method] += 1
                break
        database.commit()
        with mapping_path.open("x", encoding="utf-8", newline="") as mapping_handle, gzip.open(audit_path, "wt", encoding="utf-8", newline="") as audit_handle:
            mapping_writer = csv.writer(mapping_handle, delimiter="\t", lineterminator="\n")
            mapping_writer.writerow(["legacy_set_name", "regenerated_set_name"])
            audit_writer = csv.DictWriter(audit_handle, fieldnames=["legacy_set_name", "regenerated_set_name", "status", "method"], delimiter="\t", lineterminator="\n")
            audit_writer.writeheader()
            for legacy_name, current_name, method in database.execute("SELECT legacy_name, current_name, method FROM legacy_sets ORDER BY legacy_name"):
                status = "mapped" if current_name else "unmatched"
                audit_writer.writerow({"legacy_set_name": legacy_name, "regenerated_set_name": current_name or "", "status": status, "method": method or ""})
                if current_name:
                    mapping_writer.writerow([legacy_name, current_name])
        counts["mapped"] = counts["exact_name"] + counts["canonical_name"] + counts["exact_membership"]
        counts["unmatched"] = counts["legacy_total"] - counts["mapped"]
        return counts


def _resolve_by_basename(root: Path, recorded_path: str) -> Path:
    basename = Path(recorded_path).name
    matches = list(root.rglob(basename))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {basename!r} beneath {root}, found {len(matches)}")
    return matches[0]


def _library_model(current_gmt: Path) -> tuple[str, str]:
    suffix = ".genesets.gmt"
    if not current_gmt.name.endswith(suffix):
        raise ValueError(f"current GMT must be named <library>.<model>{suffix}: {current_gmt.name}")
    library, model = current_gmt.name.removesuffix(suffix).rsplit(".", 1)
    return library, model


def derive_from_manifest(manifest: Path, legacy_root: Path, current_root: Path, wrapper_root: Path, *, skip_existing: bool = False, name_only: bool = False, skip_models: set[tuple[str, str]] | None = None) -> list[dict[str, object]]:
    with manifest.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if not rows or not {"legacy_gmt", "current_gmt"} <= set(rows[0]):
        raise ValueError("manifest must contain legacy_gmt and current_gmt columns")
    results = []
    for row in rows:
        legacy = _resolve_by_basename(legacy_root, str(row["legacy_gmt"]))
        current = _resolve_by_basename(current_root, str(row["current_gmt"]))
        library, model = _library_model(current)
        if (library, model) in (skip_models or set()):
            results.append({"library_id": library, "model_id": model, "skipped": True})
            continue
        target_dir = wrapper_root / library / "adoption" / "legacy_reference_mappings" / model
        if skip_existing and (target_dir / "legacy_reference_mapping.tsv").exists():
            results.append({"library_id": library, "model_id": model, "skipped": True})
            continue
        counts = derive_mapping(legacy, current, target_dir / "legacy_reference_mapping.tsv", target_dir / "legacy_reference_mapping_audit.tsv.gz", name_only=name_only)
        (target_dir / "commands.md").write_text(f"# Derivation command\n\n- legacy GMT: `{legacy}`\n- current GMT: `{current}`\n- methods: exact name, normalized formatting, exact membership\n", encoding="utf-8")
        (target_dir / "run.log").write_text("\n".join(f"{key}\t{value}" for key, value in sorted(counts.items())) + "\n", encoding="utf-8")
        results.append({"library_id": library, "model_id": model, "legacy_gmt": str(legacy), "current_gmt": str(current), **counts})
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Derive conservative per-model legacy-reference mappings from paired GMTs.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--legacy-root", type=Path, required=True)
    parser.add_argument("--current-root", type=Path, required=True)
    parser.add_argument("--wrapper-root", type=Path, required=True)
    parser.add_argument("--skip-existing", action="store_true", help="Leave already-derived model mappings unchanged.")
    parser.add_argument("--name-only", action="store_true", help="Use exact/normalized names only; skip expensive membership fingerprints.")
    parser.add_argument("--skip-model", action="append", default=[], metavar="LIBRARY_ID/MODEL_ID", help="Skip one pair, repeatable.")
    args = parser.parse_args(argv)
    try:
        skip_models = {tuple(item.split("/", 1)) for item in args.skip_model if "/" in item}
        if len(skip_models) != len(args.skip_model):
            parser.error("--skip-model must use LIBRARY_ID/MODEL_ID")
        results = derive_from_manifest(args.manifest, args.legacy_root, args.current_root, args.wrapper_root, skip_existing=args.skip_existing, name_only=args.name_only, skip_models=skip_models)
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.error(str(exc))
    for result in results:
        print("{library_id}\t{model_id}\t{mapped}/{legacy_total}".format(**result) if not result.get("skipped") else "{library_id}\t{model_id}\tskipped".format(**result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
