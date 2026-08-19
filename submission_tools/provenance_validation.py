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
    if str(payload.get("submission_status", "draft")) == "ready" and code in {"provenance_missing", "provenance_input_link", "provenance_local_path", "provenance_workspace_url"}:
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


def _has_workspace_url(node: dict[str, Any]) -> bool:
    """Detect an HTTP URL fabricated from an adoption/workspace path.

    This deliberately targets repository and adoption-directory path segments,
    not legitimate source-provider URLs.  Stable source URLs are supplied via
    the input manifest and provenance overlay, never by mirroring a whole
    contributor home directory.
    """
    return bool(re.search(
        r"https?://[^\s\"']*/(?:adoption_candidate|geneset-extractor-dev|dig-gene-set-extractors)(?:/|$)",
        _node_text(node),
    ))


def _graphs(payload: object) -> tuple[list[tuple[str, dict[str, Any]]], str | None]:
    """Return graphs from either supported DIG sidecar representation.

    Older and current DIG producers may write one graph directly, while other
    producers write a graph-map envelope keyed by provenance graph ID.  The
    envelope is part of the existing DIG output contract; normalizing it here
    keeps wrapper validation format-compatible without constructing or
    changing DIG provenance.
    """
    if not isinstance(payload, dict):
        return [], "must contain a graph object or graph-ID map"
    if "nodes" in payload or "edges" in payload:
        return [("", payload)], None
    if not payload:
        return [], "graph-ID map is empty"
    graphs: list[tuple[str, dict[str, Any]]] = []
    for graph_id, graph in payload.items():
        if not isinstance(graph, dict):
            return [], f"graph-ID map entry {graph_id!r} is not a graph object"
        graphs.append((str(graph_id), graph))
    return graphs, None


def _stable_source_identifier(node: dict[str, Any]) -> bool:
    """Return whether a source file has a non-local stable identifier."""
    values: list[object] = [node.get(key) for key in ("canonical_uri", "download_url", "dcc_url", "drc_url", "persistent_id")]
    access = node.get("access")
    if isinstance(access, dict):
        values.extend(access.get(key) for key in ("canonical_uri", "download_url", "persistent_id", "uri"))
    for value in values:
        text = str(value or "").strip()
        if text and not text.startswith(("/", "file://")):
            return True
    return False


def _is_external_source_file(node_id: str, node: dict[str, Any], files: set[str], incoming: dict[str, set[str]]) -> bool:
    """Identify root data inputs, excluding local config and smoke fixtures."""
    if node_id not in files or incoming.get(node_id):
        return False
    text = _node_text(node)
    if "tests/fixtures" in text or any(token in text for token in ("manifest", "config")):
        return False
    return any(token in text for token in ("input", "source", "raw", "released", "expression", "matrix", "count"))


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
    incoming: dict[str, set[str]] = {node_id: set() for node_id in indexed}
    for edge in edges:
        if not isinstance(edge, dict) or str(edge.get("source", "")) not in indexed or str(edge.get("target", "")) not in indexed:
            issues.append(("provenance_graph", "edge has a missing source or target node", True))
            continue
        adjacency[str(edge["source"])].add(str(edge["target"]))
        incoming[str(edge["target"])].add(str(edge["source"]))
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
    for node_id, node in indexed.items():
        if _is_external_source_file(node_id, node, files, incoming) and not _stable_source_identifier(node):
            issues.append(("provenance_local_path", "external source file lacks a stable URI or persistent identifier", False))
            break
    for node in indexed.values():
        if _has_workspace_url(node):
            issues.append(("provenance_workspace_url", "graph contains a remote URL fabricated from an adoption/workspace path", False))
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
        artifact_roles = {str(value) for value in contract.get("artifact_roles", []) if str(value)}
        matched_rows = 0
        for row in rows:
            if str(row.get("required", "")).lower() not in {"true", "yes", "1"}:
                continue
            if artifact_roles and str(row.get("role", "")) not in artifact_roles:
                continue
            matched_rows += 1
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
                payload = json.loads(sidecar.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                result.add("error", "provenance_json", f"{sidecar.relative_to(library_root)} is not valid JSON: {exc}")
                continue
            graphs, error = _graphs(payload)
            if error:
                result.add("error", "provenance_json", f"{sidecar.relative_to(library_root)} {error}")
                continue
            for graph_id, graph in graphs:
                label = f" graph {graph_id}" if graph_id else ""
                for code, message, structural in _graph_issues(graph, artifact, required_inputs):
                    _add(result, submission, code, f"{sidecar.relative_to(library_root)}{label}: {message}", structural=structural)
        if artifact_roles and not matched_rows:
            result.add("error", "provenance_contract", f"contract {index} artifact_roles did not match any required output: {sorted(artifact_roles)}")
    return result
