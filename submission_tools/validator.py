from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .yaml_loader import load

INPUT_HEADERS = {"input_id", "source_uri_or_access_instructions", "version_release", "checksum", "access_method", "smoke_full", "workflow_stage", "redistribution_status", "committed_fixture", "fixture_path"}
OUTPUT_HEADERS = {"output_id", "relative_path", "role", "required", "model_id", "partition_id"}
MODEL_HEADERS = {"model_id"}
PARTITION_HEADERS = {"partition_id", "tissue_id", "dataset_id", "signature_id"}
DESCRIPTION_HEADERS = {"model_id", "description_template"}
ANALYTICAL_IMPORTS = ("pandas", "numpy", "scipy", "statsmodels", "scanpy", "sklearn", "rpy2", "tensorflow", "torch")
UNSAFE_PROVENANCE_MIRROR = re.compile(
    r"(?:Path\s*\.\s*home\s*\(|os\.environ\s*\[\s*['\"]HOME['\"]\s*\]|"
    r"expanduser\s*\(\s*['\"]~|\$\{?HOME\}?|(?:^|[\s'\"])~(?:/|['\"]|$)|/(?:home|Users)/)",
    re.M,
)


@dataclass
class Issue:
    level: str
    code: str
    message: str


@dataclass
class ValidationResult:
    issues: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.level == "error" for issue in self.issues)

    def add(self, level: str, code: str, message: str) -> None:
        self.issues.append(Issue(level, code, message))


def _safe_relative(value: object) -> bool:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        return False
    return ".." not in Path(value).parts and not re.match(r"^[A-Za-z]:[\\/]", value)


def _read_tsv(path: Path, required: set[str], unique_column: str | None, result: ValidationResult) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            headers = set(reader.fieldnames or [])
            missing = required - headers
            if missing:
                result.add("error", "tsv_headers", f"{path}: missing required headers {sorted(missing)}")
                return []
            rows = list(reader)
    except (OSError, csv.Error) as exc:
        result.add("error", "tsv_read", f"{path}: {exc}")
        return []
    if unique_column:
        values = [row.get(unique_column, "").strip() for row in rows]
        if not all(values):
            result.add("error", "tsv_id", f"{path}: blank {unique_column}")
        if len(values) != len(set(values)):
            result.add("error", "duplicate_id", f"{path}: duplicate {unique_column}")
    return rows


def _required_mapping(payload: dict[str, Any], key: str, result: ValidationResult) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        result.add("error", "schema", f"submission.yaml requires mapping {key!r}")
        return {}
    return value


