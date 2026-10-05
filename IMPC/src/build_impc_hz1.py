#!/usr/bin/env python3
"""Build the pinned IMPC DR18 HZ1 mouse-phenotype library.

The 2017 Harmonizome table canonicalizes the case-normalized marker symbols
to approved human symbols.  It is intentionally an input, never inferred from
the historical KOMP2 GMT.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

REQUIRED_COLUMNS = {"marker_symbol", "mp_term_id", "mp_term_name"}
ACRONYMS = {"cd4": "CD4", "cd8": "CD8", "cd25": "CD25", "hdl": "HDL", "ige": "IgE", "igg1": "IgG1", "igg2b": "IgG2b", "klrg1": "KLRG1", "ldl": "LDL", "ly6c": "Ly6C", "nk": "NK", "pq": "PQ", "pr": "PR", "qrs": "QRS", "qt": "QT", "rr": "RR", "st": "ST"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def format_term(name: str, mp_id: str) -> str:
    """Use deterministic title style while preserving common biomedical acronyms."""
    titled = name.strip().title()
    for lower, canonical in ACRONYMS.items():
        titled = re.sub(rf"\b{re.escape(lower)}\b", canonical, titled, flags=re.IGNORECASE)
    return f"{titled} ({mp_id.strip()})"


def load_symbol_mapping(path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle, delimiter="\t"):
            if len(row) < 2 or not row[0].strip() or not row[1].strip():
                continue
            source, target = row[0].strip().upper(), row[1].strip().upper()
            mapping[source] = target
    if not mapping:
        raise ValueError(f"no symbol mappings found in {path}")
    return mapping


def open_assertions(path: Path):
    return gzip.open(path, "rt", encoding="utf-8", newline="") if path.suffix == ".gz" else path.open(encoding="utf-8", newline="")


def build(assertions: Path, mapping_file: Path, min_genes: int) -> tuple[dict[str, list[str]], dict[str, int]]:
    mapping = load_symbol_mapping(mapping_file)
    sets: defaultdict[str, set[str]] = defaultdict(set)
    rows_read = rows_accepted = rows_unmapped = 0
    with open_assertions(assertions) as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS.difference(reader.fieldnames or ())
        if missing:
            raise ValueError(f"assertions missing required columns: {sorted(missing)}")
        for row in reader:
            rows_read += 1
            marker = (row.get("marker_symbol") or "").strip()
            mp_id = (row.get("mp_term_id") or "").strip()
            mp_name = (row.get("mp_term_name") or "").strip()
            if not marker or not mp_id or not mp_name:
                continue
            human_symbol = mapping.get(marker.upper())
            if not human_symbol:
                rows_unmapped += 1
                continue
            sets[format_term(mp_name, mp_id)].add(human_symbol)
            rows_accepted += 1
    retained = {term: sorted(genes) for term, genes in sets.items() if len(genes) >= min_genes}
    diagnostics = {"rows_read": rows_read, "rows_accepted": rows_accepted, "rows_unmapped": rows_unmapped, "terms_before_min_genes": len(sets), "terms_retained": len(retained), "memberships_retained": sum(map(len, retained.values())), "unique_genes_retained": len({gene for genes in retained.values() for gene in genes}), "min_genes": min_genes}
    return dict(sorted(retained.items())), diagnostics


def write_gmt(sets: dict[str, list[str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for term, genes in sets.items():
            handle.write("\t".join([term, "", *genes]) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assertions", required=True, type=Path)
    parser.add_argument("--symbol-mapping", required=True, type=Path)
    parser.add_argument("--out-gmt", required=True, type=Path)
    parser.add_argument("--diagnostics", required=True, type=Path)
    parser.add_argument("--min-genes", type=int, default=5)
    args = parser.parse_args()
    if args.min_genes < 1:
        raise SystemExit("--min-genes must be positive")
    sets, diagnostics = build(args.assertions, args.symbol_mapping, args.min_genes)
    write_gmt(sets, args.out_gmt)
    diagnostics.update({"assertions_sha256": sha256(args.assertions), "symbol_mapping_sha256": sha256(args.symbol_mapping)})
    args.diagnostics.parent.mkdir(parents=True, exist_ok=True)
    args.diagnostics.write_text(json.dumps(diagnostics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(diagnostics, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
