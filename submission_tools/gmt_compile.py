#!/usr/bin/env python3
"""Compile split wrapper output GMTs for one model into a single GMT."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import logging
import sys
import tempfile
from pathlib import Path


LOG = logging.getLogger(__name__)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _model_from_path(path: Path) -> str | None:
    parts = path.parts
    for index, part in enumerate(parts[:-1]):
        if part in {"models", "tissue_models"} and index + 1 < len(parts):
            return parts[index + 1]
    return None


def discover_model_gmts(run_root: Path, model_id: str) -> list[Path]:
    """Discover extractor GMTs for a model and omit redundant aggregates.

    A model directory may also contain workflow/selection intermediates and
    their provenance.  Only paths rooted below an ``extractor`` or
    ``tissue_extractor`` directory are final generated gene-set outputs.
    """
    paths = sorted(
        path.resolve()
        for path in run_root.rglob("*.gmt")
        if path.is_file()
        and path.name == "genesets.gmt"
        and _model_from_path(path) == model_id
        and any(part in {"extractor", "tissue_extractor"} for part in path.parts)
    )
    if not paths:
        raise ValueError(f"no extractor genesets.gmt files for model {model_id!r} beneath {run_root}")
    selected: list[Path] = []
    for path in paths:
        # A direct extractor-level GMT is commonly an aggregate of the child
        # split outputs; compile the children once rather than duplicating it.
        if path.parent.name in {"extractor", "tissue_extractor"}:
            child_prefix = path.parent
            if any(child_prefix in candidate.parents and candidate.parent != child_prefix for candidate in paths):
                continue
        selected.append(path)
    return selected


def _iter_records(path: Path):
    """Yield GMT records without retaining an entire source file in memory."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            fields = line.rstrip("\r\n").split("\t")
            if len(fields) < 3 or not fields[0].strip():
                raise ValueError(f"malformed GMT record at {path}:{line_number}")
            yield fields[0].strip(), fields[1], [gene for gene in fields[2:] if gene], line_number


def _source_label(path: Path, run_root: Path) -> str:
    return str(path.relative_to(run_root)).replace("/", "__").replace("\\", "__").removesuffix(".gmt")


def compile_gmts(run_root: Path, model_id: str, output: Path, *, duplicate_policy: str = "fail") -> tuple[list[dict[str, object]], int]:
    """Compile all selected split outputs, returning a source manifest and count."""
    if duplicate_policy not in {"fail", "prefix_source"}:
        raise ValueError("duplicate_policy must be fail or prefix_source")
    run_root, output = run_root.resolve(), output.resolve()
    if output.exists():
        raise ValueError(f"refusing to overwrite existing output: {output}")
    sources = discover_model_gmts(run_root, model_id)
    names: dict[str, Path] = {}
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, object]] = []
    record_count = 0
    temporary = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", prefix=f".{output.name}.", suffix=".tmp", dir=output.parent, delete=False)
    temporary_path = Path(temporary.name)
    try:
        with temporary as handle:
            for source in sources:
                emitted = 0
                source_record_count = 0
                source_duplicate_count = 0
                source_renamed_count = 0
                for name, description, genes, line_number in _iter_records(source):
                    source_record_count += 1
                    compiled_name = name
                    if compiled_name in names:
                        source_duplicate_count += 1
                        if duplicate_policy == "fail":
                            raise ValueError(f"duplicate gene-set name {name!r} in {source}; first seen in {names[name]}")
                        compiled_name = f"{_source_label(source, run_root)}__{name}"
                        if compiled_name in names:
                            raise ValueError(f"prefixed duplicate gene-set name {compiled_name!r} in {source}")
                        source_renamed_count += 1
                    names[compiled_name] = source
                    handle.write("\t".join([compiled_name, description, *genes]) + "\n")
                    emitted += 1
                    record_count += 1
                manifest.append({"model_id": model_id, "source_gmt": str(source), "source_sha256": _sha256(source), "source_record_count": source_record_count, "compiled_record_count": emitted, "duplicate_term_count": source_duplicate_count, "renamed_term_count": source_renamed_count, "included": True})
        temporary_path.replace(output)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return manifest, record_count


def _write_manifest(path: Path, rows: list[dict[str, object]]) -> None:
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        fields = ["model_id", "source_gmt", "source_sha256", "source_record_count", "compiled_record_count", "duplicate_term_count", "renamed_term_count", "included"]
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader(); writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile split/tissue-specific GMT outputs for one model.")
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--output", type=Path, required=True, help="New compiled GMT path; it must not already exist.")
    parser.add_argument("--duplicate-policy", choices=["fail", "prefix_source"], default="fail")
    args = parser.parse_args(argv)
    if not args.run_root.is_dir():
        parser.error(f"run root is not a directory: {args.run_root}")
    if args.output.suffix != ".gmt":
        parser.error("--output must end in .gmt")
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(filename=args.output.with_suffix(".log"), level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", force=True)
        manifest, record_count = compile_gmts(args.run_root, args.model_id, args.output, duplicate_policy=args.duplicate_policy)
        manifest_path = args.output.with_suffix(".manifest.tsv.gz")
        _write_manifest(manifest_path, manifest)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    LOG.info("wrote %s records from %s source GMTs", record_count, len(manifest))
    print(f"compiled {record_count} gene sets from {len(manifest)} GMTs: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