def _validate_schema(data: dict[str, Any], result: ValidationResult) -> None:
    required = {"schema_version", "library", "sources", "dig", "configs", "reproduction", "expected_outputs", "environment", "deviations", "paired_pull_requests"}
    missing = required - set(data)
    if missing:
        result.add("error", "schema", f"missing required fields: {sorted(missing)}")
    if not re.fullmatch(r"1\.\d+\.\d+", str(data.get("schema_version", ""))):
        result.add("error", "schema_version", "schema_version must be a 1.x.y value")
    library = _required_mapping(data, "library", result)
    for key in ("id", "display_name", "organism", "assay_types", "closest_reference_pattern", "wrapper_directory"):
        if not library.get(key):
            result.add("error", "schema", f"library.{key} is required")
    if library.get("closest_reference_pattern") not in {"gtex", "motrpac", "hubmap", "lincs_l1000", "generic"}:
        result.add("error", "pattern", "library.closest_reference_pattern is not supported")
    if not isinstance(library.get("assay_types"), list) or not library.get("assay_types"):
        result.add("error", "schema", "library.assay_types must be a non-empty list")
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        result.add("error", "schema", "sources must be a non-empty list")
    else:
        for index, source in enumerate(sources):
            if not isinstance(source, dict) or any(not source.get(k) for k in ("name", "uri_or_identifier", "release", "access_restrictions", "license")):
                result.add("error", "schema", f"sources[{index}] requires name, uri_or_identifier, release, access_restrictions, license")
    dig = _required_mapping(data, "dig", result)
    if not str(dig.get("repository_url", "")).startswith(("https://", "git@")) or not isinstance(dig.get("entrypoints"), list) or not dig.get("entrypoints") or not isinstance(dig.get("identifiers"), list) or not dig.get("identifiers"):
        result.add("error", "schema", "dig requires repository_url, non-empty entrypoints, and identifiers")
    for section, keys in (("configs", ("model_config", "partition_config", "description_config")), ("reproduction", ("entry_point", "input_manifest", "smoke_test_command")), ("expected_outputs", ("manifest",)), ("environment", ("declaration",))):
        mapping = _required_mapping(data, section, result)
        for key in keys:
            if not mapping.get(key):
                result.add("error", "schema", f"{section}.{key} is required")
    provenance = data.get("provenance", {})
    if provenance and (not isinstance(provenance, dict) or not isinstance(provenance.get("contracts", []), list)):
        result.add("error", "provenance_contract", "provenance.contracts must be a list")
    elif isinstance(provenance, dict):
        for index, contract in enumerate(provenance.get("contracts", [])):
            if not isinstance(contract, dict) or contract.get("scope") not in {"smoke", "full"}:
                result.add("error", "provenance_contract", f"provenance.contracts[{index}] requires scope smoke or full")
                continue
            if not _safe_relative(contract.get("output_manifest")):
                result.add("error", "provenance_contract", f"provenance.contracts[{index}].output_manifest must be a safe relative path")
            filename = contract.get("provenance_filename", "geneset.provenance.json")
            if not isinstance(filename, str) or Path(filename).name != filename:
                result.add("error", "provenance_contract", f"provenance.contracts[{index}].provenance_filename must be a filename")
            if "required_input_ids" in contract and not isinstance(contract["required_input_ids"], list):
                result.add("error", "provenance_contract", f"provenance.contracts[{index}].required_input_ids must be a list")
            if "artifact_roles" in contract and (
                not isinstance(contract["artifact_roles"], list)
                or not all(isinstance(value, str) and value for value in contract["artifact_roles"])
            ):
                result.add("error", "provenance_contract", f"provenance.contracts[{index}].artifact_roles must be a list of non-empty output roles")
    if data.get("submission_status") == "ready":
        contracts = provenance.get("contracts", []) if isinstance(provenance, dict) else []
        if not any(isinstance(contract, dict) and contract.get("scope") == "full" for contract in contracts):
            result.add("error", "provenance_contract", "ready submissions require a full provenance contract")
    paired = _required_mapping(data, "paired_pull_requests", result)
    for key in ("geneset_extractor_dev", "dig_gene_set_extractors"):
        value = str(paired.get(key, ""))
        if value not in {"TBD", "N/A", ""} and not re.match(r"https://github\.com/[^/]+/[^/]+/pull/\d+$", value):
            result.add("error", "paired_pr", f"paired_pull_requests.{key} must be TBD, N/A, or a GitHub PR URL")
    adoption = data.get("adoption", {})
    if adoption and not isinstance(adoption, dict):
        result.add("error", "adoption", "adoption must be a mapping")
    elif isinstance(adoption, dict):
        policy = adoption.get("comparison_policy", {"mode": "exact_reproduction"})
        if not isinstance(policy, dict) or policy.get("mode", "exact_reproduction") not in {"exact_reproduction", "scientific_reimplementation"}:
            result.add("error", "comparison_policy", "adoption.comparison_policy.mode must be exact_reproduction or scientific_reimplementation")
        elif policy.get("mode") == "scientific_reimplementation":
            assessment = policy.get("source_version_assessment")
            review = policy.get("required_review")
            if not isinstance(assessment, dict) or not policy.get("reason") or not policy.get("source_assessment_path"):
                result.add("error", "comparison_policy", "scientific_reimplementation requires reason, source_assessment_path, and source_version_assessment")
            if not isinstance(review, dict) or review.get("status") not in {"pending", "approved"}:
                result.add("error", "comparison_policy", "scientific_reimplementation requires required_review.status pending or approved")
            if data.get("submission_status") == "ready" and (not isinstance(review, dict) or review.get("status") != "approved" or not re.match(r"https://github\.com/[^/]+/[^/]+/(?:pull|issues)/\d+$", str(review.get("approval_reference", "")))):
                result.add("error", "comparison_review", "ready scientific_reimplementation requires an approved GitHub PR or issue reference")
        for index, item in enumerate(adoption.get("reference_outputs", [])):
            if not isinstance(item, dict):
                result.add("error", "comparison_policy", f"adoption.reference_outputs[{index}] must be a mapping")
                continue
            comparison = item.get("comparison", "set_equivalent")
            if comparison not in {"exact", "set_equivalent", "scientific_comparability"}:
                result.add("error", "comparison_policy", f"adoption.reference_outputs[{index}].comparison is unsupported")
            if comparison == "scientific_comparability":
                metrics = item.get("metrics")
                if not isinstance(metrics, dict) or not all(isinstance(metrics.get(key), (int, float)) and 0 <= float(metrics[key]) <= 1 for key in ("min_named_set_recall", "min_gene_set_jaccard_median", "min_gene_set_jaccard_min")):
                    result.add("error", "comparison_policy", f"adoption.reference_outputs[{index}] scientific_comparability requires 0..1 metrics")
                if not _safe_relative(item.get("mapping_file")):
                    result.add("error", "comparison_policy", f"adoption.reference_outputs[{index}].mapping_file must be a safe relative path")


