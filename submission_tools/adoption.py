"""Read-only inventory and scaffolding helpers for adopting legacy libraries."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .scaffold import scaffold

CODE_SUFFIXES = {".py": "python", ".r": "r", ".R": "r", ".sh": "shell", ".ipynb": "notebook", ".smk": "snakemake", ".nf": "nextflow"}
DATA_SUFFIXES = {".tsv", ".csv", ".gct", ".h5", ".h5ad", ".rds", ".parquet", ".RData"}
ENVIRONMENT_NAMES = {"environment.yml", "environment.yaml", "requirements.txt", "requirements-dev.txt", "pyproject.toml", "poetry.lock", "uv.lock", "renv.lock", "Dockerfile", "Makefile", "Snakefile", "nextflow.config"}
NONPORTABLE = re.compile(r"(?:/home/|/Users/|/humgen/|/broad/|\bscratch/|\b(?:token|password|credential)s?\b)", re.I)
MANUAL = re.compile(r"\b(?:manually|open in excel|edit this file|copy this file|download by hand|rename manually|filter rows|paste)\b", re.I)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _kind(path: Path) -> str | None:
    if path.name in {"Snakefile", "Makefile", "nextflow.config"}:
        return {"Snakefile": "snakemake", "Makefile": "make", "nextflow.config": "nextflow"}[path.name]
    if path.suffix in CODE_SUFFIXES:
        return CODE_SUFFIXES[path.suffix]
    return None


def _is_data(path: Path) -> bool:
    suffixes = path.suffixes
    return path.suffix in DATA_SUFFIXES or (len(suffixes) >= 2 and suffixes[-1] == ".gz" and suffixes[-2] in DATA_SUFFIXES)


def _text_prefix(path: Path, limit: int = 65536) -> str:
    try:
        with path.open("rb") as handle:
            return handle.read(limit).decode("utf-8", errors="ignore")
    except OSError:
        return ""


def _tabular_header(path: Path) -> list[str]:
    text = _text_prefix(path, 8192)
    line = text.splitlines()[0] if text else ""
    delimiter = "\t" if "\t" in line else ","
    return [item.strip() for item in line.split(delimiter) if item.strip()][:100]


def _gmt_summary(path: Path) -> dict[str, Any]:
    count = 0
    names: list[str] = []
    sizes: list[int] = []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 3:
                continue
            count += 1
            if len(names) < 50:
                names.append(fields[0])
            sizes.append(len([gene for gene in fields[2:] if gene]))
    return {"n_gene_sets": count, "set_names_sample": names, "set_size_min": min(sizes) if sizes else 0, "set_size_max": max(sizes) if sizes else 0}


def inventory_legacy(root: Path) -> dict[str, Any]:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"existing legacy directory does not exist: {root}")
    inventory: dict[str, Any] = {"schema_version": "1.0.0", "legacy_root": str(root), "code_files": [], "data_files": [], "gene_set_outputs": [], "environment_files": [], "nonportable_findings": [], "manual_step_findings": [], "possible_intermediates": []}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        rel = str(path.relative_to(root))
        record: dict[str, Any] = {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}
        code_kind = _kind(path)
        if code_kind:
            record.update({"language": code_kind, "likely_role": "entrypoint" if path.name.startswith(("run", "main", "submit")) else "processing_code"})
            inventory["code_files"].append(record)
        elif path.name in ENVIRONMENT_NAMES or path.suffix == ".def":
            record["type"] = "environment"
            inventory["environment_files"].append(record)
        elif path.suffix == ".gmt":
            record.update({"likely_role": "gene_set_output", **_gmt_summary(path)})
            inventory["gene_set_outputs"].append(record)
        elif _is_data(path):
            record.update({"header": _tabular_header(path) if path.stat().st_size <= 20_000_000 else [], "likely_classification": "output" if any(part in {"output", "outputs", "result", "results"} for part in path.parts) else "unknown"})
            inventory["data_files"].append(record)
            if record["likely_classification"] == "unknown" and any(token in path.name.lower() for token in ("processed", "filtered", "intermediate", "result", "de")):
                inventory["possible_intermediates"].append(record)
        if code_kind or path.suffix in {".md", ".txt", ".sh", ".py", ".R", ".r"}:
            text = _text_prefix(path)
            for pattern, destination, label in ((NONPORTABLE, "nonportable_findings", "nonportable_path_or_secret_marker"), (MANUAL, "manual_step_findings", "manual_step_marker")):
                if pattern.search(text):
                    inventory[destination].append({"path": rel, "kind": label})
    return inventory


def adoption_report(inventory: dict[str, Any]) -> str:
    lines = ["# Legacy adoption report", "", "## Inventory", "", f"- Code files: {len(inventory['code_files'])}", f"- Data files: {len(inventory['data_files'])}", f"- Gene-set outputs: {len(inventory['gene_set_outputs'])}", f"- Environment files: {len(inventory['environment_files'])}"]
    for heading, key, severity in (("Reproducibility risks", "manual_step_findings", "warning"), ("Portability/security risks", "nonportable_findings", "warning"), ("Possible unexplained intermediates", "possible_intermediates", "blocker")):
        lines.extend(["", f"## {heading}"])
        findings = inventory[key]
        if not findings:
            lines.append("- None detected by static inventory.")
        else:
            lines.extend(f"- **{severity}**: `{item['path']}`" for item in findings)
    lines.extend(["", "## Next steps", "", "- Reconstruct every source-to-output dependency before migration.", "- Move substantive processing, analysis, mapping, ranking, and GMT generation to `dig-gene-set-extractors`.", "- Use the generated AI prompt, then run normal submission validation and compare regenerated outputs."])
    return "\n".join(lines) + "\n"


def adoption_prompt(existing: Path, output: Path, inventory: dict[str, Any], dig_repo: Path | None) -> str:
    output_paths = ", ".join(item["path"] for item in inventory["gene_set_outputs"]) or "none detected"
    return f"""# AI migration prompt\n\nMigrate the legacy implementation at `{existing}` into `{output}`. The inventory is `{output / 'adoption/inventory.json'}`, the dependency map is `{output / 'adoption/dependency_map.json'}`, and the adoption report is `{output / 'adoption/adoption_report.md'}`. DIG is `{dig_repo or '../dig-gene-set-extractors'}`. Reference legacy gene-set outputs: {output_paths}.\n\nHaving previously generated gene sets is not sufficient. Every required intermediate must either be a declared source input or be generated by committed code in the migrated workflow.\n\nAll substantive source-data processing, statistical analysis, gene mapping, ranking, and gene-set generation must live in `dig-gene-set-extractors`. `geneset-extractor-dev` may contain only configuration, thin orchestration, reproduction metadata, adoption metadata, and publishing integration.\n\nInspect both repositories and the legacy code. Reconstruct every dependency from declared source inputs to final outputs; do not accept unexplained precomputed intermediates. Reuse scientifically equivalent DIG workflows where possible, add DIG tests and smoke fixtures, preserve scientific parameters, compare regenerated output with the legacy reference, classify every difference, and do not modify `{existing}`. Finish with coordinated validation.\n"""


