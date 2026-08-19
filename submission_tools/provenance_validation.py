"""Structural completeness checks for DIG-produced provenance sidecars.

This module validates provenance; it never constructs or rewrites provenance
graphs.  Scientific workflow provenance remains a DIG responsibility.
"""
from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path
from typing import Any

from .validator import ValidationResult


def _safe_path(value: object) -> bool:
    return isinstance(value, str) and bool(value) and not Path(value).is_absolute() and ".." not in Path(value).parts


def _contracts(payload: dict[str, Any], scope: str) -> list[dict[str, Any]]:
    provenance = payload.get("provenance", {})
    values = provenance.get("contracts", []) if isinstance(provenance, dict) else []
    return [value for value in values if isinstance(value, dict) and str(value.get("scope", "")) == scope]


def _severity(payload: dict[str, Any], code: str) -> str:
    # A ready submission cannot waive an absent required sidecar, source
    # linkage, or publishable source location. Structural failures are handled
    # separately as unconditional errors.
    if str(payload.get("submission_status", "draft")) == "ready" and code in {"provenance_missing", "provenance_input_link", "provenance_local_path"}:
        return "error"
    deviations = payload.get("deviations", {})
    allowed = deviations.get("allow_provenance_findings", []) if isinstance(deviations, dict) else []
    if code in allowed:
        return "warning"
    return "error" if str(payload.get("submission_status", "draft")) == "ready" else "warning"


def _add(result: ValidationResult, payload: dict[str, Any], code: str, message: str, *, structural: bool = False) -> None:
    # Broken JSON and graph topology are never useful, even while a submission
    # is a draft. Availability/linkage may be completed during draft work.
    result.add("error" if structural else _severity(payload, code), code, message)


def _read_rows(root: Path, manifest: object, result: ValidationResult) -> list[dict[str, str]]:
    if not _safe_path(manifest):
        result.add("error", "provenance_contract", f"provenance output_manifest must be a safe relative path: {manifest!r}")
        return []
    path = root / str(manifest)
    if not path.is_file():
        result.add("error", "provenance_contract", f"provenance output manifest does not exist: {manifest}")
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _node_text(node: dict[str, Any]) -> str:
    return json.dumps(node, sort_keys=True).lower()


def _graph_issues(graph: dict[str, Any], artifact: Path, required_inputs: list[str]) -> list[tuple[str, str, bool]]:
    issues: list[tuple[str, str, bool]] = []
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not nodes:
        return [("provenance_graph", "graph has no nodes", True)]
    if not isinstance(edges, list) or not edges:
        return [("provenance_graph", "graph has no edges", True)]
    indexed = {str(node.get("id", "")): node for node in nodes if isinstance(node, dict) and node.get("id")}
    if len(indexed) != len(nodes):
        issues.append(("provenance_graph", "node IDs are blank or not unique", True))
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in indexed}
    for edge in edges:
        if not isinstance(edge, dict) or str(edge.get("source", "")) not in indexed or str(edge.get("target", "")) not in indexed:
            issues.append(("provenance_graph", "edge has a missing source or target node", True))
            continue
        adjacency[str(edge["source"])].add(str(edge["target"]))
    kinds = {node_id: str(node.get("kind") or node.get("type") or "").lower() for node_id, node in indexed.items()}
    genesets = {node_id for node_id, kind in kinds.items() if kind in {"geneset", "gene_set"}}
    operations = {node_id for node_id, kind in kinds.items() if kind in {"operation", "analysistype", "analysis_type", "workflow"}}
    files = {node_id for node_id, kind in kinds.items() if kind == "file"}
    focus = str(graph.get("focus_node_id", ""))
    if focus and focus not in genesets:
        issues.append(("provenance_graph", "focus_node_id is not a geneset node", True))
    if not genesets:
        issues.append(("provenance_graph", "graph has no geneset node", True))
    if not operations:
        issues.append(("provenance_graph", "graph has no operation/workflow node", True))
    source_files = {node_id for node_id in files if any(token in _node_text(indexed[node_id]) for token in ("input", "source", "raw", "metadata"))}
    if not source_files:
        # Some producers do not label input nodes; any file that is upstream of
        # a workflow remains a useful source candidate.
        source_files = set(files)
    if not source_files:
        issues.append(("provenance_graph", "graph has no source file node", True))
    target = focus if focus else next(iter(genesets), "")
    reachable: set[str] = set(source_files)
    frontier = list(source_files)
    while frontier:
        current = frontier.pop()
        for nxt in adjacency.get(current, set()):
            if nxt not in reachable:
                reachable.add(nxt); frontier.append(nxt)
    if target and target not in reachable:
        issues.append(("provenance_graph", "no directed source-input to geneset path", True))
    if operations and not operations & reachable:
        issues.append(("provenance_graph", "no operation/workflow lies on a source path", True))
    materialized = [indexed[node_id] for node_id in files if artifact.name.lower() in _node_text(indexed[node_id])]
    if not materialized:
        issues.append(("provenance_materialization", f"graph does not materialize expected artifact {artifact.name}", True))
    for input_id in required_inputs:
        if not any(input_id.lower() in _node_text(node) for node in indexed.values()):
            issues.append(("provenance_input_link", f"required input_manifest ID is absent from graph: {input_id}", False))
    for node in indexed.values():
        text = _node_text(node)
        if re.search(r"/(?:home/[^/]+|users/[^/]+|broad/|humgen/)", text):
            issues.append(("provenance_local_path", "graph contains a contributor-specific local path", False))
            break
    return issues


def validate_provenance_complete(library_root: Path, submission: dict[str, Any], *, scope: str) -> ValidationResult:
    """Validate declared provenance sidecars for one smoke/full scope.

    A scope with no contract is not an error: draft scaffolds may not have
    generated full outputs yet. Ready submissions are required elsewhere to
    declare a full contract.
    """
    result = ValidationResult()
    contracts = _contracts(submission, scope)
    if not contracts:
        result.add("warning", "provenance_not_declared", f"no {scope} provenance contract is declared")
        return result
    for index, contract in enumerate(contracts, start=1):
        rows = _read_rows(library_root, contract.get("output_manifest"), result)
        filename = str(contract.get("provenance_filename", "geneset.provenance.json"))
        if not _safe_path(filename) or len(Path(filename).parts) != 1:
            result.add("error", "provenance_contract", f"contract {index} provenance_filename must be a filename")
            continue
        required_inputs = [str(value) for value in contract.get("required_input_ids", []) if str(value)]
        for row in rows:
            if str(row.get("required", "")).lower() not in {"true", "yes", "1"}:
                continue
            relative = row.get("relative_path", "")
            if not _safe_path(relative):
                result.add("error", "provenance_contract", f"contract {index} has unsafe output path: {relative!r}")
                continue
            artifact = library_root / relative
            sidecar = artifact.parent / filename
            if not sidecar.is_file():
                _add(result, submission, "provenance_missing", f"{scope} provenance sidecar is missing for {relative}: {sidecar.relative_to(library_root)}")
                continue
            try:
                graph = json.loads(sidecar.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                result.add("error", "provenance_json", f"{sidecar.relative_to(library_root)} is not valid JSON: {exc}")
                continue
            if not isinstance(graph, dict):
                result.add("error", "provenance_json", f"{sidecar.relative_to(library_root)} must contain one graph object")
                continue
            for code, message, structural in _graph_issues(graph, artifact, required_inputs):
                _add(result, submission, code, f"{sidecar.relative_to(library_root)}: {message}", structural=structural)
    return result