def _path(root: Path, value: object, label: str, result: ValidationResult) -> Path | None:
    if not _safe_relative(value):
        result.add("error", "path", f"{label} must be a safe relative path: {value!r}")
        return None
    path = (root / str(value)).resolve()
    if root not in path.parents and path != root:
        result.add("error", "path", f"{label} escapes the submitted library")
        return None
    if not path.exists():
        result.add("error", "missing_file", f"{label} does not exist: {value}")
        return None
    return path


def _allow(data: dict[str, Any], code: str) -> bool:
    deviations = data.get("deviations", {})
    return isinstance(deviations, dict) and code in deviations.get("allow_wrapper_findings", [])


def _wrapper_scan(root: Path, wrapper: Path, data: dict[str, Any], result: ValidationResult) -> None:
    if not wrapper.is_dir():
        result.add("error", "wrapper", "library.wrapper_directory must resolve to a directory")
        return
    excluded = {".git", "outputs", "data", "fixtures", "__pycache__"}
    for path in wrapper.rglob("*"):
        if not path.is_file() or any(part in excluded for part in path.relative_to(wrapper).parts) or path.suffix not in {".py", ".sh", ".R", ".r"}:
            continue
        size = path.stat().st_size
        if size > 100_000:
            result.add("warning", "large_wrapper_file", f"{path.relative_to(root)} is {size} bytes")
        text = path.read_text(encoding="utf-8", errors="ignore")
        findings = []
        if any(re.search(rf"^\s*(?:from|import)\s+{re.escape(name)}\b", text, re.M) for name in ANALYTICAL_IMPORTS):
            findings.append("analytical_import")
        if re.search(r"genesets?\.gmt|write_gmt|GMTWriter", text, re.I):
            findings.append("gmt_writing")
        if re.search(r"(normalize|differential expression|ttest|rankdata|gene.?map|map.*gene|statsmodels)", text, re.I):
            findings.append("substantive_analysis")
        if re.search(r"(provenance.*graph|graph.*provenance).*(write|build|node|edge)", text, re.I):
            findings.append("provenance_graph")
        for code in sorted(set(findings)):
            if _allow(data, code):
                result.add("warning", "allowlisted_" + code, f"{path.relative_to(root)}: allowlisted {code}")
            else:
                result.add("error", code, f"{path.relative_to(root)} appears to implement {code}; move it to DIG or document an allowlisted deviation")
        if "provenance_mirror_local_prefix" in text and UNSAFE_PROVENANCE_MIRROR.search(text):
            level = "error" if data.get("submission_status") == "ready" else "warning"
            result.add(
                level,
                "unsafe_provenance_mirror",
                f"{path.relative_to(root)} mirrors a home-directory path into provenance; use a narrow declared input mirror or config/provenance_overlay.json instead",
            )