def adopt(existing: Path, output: Path, library_id: str, display_name: str | None = None, pattern: str = "generic", dig_repo: Path | None = None) -> Path:
    inventory = inventory_legacy(existing)
    scaffold(output, library_id, display_name or library_id, pattern)
    payload_path = output / "submission.yaml"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["submission_origin"] = {"type": "adopted", "legacy_inventory": "adoption/inventory.json"}
    payload["adoption"] = {"reference_outputs": [{"path": item["path"], "comparison": "set_equivalent"} for item in inventory["gene_set_outputs"]]}
    payload_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    adoption_dir = output / "adoption"
    adoption_dir.mkdir()
    (adoption_dir / "inventory.json").write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    dependency_map = {"schema_version": "1.0.0", "intermediates": [{"path": item["path"], "producer": "TODO"} for item in inventory["possible_intermediates"]]}
    (adoption_dir / "dependency_map.json").write_text(json.dumps(dependency_map, indent=2) + "\n", encoding="utf-8")
    (adoption_dir / "adoption_report.md").write_text(adoption_report(inventory), encoding="utf-8")
    (adoption_dir / "AI_ADOPTION_PROMPT.md").write_text(adoption_prompt(existing.resolve(), output.resolve(), inventory, dig_repo), encoding="utf-8")
    return output


def adoption_status(root: Path) -> list[tuple[str, bool, str]]:
    inventory_path = root / "adoption/inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8")) if inventory_path.exists() else None
    dependency_path = root / "adoption/dependency_map.json"
    dependency_map = json.loads(dependency_path.read_text(encoding="utf-8")) if dependency_path.exists() else {}
    from .validator import validate_submission
    valid = validate_submission(root).ok if (root / "submission.yaml").exists() else False
    producers = {str(item.get("path")): str(item.get("producer", "TODO")) for item in dependency_map.get("intermediates", []) if isinstance(item, dict)}
    gaps = bool(inventory and any(producers.get(str(item.get("path")), "TODO") in {"", "TODO"} for item in inventory.get("possible_intermediates", [])))
    compared = (root / "adoption/comparison_report.tsv").exists()
    receipt_path = root / "run_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else {}
    command = receipt.get("command", []) if isinstance(receipt, dict) else []
    smoke_ok = bool(isinstance(receipt, dict) and receipt.get("validation_result", {}).get("ok") and "--smoke" in command)
    states = [("INVENTORIED", inventory is not None, "inventory.json exists"), ("DEPENDENCIES_RESOLVED", bool(inventory) and not gaps, "every possible intermediate has a declared producer"), ("ARCHITECTURE_MIGRATED", valid, "normal wrapper-boundary validation passes"), ("NEW_FORMAT_VALID", valid, "submission validator passes"), ("SMOKE_REPRODUCIBLE", smoke_ok, "successful --smoke run receipt exists"), ("LEGACY_COMPARED", compared, "comparison_report.tsv exists")]
    ready = all(ok for _name, ok, _detail in states)
    return [*states, ("READY", ready, "requires normal validation, resolved dependencies, and comparison")]
