"""Comparison of legacy and regenerated GMT outputs."""
from __future__ import annotations

import csv
from statistics import median
from pathlib import Path
from typing import Any


def _read_gmt(path: Path) -> dict[str, list[str]]:
    sets: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) >= 3:
            sets[fields[0]] = [gene for gene in fields[2:] if gene]
    return sets


def _mapping(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = {"legacy_set_name", "regenerated_set_name"}
        if not reader.fieldnames or not required <= set(reader.fieldnames):
            raise ValueError("set mapping must contain legacy_set_name and regenerated_set_name")
        result = {str(row["legacy_set_name"]).strip(): str(row["regenerated_set_name"]).strip() for row in reader}
    if not result or len(result) != len(set(result.values())) or any(not left or not right for left, right in result.items()):
        raise ValueError("set mapping must be non-empty, one-to-one, and contain no blank names")
    return result


def compare_gmt(legacy: Path, new: Path, mode: str, report_path: Path | None = None, *, metrics: dict[str, object] | None = None, mapping_path: Path | None = None) -> tuple[bool, list[dict[str, object]]]:
    if mode not in {"exact", "set_equivalent", "report_only", "scientific_comparability"}:
        raise ValueError("mode must be exact, set_equivalent, report_only, or scientific_comparability")
    old, regenerated = _read_gmt(legacy), _read_gmt(new)
    rows: list[dict[str, object]] = []
    mapping = _mapping(mapping_path) if mode == "scientific_comparability" else {}
    if mode == "scientific_comparability":
        pairs = mapping or {name: name for name in old}
        for legacy_name, new_name in sorted(pairs.items()):
            left, right = set(old.get(legacy_name, [])), set(regenerated.get(new_name, []))
            if legacy_name not in old or new_name not in regenerated:
                rows.append({"set_name": legacy_name, "regenerated_set_name": new_name, "status": "missing", "genes_added": len(right), "genes_removed": len(left), "precision": 0.0, "recall": 0.0, "jaccard": 0.0})
                continue
            shared = left & right
            rows.append({"set_name": legacy_name, "regenerated_set_name": new_name, "status": "compared", "genes_added": len(right-left), "genes_removed": len(left-right), "precision": len(shared) / len(right) if right else 0.0, "recall": len(shared) / len(left) if left else 0.0, "jaccard": len(shared) / len(left | right) if left | right else 1.0})
        if set(old) - set(pairs):
            rows.extend({"set_name": name, "regenerated_set_name": "", "status": "unmapped_legacy", "genes_added": 0, "genes_removed": len(old[name]), "precision": 0.0, "recall": 0.0, "jaccard": 0.0} for name in sorted(set(old) - set(pairs)))
        compared = [row for row in rows if row["status"] == "compared"]
        values = [float(row["jaccard"]) for row in compared]
        limits = metrics or {}
        ok = bool(compared) and not any(row["status"] != "compared" for row in rows)
        ok = ok and (median(values) if values else 0.0) >= float(limits.get("min_gene_set_jaccard_median", 1.0))
        ok = ok and (min(values) if values else 0.0) >= float(limits.get("min_gene_set_jaccard_min", 1.0))
        ok = ok and (len(compared) / len(old) if old else 0.0) >= float(limits.get("min_named_set_recall", 1.0))
        fieldnames = ["set_name", "regenerated_set_name", "status", "genes_added", "genes_removed", "precision", "recall", "jaccard"]
        if report_path:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            with report_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t"); writer.writeheader(); writer.writerows(rows)
        return ok, rows
    for name in sorted(set(old) | set(regenerated)):
        if name not in old:
            rows.append({"set_name": name, "status": "new", "genes_added": len(regenerated[name]), "genes_removed": 0})
        elif name not in regenerated:
            rows.append({"set_name": name, "status": "missing", "genes_added": 0, "genes_removed": len(old[name])})
        else:
            same = old[name] == regenerated[name] if mode == "exact" else set(old[name]) == set(regenerated[name])
            rows.append({"set_name": name, "status": "unchanged" if same else "different", "genes_added": len(set(regenerated[name]) - set(old[name])), "genes_removed": len(set(old[name]) - set(regenerated[name]))})
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["set_name", "status", "genes_added", "genes_removed"], delimiter="\t")
            writer.writeheader(); writer.writerows(rows)
    ok = mode == "report_only" or all(row["status"] == "unchanged" for row in rows)
    return ok, rows