def _script_checks(root: Path, entry: Path, result: ValidationResult) -> None:
    download_script = root / "reproduction" / "download_inputs.sh"
    if not download_script.exists():
        result.add("error", "missing_script", "required reproduction/download_inputs.sh does not exist")
    for script in (entry, download_script):
        if not script.exists():
            continue
        if not os.access(script, os.X_OK):
            result.add("error", "script_executable", f"{script.relative_to(root)} is not executable")
        text = script.read_text(encoding="utf-8", errors="ignore")
        if script.suffix == ".sh" and "set -euo pipefail" not in text:
            result.add("warning", "shell_strict_mode", f"{script.relative_to(root)} lacks set -euo pipefail")
        for ref in re.findall(r'''(?:^|[\s'"])((?:reproduction|run|src)/[A-Za-z0-9_./-]+\.sh)''', text):
            if not (root / ref).exists():
                result.add("error", "missing_script", f"{script.relative_to(root)} references missing {ref}")
        if re.search(r"/(?:home/[^/]+|broad/|humgen/diabetes2/users/)", text):
            result.add("error", "contributor_path", f"{script.relative_to(root)} contains a contributor-specific absolute path")
        if re.search(r"manual (spreadsheet|Excel)|edit.*spreadsheet", text, re.I):
            result.add("error", "manual_transform", f"{script.relative_to(root)} documents a manual spreadsheet transformation")
    if "--smoke" not in entry.read_text(encoding="utf-8", errors="ignore"):
        result.add("error", "smoke_mode", "reproduction entry point must support --smoke or document an equivalent")


def _fixture_checks(root: Path, input_rows: list[dict[str, str]], result: ValidationResult) -> None:
    declared: set[Path] = set()
    for row in input_rows:
        fixture_path = row.get("fixture_path", "").strip()
        committed = row.get("committed_fixture", "").strip().lower()
        if fixture_path:
            if not _safe_relative(fixture_path):
                result.add("error", "fixture_path", f"unsafe fixture_path for {row.get('input_id')}: {fixture_path}")
                continue
            candidate = root / fixture_path
            if not candidate.is_file():
                result.add("error", "fixture_path", f"declared fixture does not exist: {fixture_path}")
                continue
            declared.add(candidate.resolve())
        if committed in {"true", "yes", "1"} and not fixture_path:
            result.add("error", "fixture_path", f"committed fixture {row.get('input_id')} requires fixture_path")
    fixture_root = root / "tests" / "fixtures"
    if fixture_root.is_dir():
        for candidate in fixture_root.rglob("*"):
            if candidate.is_file() and candidate.name.lower() not in {"readme.md", ".gitkeep"} and candidate.resolve() not in declared:
                result.add("error", "undeclared_input", f"committed fixture is not declared in input_manifest.tsv: {candidate.relative_to(root)}")


