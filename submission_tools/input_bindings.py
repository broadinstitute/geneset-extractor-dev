"""Runtime-only bindings from declared input IDs to a reproduction host.

The committed input manifest identifies scientific inputs.  This module reads
an untracked binding file that identifies where an authorized remote operator
has materialized those inputs.  It deliberately never writes paths into the
submission or receipt.
"""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any

from .scaffold import INPUT_HEADERS
from .yaml_loader import load


def _full(row: dict[str, str]) -> bool:
    return "full" in {value.strip() for value in row.get("smoke_full", "").split(",")}


def _fixture(row: dict[str, str]) -> bool:
    return row.get("committed_fixture", "").strip().lower() in {"true", "yes", "1"}


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        headers = set(reader.fieldnames or [])
        missing = set(INPUT_HEADERS) - headers
        if missing:
            raise ValueError(f"input manifest is missing required headers: {', '.join(sorted(missing))}")
        return list(reader)


def remote_requirements(library: Path) -> tuple[str, str]:
    """Return Markdown requirements and a placeholder-only binding template."""
    manifest = library / "reproduction" / "input_manifest.tsv"
    rows = [row for row in read_manifest(manifest) if _full(row) and not _fixture(row)]
    lines = ["# Remote full-input requirements", "", "Generated from `reproduction/input_manifest.tsv`. Do not commit remote paths, credentials, or this file after filling it in.", ""]
    template: dict[str, Any] = {"schema_version": "1.0", "library_id": library.name, "mode": "full", "inputs": {}}
    if not rows:
        lines.extend(["No non-fixture full inputs are declared.", ""])
    for row in rows:
        input_id = row.get("input_id", "")
        lines.extend([
            f"## `{input_id}`",
            f"- Source: {row.get('source_uri_or_access_instructions', '') or 'not declared'}",
            f"- Release/version: {row.get('version_release', '') or 'not declared'}",
            f"- Checksum: {row.get('checksum', '') or 'not declared'}",
            f"- Access method: {row.get('access_method', '') or 'not declared'}",
            f"- Redistribution: {row.get('redistribution_status', '') or 'not declared'}",
            f"- Workflow stage: {row.get('workflow_stage', '') or 'not declared'}",
            "- Remote action: materialize an authorized file and replace the template placeholder.",
            "",
        ])
        template["inputs"][input_id] = {"path": "REPLACE_WITH_AUTHORIZED_REMOTE_PATH"}
    import json
    return "\n".join(lines) + "\n", json.dumps(template, indent=2) + "\n"


def validate_bindings(library: Path, bindings_path: Path) -> tuple[bool, list[str], str]:
    """Validate runtime bindings without exposing their paths in diagnostics."""
    rows = read_manifest(library / "reproduction" / "input_manifest.tsv")
    required = {row["input_id"]: row for row in rows if _full(row) and not _fixture(row)}
    payload = load(bindings_path)
    messages: list[str] = []
    if payload.get("schema_version") != "1.0":
        messages.append("ERROR: input bindings require schema_version 1.0")
    if payload.get("library_id") != library.name:
        messages.append("ERROR: input bindings library_id does not match the submitted library")
    if payload.get("mode") != "full":
        messages.append("ERROR: input bindings mode must be full")
    inputs = payload.get("inputs")
    if not isinstance(inputs, dict):
        messages.append("ERROR: input bindings inputs must be a mapping")
        inputs = {}
    for key in inputs:
        if key not in required:
            messages.append(f"ERROR: input bindings declare unknown or non-full input_id: {key}")
    for input_id, row in required.items():
        binding = inputs.get(input_id)
        if not isinstance(binding, dict):
            messages.append(f"ERROR: full input {input_id} has no binding")
            continue
        forbidden = {key for key in binding if any(word in key.lower() for word in ("secret", "token", "password", "credential"))}
        if forbidden:
            messages.append(f"ERROR: input binding {input_id} contains forbidden credential-like fields")
        has_path, download = "path" in binding, binding.get("download") is True
        if has_path == download:
            messages.append(f"ERROR: input binding {input_id} must specify exactly one of path or download: true")
            continue
        if has_path:
            value = binding.get("path")
            bound_path = Path(value) if isinstance(value, str) else None
            if bound_path is None or not bound_path.is_absolute() or not bound_path.is_file():
                messages.append(f"ERROR: full input {input_id} path is not an existing absolute regular file")
            else:
                declared = row.get("checksum", "").strip()
                if declared.startswith("sha256:") and len(declared) == 71:
                    digest = hashlib.sha256()
                    with bound_path.open("rb") as handle:
                        for block in iter(lambda: handle.read(1024 * 1024), b""):
                            digest.update(block)
                    observed = digest.hexdigest()
                    if observed != declared.removeprefix("sha256:"):
                        messages.append(f"ERROR: full input {input_id} checksum does not match input_manifest.tsv")
        else:
            method = row.get("access_method", "").lower()
            if method not in {"public_download", "download", "public"}:
                messages.append(f"ERROR: full input {input_id} is not declared as publicly downloadable")
    digest = hashlib.sha256(bindings_path.read_bytes()).hexdigest()
    return not any(message.startswith("ERROR:") for message in messages), messages, digest
