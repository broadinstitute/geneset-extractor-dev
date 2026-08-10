"""Comparison of legacy and regenerated GMT outputs."""
from __future__ import annotations

import csv
from pathlib import Path


def _read_gmt(path: Path) -> dict[str, list[str]]:
    sets: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) >= 3:
            sets[fields[0]] = [gene for gene in fields[2:] if gene]
    return sets


def compare_gmt(legacy: Path, new: Path, mode: str, report_path: Path | None = None) -> tuple[bool, list[dict[str, object]]]:
    if mode not in {"exact", "set_equivalent", "report_only"}:
        raise ValueError("mode must be exact, set_equivalent, or report_only")
    old, regenerated = _read_gmt(legacy), _read_gmt(new)
    rows: list[dict[str, object]] = []
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