def validate_submission(submission: Path) -> ValidationResult:
    result = ValidationResult()
    path = submission / "submission.yaml" if submission.is_dir() else submission
    if not path.exists():
        result.add("warning", "legacy_ignored", f"no submission.yaml at {submission}; legacy libraries are not validated")
        return result
    root = path.parent.resolve()
    try:
        data = load(path)
    except (OSError, ValueError) as exc:
        result.add("error", "yaml", f"cannot parse submission.yaml: {exc}")
        return result
    _validate_schema(data, result)
    library = data.get("library", {}) if isinstance(data.get("library"), dict) else {}
    configs = data.get("configs", {}) if isinstance(data.get("configs"), dict) else {}
    reproduction = data.get("reproduction", {}) if isinstance(data.get("reproduction"), dict) else {}
    expected = data.get("expected_outputs", {}) if isinstance(data.get("expected_outputs"), dict) else {}
    paths = {name: _path(root, value, name, result) for name, value in {
        "wrapper_directory": library.get("wrapper_directory"), "model_config": configs.get("model_config"), "partition_config": configs.get("partition_config"), "description_config": configs.get("description_config"), "input_manifest": reproduction.get("input_manifest"), "reproduction_entry_point": reproduction.get("entry_point"), "output_manifest": expected.get("manifest")}.items()}
    model_rows = _read_tsv(paths["model_config"], MODEL_HEADERS, "model_id", result) if paths["model_config"] else []
    partition_rows = _read_tsv(paths["partition_config"], set(), None, result) if paths["partition_config"] else []
    if paths["partition_config"]:
        with paths["partition_config"].open("r", encoding="utf-8", newline="") as handle:
            partition_headers = set(csv.DictReader(handle, delimiter="\t").fieldnames or [])
        if not partition_headers & PARTITION_HEADERS:
            result.add("error", "tsv_headers", f"{paths['partition_config']}: requires one partition ID header from {sorted(PARTITION_HEADERS)}")
    description_rows = _read_tsv(paths["description_config"], DESCRIPTION_HEADERS, "model_id", result) if paths["description_config"] else []
    input_rows = _read_tsv(paths["input_manifest"], INPUT_HEADERS, "input_id", result) if paths["input_manifest"] else []
    output_rows = _read_tsv(paths["output_manifest"], OUTPUT_HEADERS, "output_id", result) if paths["output_manifest"] else []
    model_ids = {row.get("model_id", "") for row in model_rows}
    if description_rows and not {row.get("model_id", "") for row in description_rows} <= model_ids:
        result.add("error", "config_cross_reference", "description config references unknown model_id")
    source_names = {str(x.get("name", "")) for x in data.get("sources", []) if isinstance(x, dict)}
    input_ids = {row.get("input_id", "") for row in input_rows}
    if not all(name in input_ids or name == "TODO source" for name in source_names):
        result.add("error", "input_manifest", "every declared source must have an input_manifest.tsv input_id")
    for row in output_rows:
        if not _safe_relative(row.get("relative_path", "")):
            result.add("error", "output_path", f"output manifest has unsafe path: {row.get('relative_path')}")
        if row.get("model_id") and row["model_id"] not in model_ids:
            result.add("error", "config_cross_reference", f"output manifest references unknown model_id {row['model_id']}")
    dig = data.get("dig", {}) if isinstance(data.get("dig"), dict) else {}
    if data.get("submission_status") == "ready" and not re.fullmatch(r"[0-9a-f]{40}", str(dig.get("commit", ""))):
        result.add("error", "dig_commit", "ready submissions require a full 40-character lowercase DIG commit SHA")
    if paths["wrapper_directory"]:
        _wrapper_scan(root, paths["wrapper_directory"], data, result)
    if paths["reproduction_entry_point"]:
        _script_checks(root, paths["reproduction_entry_point"], result)
        output_environment = reproduction.get("output_directory_environment")
        if output_environment is not None:
            if output_environment != "SUBMISSION_WORK_DIR":
                result.add("error", "runtime_output_directory", "reproduction.output_directory_environment must be SUBMISSION_WORK_DIR when declared")
            elif "SUBMISSION_WORK_DIR" not in paths["reproduction_entry_point"].read_text(encoding="utf-8", errors="ignore"):
                result.add("error", "runtime_output_directory", "reproduction entry point declares SUBMISSION_WORK_DIR but does not reference it")
    adoption = data.get("adoption", {}) if isinstance(data.get("adoption"), dict) else {}
    policy = adoption.get("comparison_policy", {}) if isinstance(adoption.get("comparison_policy", {}), dict) else {}
    if policy.get("mode") == "scientific_reimplementation":
        _path(root, policy.get("source_assessment_path"), "adoption.source_assessment_path", result)
        full_inputs = [row for row in input_rows if "full" in {item.strip() for item in row.get("smoke_full", "").split(",")}]
        for row in full_inputs:
            confidence = row.get("source_version_confidence", "").strip()
            relationship = row.get("legacy_input_relationship", "").strip()
            if confidence not in {"exact_historical", "provider_release", "best_available_public_release"}:
                result.add("error", "source_version_confidence", f"full input {row.get('input_id')} requires source_version_confidence exact_historical, provider_release, or best_available_public_release")
            if relationship not in {"identical", "documented_successor", "inferred_equivalent"}:
                result.add("error", "legacy_input_relationship", f"full input {row.get('input_id')} requires a documented legacy_input_relationship")
        scientific_mappings = [item for item in adoption.get("reference_outputs", []) if isinstance(item, dict) and item.get("comparison") == "scientific_comparability" and item.get("scope", "full") == "full"]
        if not scientific_mappings:
            result.add("error", "comparison_policy", "scientific_reimplementation requires at least one full scientific_comparability mapping")
        for item in adoption.get("reference_outputs", []):
            if isinstance(item, dict) and item.get("comparison") == "scientific_comparability":
                _path(root, item.get("mapping_file"), "adoption.reference_outputs.mapping_file", result)
    _fixture_checks(root, input_rows, result)
    return result
