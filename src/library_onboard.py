#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import sys
import textwrap
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1"
TOOL_VERSION = "0.1.0"

REQUIRED_BUNDLE_FILES = (
    "bundle_manifest.json",
    "library_manifest.json",
    "inputs_manifest.tsv",
    "partition_plan.tsv",
    "model_plan.tsv",
    "questionnaire.json",
    "run_examples.md",
    "notes.md",
)

INPUT_HEADERS = (
    "input_id",
    "path_or_uri",
    "input_role",
    "workflow_stage",
    "format",
    "is_external_input",
    "required_for_rerun",
    "source_url_or_uri",
    "partition_scope",
    "notes",
)

PARTITION_HEADERS = (
    "partition_id",
    "partition_label",
    "partition_type",
    "partition_group",
    "input_id",
    "enabled",
    "notes",
)

MODEL_HEADERS = (
    "model_id",
    "model_family",
    "model_label",
    "input_mode",
    "workflow_variant",
    "extractor_archetype",
    "signed_output",
    "gene_set_pattern",
    "comparison_style",
    "distinct_algorithmic_feature",
    "description",
    "options_json",
    "enabled",
)

DEFAULT_LIBRARY_MANIFEST = {
    "library_name": "",
    "library_slug": "",
    "archetype": "",
    "workflow_archetype": "",
    "extractor_archetype": "",
    "source_project": "",
    "assay_type": "",
    "data_type": "",
    "organism": "",
    "genome_build": "",
    "input_granularity": "",
    "output_granularity": "",
    "signed_output": "",
    "natural_parallel_unit": "",
    "environment_profile": "",
    "expected_workflow_category": "",
    "output_mirror_uri": "",
    "notes": "",
}

DEFAULT_QUESTIONNAIRE = {
    "library_identity": {},
    "workflow_shape": {},
    "inputs": {},
    "models": {},
    "outputs": {},
}

ARCHETYPES: dict[str, dict[str, Any]] = {
    "released_de_rna": {
        "display_name": "Released differential-expression table to RNA gene sets",
        "description": "One released differential-expression table per partition, converted with DIG rna_deg.",
        "signed_output": True,
        "workflow_category": "convert_rna_deg",
        "input_role": "de_tsv",
        "required_options": (
            "signature_name_template",
            "postprocess_mode",
            "score_mode",
            "select",
        ),
        "default_options": {
            "signature_name_template": "{library_name}_{partition_label}_{model_id}",
            "postprocess_mode": "harmonizome",
            "score_mode": "auto",
            "select": "top_k",
            "normalize": "within_set_l1",
            "emit_full": True,
            "emit_gmt": True,
            "gmt_split_signed": True,
            "gmt_name_separator": "_",
            "gmt_signed_labels": "up_dn",
            "gmt_require_symbol": True,
            "emit_small_gene_sets": False,
        },
        "model_family": "released_de_rna",
        "description_template": (
            "{library_name} released differential-expression gene-set library for {partition_label} "
            "using model {model_id}: derived from a released differential-expression table and converted "
            "with DIG rna_deg."
        ),
    },
    "unsigned_term_gene": {
        "display_name": "Unsigned term-gene table to gene sets",
        "description": "One unsigned term-gene table per partition, converted with DIG unsigned_term_gene.",
        "signed_output": False,
        "workflow_category": "convert_unsigned_term_gene",
        "input_role": "table_tsv",
        "required_options": (
            "term_column",
            "gene_id_column",
            "gene_symbol_column",
        ),
        "default_options": {
            "term_column": "term",
            "gene_id_column": "gene_id",
            "gene_symbol_column": "gene_symbol",
            "score_column": "score",
            "term_prefix": "",
            "gmt_min_genes": 5,
            "gmt_require_symbol": True,
            "emit_small_gene_sets": False,
        },
        "model_family": "unsigned_term_gene",
        "description_template": (
            "{library_name} unsigned term-gene gene-set library for {partition_label} using model {model_id}: "
            "derived from a term-to-gene table and converted with DIG unsigned_term_gene."
        ),
    },
    "signed_term_gene": {
        "display_name": "Signed term-gene table to gene sets",
        "description": "One signed term-gene table per partition, converted with DIG signed_term_gene.",
        "signed_output": True,
        "workflow_category": "convert_signed_term_gene",
        "input_role": "table_tsv",
        "required_options": (
            "term_column",
            "gene_id_column",
            "gene_symbol_column",
            "score_column",
            "sign_column",
        ),
        "default_options": {
            "term_column": "term",
            "gene_id_column": "gene_id",
            "gene_symbol_column": "gene_symbol",
            "score_column": "score",
            "sign_column": "sign",
            "term_prefix": "",
            "gmt_name_separator": "_",
            "gmt_signed_labels": "up_dn",
            "gmt_min_genes": 5,
            "gmt_require_symbol": True,
            "emit_small_gene_sets": False,
        },
        "model_family": "signed_term_gene",
        "description_template": (
            "{library_name} signed term-gene gene-set library for {partition_label} using model {model_id}: "
            "derived from a signed term-to-gene table and converted with DIG signed_term_gene."
        ),
    },
}

WORKFLOW_ARCHETYPES: dict[str, dict[str, Any]] = {
    "simple_converter": {
        "display_name": "Simple converter-only workflow",
        "description": "One input per partition is sent directly to a DIG converter without a separate workflow stage.",
        "supported_extractor_archetypes": ("released_de_rna", "unsigned_term_gene", "signed_term_gene"),
        "environment_profile": "geneset_extractor_standard",
        "partition_axis": "partition",
        "comparison_axis": "model",
        "emits_intermediate_tables": False,
        "intermediate_file_roles": (),
    },
    "bulk_counts_multi_model": {
        "display_name": "Bulk counts with multiple model families",
        "description": "Counts plus metadata workflow that supports several model families over the same biological partitions.",
        "supported_extractor_archetypes": ("released_de_rna", "signed_term_gene"),
        "environment_profile": "geneset_extractor_standard",
        "partition_axis": "tissue",
        "comparison_axis": "model_or_comparison",
        "emits_intermediate_tables": True,
        "intermediate_file_roles": ("de_tsv", "signed_term_gene_tsv"),
    },
    "released_de_multi_partition": {
        "display_name": "Released differential-expression tables across partitions",
        "description": "One or more released DE tables are normalized and converted across biological partitions.",
        "supported_extractor_archetypes": ("released_de_rna", "signed_term_gene"),
        "environment_profile": "geneset_extractor_standard",
        "partition_axis": "partition",
        "comparison_axis": "model",
        "emits_intermediate_tables": False,
        "intermediate_file_roles": (),
    },
    "raw_counts_training_timecourse": {
        "display_name": "Raw counts training or timecourse workflow",
        "description": "Raw counts plus metadata workflow that computes contrasts before conversion.",
        "supported_extractor_archetypes": ("released_de_rna", "signed_term_gene"),
        "environment_profile": "geneset_extractor_r_heavy",
        "partition_axis": "tissue",
        "comparison_axis": "model_or_comparison",
        "emits_intermediate_tables": True,
        "intermediate_file_roles": ("de_tsv", "signed_term_gene_tsv"),
    },
    "matrix_signature_library": {
        "display_name": "Matrix signature library",
        "description": "A perturbation or signature matrix is reshaped into signed term-gene form before extraction.",
        "supported_extractor_archetypes": ("signed_term_gene",),
        "environment_profile": "geneset_extractor_standard",
        "partition_axis": "global_or_collection",
        "comparison_axis": "model",
        "emits_intermediate_tables": True,
        "intermediate_file_roles": ("signed_term_gene_tsv",),
    },
    "table_directory_marker_library": {
        "display_name": "Directory of marker tables to library",
        "description": "A directory of source tables is merged or normalized into an unsigned term-gene table before extraction.",
        "supported_extractor_archetypes": ("unsigned_term_gene",),
        "environment_profile": "geneset_extractor_standard",
        "partition_axis": "global_or_collection",
        "comparison_axis": "model",
        "emits_intermediate_tables": True,
        "intermediate_file_roles": ("unsigned_term_gene_tsv",),
    },
    "custom_hybrid": {
        "display_name": "Custom hybrid workflow",
        "description": "Controlled fallback for partially custom workflows that still use the standard bundle structure.",
        "supported_extractor_archetypes": ("released_de_rna", "unsigned_term_gene", "signed_term_gene"),
        "environment_profile": "maintainer_only",
        "partition_axis": "library_defined",
        "comparison_axis": "library_defined",
        "emits_intermediate_tables": True,
        "intermediate_file_roles": ("library_defined",),
    },
}

ENVIRONMENT_PROFILES: dict[str, dict[str, Any]] = {
    "geneset_extractor_standard": {
        "display_name": "Standard geneset-extractor environment",
        "apptainer_image_required": True,
        "python_required": True,
        "r_required": False,
        "allowed_wrapper_modes": ("direct", "apptainer", "cluster_apptainer"),
    },
    "geneset_extractor_r_heavy": {
        "display_name": "R-heavy geneset-extractor environment",
        "apptainer_image_required": True,
        "python_required": True,
        "r_required": True,
        "allowed_wrapper_modes": ("direct", "apptainer", "cluster_apptainer"),
    },
    "custom_approved_image": {
        "display_name": "Custom approved image",
        "apptainer_image_required": True,
        "python_required": True,
        "r_required": True,
        "allowed_wrapper_modes": ("apptainer", "cluster_apptainer"),
    },
    "maintainer_only": {
        "display_name": "Maintainer-side environment only",
        "apptainer_image_required": False,
        "python_required": True,
        "r_required": False,
        "allowed_wrapper_modes": ("direct",),
    },
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", value.strip())
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "library"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def legacy_workflow_archetype_for_extractor(extractor_archetype: str) -> str:
    if extractor_archetype in ARCHETYPES:
        return "simple_converter"
    return ""


def infer_workflow_archetype(library_manifest: dict[str, Any]) -> str:
    workflow_archetype = str(library_manifest.get("workflow_archetype", "")).strip()
    if workflow_archetype:
        return workflow_archetype
    extractor_archetype = (
        str(library_manifest.get("extractor_archetype", "")).strip()
        or str(library_manifest.get("archetype", "")).strip()
    )
    return legacy_workflow_archetype_for_extractor(extractor_archetype)


def infer_extractor_archetype(library_manifest: dict[str, Any]) -> str:
    extractor_archetype = str(library_manifest.get("extractor_archetype", "")).strip()
    if extractor_archetype:
        return extractor_archetype
    return str(library_manifest.get("archetype", "")).strip()


def infer_environment_profile(library_manifest: dict[str, Any]) -> str:
    environment_profile = str(library_manifest.get("environment_profile", "")).strip()
    if environment_profile:
        return environment_profile
    workflow_archetype = infer_workflow_archetype(library_manifest)
    if workflow_archetype in WORKFLOW_ARCHETYPES:
        return str(WORKFLOW_ARCHETYPES[workflow_archetype]["environment_profile"])
    return ""


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def make_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | 0o111)


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict[str, Any]], headers: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=list(headers), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            normalized = {field: stringify_tsv_value(row.get(field, "")) for field in headers}
            writer.writerow(normalized)


def stringify_tsv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def parse_bool(value: str | bool | None, default: bool | None = None) -> bool | None:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "t", "1", "yes", "y"}:
        return True
    if text in {"false", "f", "0", "no", "n"}:
        return False
    return default


def merge_key_values(existing: dict[str, Any], updates: list[str]) -> dict[str, Any]:
    payload = deepcopy(existing)
    for item in updates:
        if "=" not in item:
            raise SystemExit(f"Expected KEY=VALUE, got: {item}")
        key, raw_value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise SystemExit(f"Missing key in assignment: {item}")
        value: Any = raw_value
        if raw_value in {"true", "false"}:
            value = raw_value == "true"
        else:
            try:
                value = json.loads(raw_value)
            except json.JSONDecodeError:
                value = raw_value
        target = payload
        parts = key.split(".")
        for part in parts[:-1]:
            if part not in target or not isinstance(target[part], dict):
                target[part] = {}
            target = target[part]
        target[parts[-1]] = value
    return payload


def require_bundle_dir(path_text: str) -> Path:
    path = Path(path_text).expanduser().resolve()
    if not path.is_dir():
        raise SystemExit(f"Bundle directory not found: {path}")
    return path


def bundle_file_map(bundle_dir: Path) -> dict[str, Path]:
    return {name: bundle_dir / name for name in REQUIRED_BUNDLE_FILES}


def init_bundle(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir).expanduser().resolve()
    if out_dir.exists() and any(out_dir.iterdir()) and not args.force:
        raise SystemExit(f"Bundle directory already exists and is not empty: {out_dir}\nRe-run with --force to reuse it.")
    ensure_dir(out_dir)
    library_slug = slugify(args.library_name)
    archetype = args.archetype or ""
    workflow_archetype = args.workflow_archetype or legacy_workflow_archetype_for_extractor(archetype)
    extractor_archetype = archetype
    environment_profile = args.environment_profile or (
        WORKFLOW_ARCHETYPES[workflow_archetype]["environment_profile"]
        if workflow_archetype in WORKFLOW_ARCHETYPES
        else ""
    )
    files = bundle_file_map(out_dir)

    bundle_manifest = {
        "schema_version": SCHEMA_VERSION,
        "bundle_created_at": utc_now_iso(),
        "library_name": args.library_name,
        "library_slug": library_slug,
        "archetype": archetype,
        "workflow_archetype": workflow_archetype,
        "extractor_archetype": extractor_archetype,
        "collaborator_name": "",
        "contact_email": "",
        "bundle_tool_version": TOOL_VERSION,
        "contains_sample_inputs": False,
        "contains_sample_outputs": False,
    }
    library_manifest = deepcopy(DEFAULT_LIBRARY_MANIFEST)
    library_manifest["library_name"] = args.library_name
    library_manifest["library_slug"] = library_slug
    library_manifest["archetype"] = archetype
    library_manifest["workflow_archetype"] = workflow_archetype
    library_manifest["extractor_archetype"] = extractor_archetype
    library_manifest["environment_profile"] = environment_profile
    if extractor_archetype and extractor_archetype in ARCHETYPES:
        library_manifest["signed_output"] = stringify_tsv_value(ARCHETYPES[extractor_archetype]["signed_output"])
        library_manifest["expected_workflow_category"] = ARCHETYPES[extractor_archetype]["workflow_category"]
        library_manifest["output_mirror_uri"] = f"submission://{library_slug}_all_models"

    write_json(files["bundle_manifest.json"], bundle_manifest)
    write_json(files["library_manifest.json"], library_manifest)
    write_json(files["questionnaire.json"], deepcopy(DEFAULT_QUESTIONNAIRE))
    write_tsv(files["inputs_manifest.tsv"], [], INPUT_HEADERS)
    write_tsv(files["partition_plan.tsv"], [], PARTITION_HEADERS)
    write_tsv(files["model_plan.tsv"], [], MODEL_HEADERS)
    write_text(
        files["run_examples.md"],
        textwrap.dedent(
            f"""\
            # Run Examples

            This onboarding bundle was initialized on {utc_now_iso()}.

            Example next steps:

            ```bash
            bash geneset-extractor-dev/run/library_onboard.sh validate --bundle_dir {out_dir}
            bash geneset-extractor-dev/run/library_onboard.sh generate-package --bundle_dir {out_dir} --out_dir ./{library_slug}_package
            ```
            """
        ),
    )
    write_text(
        files["notes.md"],
        textwrap.dedent(
            """\
            # Notes

            Capture any library-specific notes, assumptions, or caveats here.
            """
        ),
    )
    print(f"Initialized onboarding bundle: {out_dir}")
    return 0


def questionnaire(args: argparse.Namespace) -> int:
    bundle_dir = require_bundle_dir(args.bundle_dir)
    path = bundle_dir / "questionnaire.json"
    payload = read_json(path)
    payload = merge_key_values(payload, args.set or [])
    write_json(path, payload)
    print(f"Updated questionnaire: {path}")
    return 0


def add_input(args: argparse.Namespace) -> int:
    bundle_dir = require_bundle_dir(args.bundle_dir)
    path = bundle_dir / "inputs_manifest.tsv"
    rows = read_tsv(path)
    for row in rows:
        if row["input_id"] == args.input_id:
            raise SystemExit(f"Duplicate input_id: {args.input_id}")
    rows.append(
        {
            "input_id": args.input_id,
            "path_or_uri": args.path_or_uri,
            "input_role": args.input_role,
            "workflow_stage": args.workflow_stage,
            "format": args.format,
            "is_external_input": stringify_tsv_value(parse_bool(args.is_external_input, True)),
            "required_for_rerun": stringify_tsv_value(parse_bool(args.required_for_rerun, True)),
            "source_url_or_uri": args.source_url_or_uri or "",
            "partition_scope": args.partition_scope or "",
            "notes": args.notes or "",
        }
    )
    write_tsv(path, rows, INPUT_HEADERS)
    print(f"Added input {args.input_id}")
    return 0


def add_partition(args: argparse.Namespace) -> int:
    bundle_dir = require_bundle_dir(args.bundle_dir)
    path = bundle_dir / "partition_plan.tsv"
    rows = read_tsv(path)
    for row in rows:
        if row["partition_id"] == args.partition_id:
            raise SystemExit(f"Duplicate partition_id: {args.partition_id}")
    rows.append(
        {
            "partition_id": args.partition_id,
            "partition_label": args.partition_label,
            "partition_type": args.partition_type,
            "partition_group": args.partition_group or "",
            "input_id": args.input_id,
            "enabled": stringify_tsv_value(parse_bool(args.enabled, True)),
            "notes": args.notes or "",
        }
    )
    write_tsv(path, rows, PARTITION_HEADERS)
    print(f"Added partition {args.partition_id}")
    return 0


def add_model(args: argparse.Namespace) -> int:
    bundle_dir = require_bundle_dir(args.bundle_dir)
    path = bundle_dir / "model_plan.tsv"
    rows = read_tsv(path)
    for row in rows:
        if row["model_id"] == args.model_id:
            raise SystemExit(f"Duplicate model_id: {args.model_id}")
    options_payload = {}
    if args.options_json:
        try:
            options_payload = json.loads(args.options_json)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid --options_json: {exc}") from exc
    rows.append(
        {
            "model_id": args.model_id,
            "model_family": args.model_family,
            "model_label": args.model_label,
            "input_mode": args.input_mode,
            "workflow_variant": args.workflow_variant or "",
            "extractor_archetype": args.extractor_archetype or "",
            "signed_output": stringify_tsv_value(parse_bool(args.signed_output, None)),
            "gene_set_pattern": args.gene_set_pattern,
            "comparison_style": args.comparison_style or "",
            "distinct_algorithmic_feature": args.distinct_algorithmic_feature,
            "description": args.description,
            "options_json": options_payload,
            "enabled": stringify_tsv_value(parse_bool(args.enabled, True)),
        }
    )
    write_tsv(path, rows, MODEL_HEADERS)
    print(f"Added model {args.model_id}")
    return 0


def validate_bundle_dir(bundle_dir: Path) -> tuple[list[str], list[str], dict[str, Any] | None]:
    errors: list[str] = []
    warnings: list[str] = []
    files = bundle_file_map(bundle_dir)
    for name, path in files.items():
        if not path.exists():
            errors.append(f"Missing required file: {name}")
    if errors:
        return errors, warnings, None

    bundle_manifest = read_json(files["bundle_manifest.json"])
    library_manifest = read_json(files["library_manifest.json"])
    questionnaire_payload = read_json(files["questionnaire.json"])
    if not isinstance(bundle_manifest, dict):
        errors.append("bundle_manifest.json must be a JSON object")
    if not isinstance(library_manifest, dict):
        errors.append("library_manifest.json must be a JSON object")
    if not isinstance(questionnaire_payload, dict):
        errors.append("questionnaire.json must be a JSON object")

    inputs_rows = read_tsv(files["inputs_manifest.tsv"])
    partition_rows = read_tsv(files["partition_plan.tsv"])
    model_rows = read_tsv(files["model_plan.tsv"])

    library_name = str(library_manifest.get("library_name", "")).strip()
    archetype = str(library_manifest.get("archetype", "")).strip()
    workflow_archetype = infer_workflow_archetype(library_manifest)
    extractor_archetype = infer_extractor_archetype(library_manifest)
    environment_profile = infer_environment_profile(library_manifest)
    organism = str(library_manifest.get("organism", "")).strip()
    if not library_name:
        errors.append("library_manifest.json missing library_name")
    if not organism:
        errors.append("library_manifest.json missing organism")
    if archetype and archetype not in ARCHETYPES:
        errors.append(f"Unsupported archetype: {archetype}")
    if workflow_archetype and workflow_archetype not in WORKFLOW_ARCHETYPES:
        errors.append(f"Unsupported workflow_archetype: {workflow_archetype}")
    if extractor_archetype and extractor_archetype not in ARCHETYPES:
        errors.append(f"Unsupported extractor_archetype: {extractor_archetype}")
    if environment_profile and environment_profile not in ENVIRONMENT_PROFILES:
        errors.append(f"Unsupported environment_profile: {environment_profile}")
    if workflow_archetype and extractor_archetype and workflow_archetype in WORKFLOW_ARCHETYPES:
        supported = set(WORKFLOW_ARCHETYPES[workflow_archetype]["supported_extractor_archetypes"])
        if extractor_archetype not in supported:
            errors.append(
                f"workflow_archetype {workflow_archetype} does not support extractor_archetype {extractor_archetype}"
            )
    if extractor_archetype and not str(library_manifest.get("expected_workflow_category", "")).strip():
        warnings.append("library_manifest.json missing expected_workflow_category for selected archetype")
    if not inputs_rows:
        errors.append("inputs_manifest.tsv must contain at least one input")
    if not partition_rows:
        errors.append("partition_plan.tsv must contain at least one partition")
    if not model_rows:
        errors.append("model_plan.tsv must contain at least one model")

    input_ids = set()
    external_inputs = 0
    for row in inputs_rows:
        input_id = row["input_id"].strip()
        if not input_id:
            errors.append("inputs_manifest.tsv contains a row with empty input_id")
            continue
        if input_id in input_ids:
            errors.append(f"Duplicate input_id in inputs_manifest.tsv: {input_id}")
        input_ids.add(input_id)
        is_external = parse_bool(row.get("is_external_input"), False)
        required = parse_bool(row.get("required_for_rerun"), False)
        source_uri = str(row.get("source_url_or_uri", "")).strip()
        local_ref = str(row.get("path_or_uri", "")).strip()
        if is_external:
            external_inputs += 1
        if required and not (source_uri or local_ref):
            errors.append(f"Input {input_id} is required_for_rerun but has no path_or_uri or source_url_or_uri")
        if not source_uri:
            warnings.append(f"Input {input_id} has no source_url_or_uri")
        if not str(row.get("workflow_stage", "")).strip():
            warnings.append(f"Input {input_id} has no workflow_stage")

    if external_inputs == 0:
        errors.append("At least one external input must be recorded")

    partition_ids = set()
    for row in partition_rows:
        partition_id = row["partition_id"].strip()
        if not partition_id:
            errors.append("partition_plan.tsv contains a row with empty partition_id")
            continue
        if partition_id in partition_ids:
            errors.append(f"Duplicate partition_id in partition_plan.tsv: {partition_id}")
        partition_ids.add(partition_id)
        input_id = row["input_id"].strip()
        if input_id and input_id not in input_ids:
            errors.append(f"Partition {partition_id} references unknown input_id: {input_id}")

    model_ids = set()
    for row in model_rows:
        model_id = row["model_id"].strip()
        if not model_id:
            errors.append("model_plan.tsv contains a row with empty model_id")
            continue
        if model_id in model_ids:
            errors.append(f"Duplicate model_id in model_plan.tsv: {model_id}")
        model_ids.add(model_id)
        signed_output = parse_bool(row.get("signed_output"), None)
        pattern = str(row.get("gene_set_pattern", "")).strip()
        if signed_output and "up" not in pattern.lower() and "dn" not in pattern.lower():
            warnings.append(f"Model {model_id} is signed_output=true but gene_set_pattern does not mention up/dn")
        options_json_text = str(row.get("options_json", "")).strip()
        options_payload = {}
        if options_json_text:
            try:
                options_payload = json.loads(options_json_text)
                if not isinstance(options_payload, dict):
                    errors.append(f"Model {model_id} options_json must decode to a JSON object")
                    options_payload = {}
            except json.JSONDecodeError as exc:
                errors.append(f"Model {model_id} has invalid options_json: {exc}")
        model_extractor = str(row.get("extractor_archetype", "")).strip() or extractor_archetype
        if model_extractor in ARCHETYPES:
            archetype_spec = ARCHETYPES[model_extractor]
            for option_name in archetype_spec["required_options"]:
                if option_name not in options_payload and option_name not in archetype_spec["default_options"]:
                    errors.append(f"Model {model_id} missing required options_json field: {option_name}")
        elif extractor_archetype:
            warnings.append(f"Model {model_id} does not resolve to a supported extractor archetype")
        if len(str(row.get("description", "")).strip()) < 10:
            warnings.append(f"Model {model_id} description is very short")

    if not str(bundle_manifest.get("schema_version", "")).strip():
        errors.append("bundle_manifest.json missing schema_version")
    if not str(bundle_manifest.get("library_name", "")).strip():
        errors.append("bundle_manifest.json missing library_name")

    context = {
        "bundle_manifest": bundle_manifest,
        "library_manifest": library_manifest,
        "questionnaire": questionnaire_payload,
        "inputs_rows": inputs_rows,
        "partition_rows": partition_rows,
        "model_rows": model_rows,
        "workflow_archetype": workflow_archetype,
        "extractor_archetype": extractor_archetype,
        "environment_profile": environment_profile,
    }
    return errors, warnings, context


def validate(args: argparse.Namespace) -> int:
    bundle_dir = require_bundle_dir(args.bundle_dir)
    errors, warnings, _ = validate_bundle_dir(bundle_dir)
    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Bundle is valid: {bundle_dir}")
    return 0


def package_bundle(args: argparse.Namespace) -> int:
    bundle_dir = require_bundle_dir(args.bundle_dir)
    errors, warnings, context = validate_bundle_dir(bundle_dir)
    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    assert context is not None
    out_zip = Path(args.out_zip).expanduser().resolve()
    ensure_dir(out_zip.parent)
    if out_zip.exists():
        out_zip.unlink()
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        root_name = bundle_dir.name
        for path in sorted(bundle_dir.rglob("*")):
            if path.is_file():
                handle.write(path, arcname=str(Path(root_name) / path.relative_to(bundle_dir)))
    print(f"Wrote bundle zip: {out_zip}")
    return 0


def extract_bundle_zip(bundle_zip: Path, temp_dir: Path) -> Path:
    with zipfile.ZipFile(bundle_zip, "r") as handle:
        handle.extractall(temp_dir)
    children = [path for path in temp_dir.iterdir() if path.is_dir()]
    if len(children) == 1:
        return children[0]
    return temp_dir


def load_bundle_source(bundle_dir: str | None, bundle_zip: str | None) -> Path:
    if bool(bundle_dir) == bool(bundle_zip):
        raise SystemExit("Provide exactly one of --bundle_dir or --bundle_zip")
    if bundle_dir:
        return require_bundle_dir(bundle_dir)
    zip_path = Path(str(bundle_zip)).expanduser().resolve()
    if not zip_path.is_file():
        raise SystemExit(f"Bundle zip not found: {zip_path}")
    temp_root = Path("/tmp") / f"library_onboard_{zip_path.stem}"
    if temp_root.exists():
        shutil.rmtree(temp_root)
    ensure_dir(temp_root)
    return extract_bundle_zip(zip_path, temp_root)


def inspect_bundle(args: argparse.Namespace) -> int:
    bundle_root = load_bundle_source(args.bundle_dir, args.bundle_zip)
    errors, warnings, context = validate_bundle_dir(bundle_root)
    if context:
        library_manifest = context["library_manifest"]
        print(json.dumps(
            {
                "library_name": library_manifest.get("library_name", ""),
                "library_slug": library_manifest.get("library_slug", ""),
                "archetype": library_manifest.get("archetype", ""),
                "workflow_archetype": infer_workflow_archetype(library_manifest),
                "extractor_archetype": infer_extractor_archetype(library_manifest),
                "environment_profile": infer_environment_profile(library_manifest),
                "organism": library_manifest.get("organism", ""),
                "genome_build": library_manifest.get("genome_build", ""),
                "n_inputs": len(context["inputs_rows"]),
                "n_partitions": len(context["partition_rows"]),
                "n_models": len(context["model_rows"]),
                "warnings": warnings,
                "errors": errors,
            },
            indent=2,
            sort_keys=True,
        ))
    else:
        print(json.dumps({"warnings": warnings, "errors": errors}, indent=2, sort_keys=True))
    return 1 if errors else 0


def validate_bundle_zip(args: argparse.Namespace) -> int:
    bundle_root = load_bundle_source(None, args.bundle_zip)
    errors, warnings, _ = validate_bundle_dir(bundle_root)
    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Bundle zip is valid: {args.bundle_zip}")
    return 0


def render_string_template(template: str, context: dict[str, Any]) -> str:
    class SafeMap(dict[str, Any]):
        def __missing__(self, key: str) -> str:
            return "{" + key + "}"

    flat: dict[str, Any] = {}

    def visit(prefix: str, value: Any) -> None:
        if isinstance(value, dict):
            for key, subvalue in value.items():
                next_prefix = f"{prefix}.{key}" if prefix else key
                visit(next_prefix, subvalue)
        else:
            flat[prefix] = value

    visit("", context)
    return template.format_map(SafeMap(flat))


def archetype_defaults(archetype: str) -> dict[str, Any]:
    spec = ARCHETYPES[archetype]
    return deepcopy(spec["default_options"])


def write_scaffold_files(out_dir: Path, context: dict[str, Any], runnable: bool) -> None:
    library_manifest = context["library_manifest"]
    model_rows = context["model_rows"]
    partition_rows = context["partition_rows"]
    archetype = str(library_manifest["archetype"]).strip()
    workflow_archetype = infer_workflow_archetype(library_manifest)
    extractor_archetype = infer_extractor_archetype(library_manifest)
    environment_profile = infer_environment_profile(library_manifest)
    library_name = str(library_manifest["library_name"]).strip()
    library_slug = str(library_manifest["library_slug"]).strip() or slugify(library_name)
    package_root = out_dir.resolve()
    ensure_dir(package_root)
    config_dir = package_root / "config"
    src_dir = package_root / "src"
    run_dir = package_root / "run"
    planning_dir = package_root / "planning"
    ensure_dir(config_dir)
    ensure_dir(src_dir)
    ensure_dir(run_dir)
    ensure_dir(planning_dir)

    write_json(config_dir / "library_config.json", library_manifest)
    write_json(config_dir / "bundle_manifest.json", context["bundle_manifest"])
    write_json(config_dir / "questionnaire.json", context["questionnaire"])
    write_json(
        config_dir / "workflow_manifest.json",
        {
            "workflow_archetype": workflow_archetype,
            "extractor_archetype": extractor_archetype,
            "entrypoint_template": f"src/build_{library_slug}_genesets.py",
            "partition_axis": WORKFLOW_ARCHETYPES[workflow_archetype]["partition_axis"],
            "comparison_axis": WORKFLOW_ARCHETYPES[workflow_archetype]["comparison_axis"],
            "emits_intermediate_tables": WORKFLOW_ARCHETYPES[workflow_archetype]["emits_intermediate_tables"],
            "intermediate_file_roles": list(WORKFLOW_ARCHETYPES[workflow_archetype]["intermediate_file_roles"]),
            "requires_refresh": True,
            "supports_apptainer": environment_profile != "maintainer_only",
            "environment_profile": environment_profile,
        },
    )
    write_json(
        config_dir / "environment_profile.json",
        {
            "environment_profile": environment_profile,
            **ENVIRONMENT_PROFILES[environment_profile],
        },
    )
    write_tsv(config_dir / "inputs_manifest.tsv", context["inputs_rows"], INPUT_HEADERS)
    write_tsv(config_dir / "partition_list.tsv", partition_rows, PARTITION_HEADERS)
    write_tsv(config_dir / "model_list.tsv", model_rows, MODEL_HEADERS)

    model_manifest_rows: list[dict[str, Any]] = []
    template_rows: list[dict[str, Any]] = []
    description_template = ARCHETYPES[extractor_archetype]["description_template"]
    for row in model_rows:
        options_payload = {}
        if str(row.get("options_json", "")).strip():
            options_payload = json.loads(str(row["options_json"]))
        merged_options = archetype_defaults(str(row.get("extractor_archetype", "")).strip() or extractor_archetype)
        merged_options.update(options_payload)
        model_manifest_rows.append(
            {
                "model_id": row["model_id"],
                "model_family": row["model_family"],
                "model_label": row["model_label"],
                "input_mode": row["input_mode"],
                "workflow_variant": row.get("workflow_variant", ""),
                "extractor_archetype": str(row.get("extractor_archetype", "")).strip() or extractor_archetype,
                "signed_output": row["signed_output"],
                "comparison_style": row.get("comparison_style", ""),
                "options_json": merged_options,
                "enabled": row["enabled"],
            }
        )
        template_rows.append(
            {
                "model_id": row["model_id"],
                "description_template": row["description"] or description_template,
            }
        )

    write_tsv(
        config_dir / "model_manifest.tsv",
        model_manifest_rows,
        (
            "model_id",
            "model_family",
            "model_label",
            "input_mode",
            "workflow_variant",
            "extractor_archetype",
            "signed_output",
            "comparison_style",
            "options_json",
            "enabled",
        ),
    )
    write_tsv(config_dir / "model_description_templates.tsv", template_rows, ("model_id", "description_template"))

    write_text(
        planning_dir / "pipeline_inputs.md",
        textwrap.dedent(
            f"""\
            # Pipeline Inputs

            Library: `{library_name}`
            Workflow archetype: `{workflow_archetype}`
            Extractor archetype: `{extractor_archetype}`
            Environment profile: `{environment_profile}`

            External inputs are defined in `config/inputs_manifest.tsv`.
            Partitions are defined in `config/partition_list.tsv`.
            Models are defined in `config/model_list.tsv`.
            """
        ),
    )
    write_text(
        planning_dir / "archetype_selection.md",
        textwrap.dedent(
            f"""\
            # Archetype Selection

            Selected workflow archetype: `{workflow_archetype}`
            Selected extractor archetype: `{extractor_archetype}`

            Workflow:
            {WORKFLOW_ARCHETYPES[workflow_archetype]["description"]}

            Extractor:
            {ARCHETYPES[extractor_archetype]["description"]}
            """
        ),
    )
    write_text(
        planning_dir / "package_summary.md",
        textwrap.dedent(
            f"""\
            # Package Summary

            This package was generated by `library_onboard` version `{TOOL_VERSION}`.

            Library: `{library_name}`
            Slug: `{library_slug}`
            Workflow archetype: `{workflow_archetype}`
            Extractor archetype: `{extractor_archetype}`
            Environment profile: `{environment_profile}`
            Runnable package: `{str(runnable).lower()}`
            """
        ),
    )

    runtime_code = build_generated_runtime_code(library_name, library_slug, archetype, workflow_archetype)
    build_code = build_generated_build_script(library_name, library_slug)
    run_model_code = build_generated_run_model_script(library_name, library_slug)
    validate_code = build_generated_validate_script(library_name, library_slug)

    write_text(src_dir / "generated_library_runtime.py", runtime_code)
    write_text(src_dir / f"build_{library_slug}_genesets.py", build_code)
    write_text(src_dir / f"run_{library_slug}_model.py", run_model_code)
    write_text(src_dir / f"validate_{library_slug}_outputs.py", validate_code)
    make_executable(src_dir / "generated_library_runtime.py")
    make_executable(src_dir / f"build_{library_slug}_genesets.py")
    make_executable(src_dir / f"run_{library_slug}_model.py")
    make_executable(src_dir / f"validate_{library_slug}_outputs.py")

    write_text(
        run_dir / f"build_{library_slug}_genesets.sh",
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            set -euo pipefail

            SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
            PACKAGE_ROOT="$(cd "${{SCRIPT_DIR}}/.." && pwd)"
            PYTHON_BIN="${{PYTHON_BIN:-python3}}"

            exec "${{PYTHON_BIN}}" "${{PACKAGE_ROOT}}/src/build_{library_slug}_genesets.py" "$@"
            """
        ),
    )
    make_executable(run_dir / f"build_{library_slug}_genesets.sh")
    write_text(
        run_dir / f"build_{library_slug}_genesets_apptainer.sh",
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            set -euo pipefail

            SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
            PACKAGE_ROOT="$(cd "${{SCRIPT_DIR}}/.." && pwd)"
            APPTAINER_BIN="${{APPTAINER_BIN:-apptainer}}"
            APPTAINER_IMAGE="${{APPTAINER_IMAGE:-}}"
            APPTAINER_EXTRA_ARGS="${{APPTAINER_EXTRA_ARGS:---cleanenv}}"
            APPTAINER_PYTHON_BIN="${{APPTAINER_PYTHON_BIN:-python}}"
            DIG_DIR="${{DIG_DIR:-}}"
            OUT_ROOT="${{OUT_ROOT:-${{PACKAGE_ROOT}}/outputs/{library_slug}_all_models}}"

            [[ -n "${{APPTAINER_IMAGE}}" ]] || {{ echo "Missing APPTAINER_IMAGE" >&2; exit 1; }}
            [[ -n "${{DIG_DIR}}" ]] || {{ echo "Missing DIG_DIR" >&2; exit 1; }}

            BIND_DIRS=("${{PACKAGE_ROOT}}" "${{DIG_DIR}}" "${{OUT_ROOT}}")
            BIND_ARG="$(IFS=,; printf '%s' "${{BIND_DIRS[*]}}")"

            exec "${{APPTAINER_BIN}}" exec --bind "${{BIND_ARG}}" ${{APPTAINER_EXTRA_ARGS}} "${{APPTAINER_IMAGE}}" \\
              bash --noprofile --norc -c \\
              "export PYTHON_BIN='${{APPTAINER_PYTHON_BIN}}'; export PYTHONPATH='${{DIG_DIR}}/src'; bash '${{PACKAGE_ROOT}}/run/build_{library_slug}_genesets.sh' --dig_dir '${{DIG_DIR}}' --out_root '${{OUT_ROOT}}' $*"
            """
        ),
    )
    make_executable(run_dir / f"build_{library_slug}_genesets_apptainer.sh")
    write_text(
        run_dir / f"validate_{library_slug}_outputs.sh",
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            set -euo pipefail

            SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
            PACKAGE_ROOT="$(cd "${{SCRIPT_DIR}}/.." && pwd)"
            PYTHON_BIN="${{PYTHON_BIN:-python3}}"
            OUT_ROOT="${{OUT_ROOT:-${{PACKAGE_ROOT}}/outputs/{library_slug}_all_models}}"

            exec "${{PYTHON_BIN}}" "${{PACKAGE_ROOT}}/src/validate_{library_slug}_outputs.py" --out_root "${{OUT_ROOT}}" "$@"
            """
        ),
    )
    make_executable(run_dir / f"validate_{library_slug}_outputs.sh")
    write_text(
        run_dir / "package_submission.sh",
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            set -euo pipefail

            SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
            PACKAGE_ROOT="$(cd "${{SCRIPT_DIR}}/.." && pwd)"
            OUT_ROOT="${{OUT_ROOT:-${{PACKAGE_ROOT}}/outputs/{library_slug}_all_models}}"
            SUBMISSION_DIR="${{SUBMISSION_DIR:-${{PACKAGE_ROOT}}/submission}}"
            ARCHIVE_PATH="${{ARCHIVE_PATH:-${{PACKAGE_ROOT}}/{library_slug}_submission.zip}}"

            mkdir -p "${{SUBMISSION_DIR}}"
            rm -rf "${{SUBMISSION_DIR}}/code" "${{SUBMISSION_DIR}}/outputs"
            cp -R "${{PACKAGE_ROOT}}/config" "${{SUBMISSION_DIR}}/code"
            cp -R "${{PACKAGE_ROOT}}/src" "${{SUBMISSION_DIR}}/code"
            cp -R "${{PACKAGE_ROOT}}/run" "${{SUBMISSION_DIR}}/code"
            cp -R "${{PACKAGE_ROOT}}/planning" "${{SUBMISSION_DIR}}/code"
            cp -R "${{OUT_ROOT}}" "${{SUBMISSION_DIR}}/outputs"
            (cd "${{SUBMISSION_DIR}}" && zip -r "${{ARCHIVE_PATH}}" .)
            """
        ),
    )
    make_executable(run_dir / "package_submission.sh")
    write_text(
        package_root / "README.md",
        textwrap.dedent(
            f"""\
            # {library_name} Generated Package

            This package was generated by `library_onboard` version `{TOOL_VERSION}`.

            Workflow archetype: `{workflow_archetype}`
            Extractor archetype: `{extractor_archetype}`
            Environment profile: `{environment_profile}`

            Build locally:

            ```bash
            bash run/build_{library_slug}_genesets.sh --dig_dir /path/to/dig-gene-set-extractors --out_root ./outputs/{library_slug}_all_models
            ```

            Build in Apptainer:

            ```bash
            export APPTAINER_IMAGE=/path/to/geneset-extractor.sif
            export DIG_DIR=/path/to/dig-gene-set-extractors
            bash run/build_{library_slug}_genesets_apptainer.sh
            ```

            Validate:

            ```bash
            bash run/validate_{library_slug}_outputs.sh
            ```
            """
        ),
    )


def build_generated_runtime_code(library_name: str, library_slug: str, archetype: str, workflow_archetype: str) -> str:
    spec = ARCHETYPES[archetype]
    workflow_spec = WORKFLOW_ARCHETYPES[workflow_archetype]
    return textwrap.dedent(
        f"""\
        #!/usr/bin/env python3
        from __future__ import annotations

        import csv
        import gzip
        import json
        import os
        import re
        import shutil
        import subprocess
        import sys
        from pathlib import Path

        LIBRARY_NAME = {library_name!r}
        LIBRARY_SLUG = {library_slug!r}
        ARCHETYPE = {archetype!r}
        ARCHETYPE_SPEC = {json.dumps(spec, sort_keys=True, indent=2)}
        WORKFLOW_ARCHETYPE = {workflow_archetype!r}
        WORKFLOW_SPEC = {json.dumps(workflow_spec, sort_keys=True, indent=2)}


        def read_tsv(path: Path):
            with path.open("r", encoding="utf-8", newline="") as handle:
                return list(csv.DictReader(handle, delimiter="\\t"))


        def read_json(path: Path):
            return json.loads(path.read_text(encoding="utf-8"))


        def write_json(path: Path, payload):
            path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\\n", encoding="utf-8")


        def open_text_auto(path: Path):
            if path.suffix == ".gz":
                return gzip.open(path, "rt", encoding="utf-8", newline="")
            return path.open("r", encoding="utf-8", newline="")


        def stringify(value):
            if value is None:
                return ""
            if isinstance(value, bool):
                return "true" if value else "false"
            if isinstance(value, (dict, list)):
                return json.dumps(value, sort_keys=True)
            return str(value)


        def parse_bool(value, default=None):
            if value is None:
                return default
            text = str(value).strip().lower()
            if text in {{"true", "1", "yes", "y"}}:
                return True
            if text in {{"false", "0", "no", "n"}}:
                return False
            return default


        def render_template(template, context):
            class SafeMap(dict):
                def __missing__(self, key):
                    return "{{" + key + "}}"
            return template.format_map(SafeMap(context))


        def library_root() -> Path:
            return Path(__file__).resolve().parent.parent


        def config_dir() -> Path:
            return library_root() / "config"


        def load_bundle():
            return {{
                "library_config": read_json(config_dir() / "library_config.json"),
                "bundle_manifest": read_json(config_dir() / "bundle_manifest.json"),
                "questionnaire": read_json(config_dir() / "questionnaire.json"),
                "workflow_manifest": read_json(config_dir() / "workflow_manifest.json"),
                "environment_profile": read_json(config_dir() / "environment_profile.json"),
                "inputs": read_tsv(config_dir() / "inputs_manifest.tsv"),
                "partitions": read_tsv(config_dir() / "partition_list.tsv"),
                "models": read_tsv(config_dir() / "model_list.tsv"),
                "model_manifest": read_tsv(config_dir() / "model_manifest.tsv"),
                "description_templates": read_tsv(config_dir() / "model_description_templates.tsv"),
            }}


        def input_map(bundle):
            return {{row["input_id"]: row for row in bundle["inputs"]}}


        def model_manifest_map(bundle):
            return {{row["model_id"]: row for row in bundle["model_manifest"]}}


        def description_template_map(bundle):
            return {{row["model_id"]: row["description_template"] for row in bundle["description_templates"]}}


        def resolve_input_path(row):
            text = str(row.get("path_or_uri", "")).strip()
            if not text:
                raise SystemExit(f"Missing path_or_uri for input_id={{row.get('input_id', '')}}")
            return Path(text).expanduser().resolve()


        def build_converter_command(*, python_bin, dig_dir, archetype, options, input_path, out_dir, library_config, partition, model):
            cmd = [str(python_bin), "-m", "geneset_extractors.cli", "convert"]
            organism = library_config["organism"]
            genome_build = library_config["genome_build"]
            if archetype == "released_de_rna":
                signature_name = render_template(
                    str(options.get("signature_name_template", "{{library_name}}_{{partition_label}}_{{model_id}}")),
                    {{
                        "library_name": LIBRARY_NAME,
                        "partition_id": partition["partition_id"],
                        "partition_label": partition["partition_label"],
                        "model_id": model["model_id"],
                    }},
                )
                cmd += [
                    "rna_deg",
                    "--deg_tsv", str(input_path),
                    "--out_dir", str(out_dir),
                    "--organism", organism,
                    "--genome_build", genome_build,
                    "--signature_name", signature_name,
                    "--postprocess_mode", str(options.get("postprocess_mode", "harmonizome")),
                    "--score_mode", str(options.get("score_mode", "auto")),
                    "--select", str(options.get("select", "top_k")),
                    "--normalize", str(options.get("normalize", "within_set_l1")),
                    "--emit_full", str(options.get("emit_full", True)).lower(),
                    "--emit_gmt", str(options.get("emit_gmt", True)).lower(),
                    "--gmt_split_signed", str(options.get("gmt_split_signed", True)).lower(),
                    "--gmt_name_separator", str(options.get("gmt_name_separator", "_")),
                    "--gmt_signed_labels", str(options.get("gmt_signed_labels", "up_dn")),
                    "--gmt_require_symbol", str(options.get("gmt_require_symbol", True)).lower(),
                    "--emit_small_gene_sets", str(options.get("emit_small_gene_sets", False)).lower(),
                ]
                for optional_name in [
                    "padj_max", "min_score", "top_k", "gmt_source", "gmt_topk_list",
                    "gmt_min_genes", "gmt_max_genes", "gtf", "gmt_biotype_allowlist",
                    "min_abs_logfc",
                ]:
                    if optional_name in options and str(options[optional_name]).strip() not in {{"", "NA", "None"}}:
                        cmd += [f"--{{optional_name}}", str(options[optional_name])]
                if parse_bool(options.get("disable_default_excludes"), False):
                    cmd.append("--disable_default_excludes")
                return cmd
            if archetype == "unsigned_term_gene":
                cmd += [
                    "unsigned_term_gene",
                    "--table_tsv", str(input_path),
                    "--out_dir", str(out_dir),
                    "--organism", organism,
                    "--genome_build", genome_build,
                    "--term_column", str(options.get("term_column", "term")),
                    "--gene_id_column", str(options.get("gene_id_column", "gene_id")),
                    "--gene_symbol_column", str(options.get("gene_symbol_column", "gene_symbol")),
                ]
                if str(options.get("score_column", "")).strip():
                    cmd += ["--score_column", str(options["score_column"])]
                if str(options.get("term_prefix", "")).strip():
                    cmd += ["--term_prefix", str(options["term_prefix"])]
                cmd += [
                    "--gmt_min_genes", str(options.get("gmt_min_genes", 5)),
                    "--gmt_require_symbol", str(options.get("gmt_require_symbol", True)).lower(),
                    "--emit_small_gene_sets", str(options.get("emit_small_gene_sets", False)).lower(),
                ]
                return cmd
            if archetype == "signed_term_gene":
                cmd += [
                    "signed_term_gene",
                    "--table_tsv", str(input_path),
                    "--out_dir", str(out_dir),
                    "--organism", organism,
                    "--genome_build", genome_build,
                    "--term_column", str(options.get("term_column", "term")),
                    "--gene_id_column", str(options.get("gene_id_column", "gene_id")),
                    "--gene_symbol_column", str(options.get("gene_symbol_column", "gene_symbol")),
                    "--score_column", str(options.get("score_column", "score")),
                    "--sign_column", str(options.get("sign_column", "sign")),
                    "--gmt_name_separator", str(options.get("gmt_name_separator", "_")),
                    "--gmt_signed_labels", str(options.get("gmt_signed_labels", "up_dn")),
                    "--gmt_min_genes", str(options.get("gmt_min_genes", 5)),
                    "--gmt_require_symbol", str(options.get("gmt_require_symbol", True)).lower(),
                    "--emit_small_gene_sets", str(options.get("emit_small_gene_sets", False)).lower(),
                ]
                if str(options.get("term_prefix", "")).strip():
                    cmd += ["--term_prefix", str(options["term_prefix"])]
                return cmd
            raise SystemExit(f"Unsupported archetype: {{archetype}}")


        def run_command(cmd, *, cwd, env, log_path):
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write("$ " + " ".join(cmd) + "\\n")
            proc = subprocess.run(cmd, cwd=str(cwd), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
            with log_path.open("a", encoding="utf-8") as handle:
                if proc.stdout:
                    handle.write(proc.stdout)
                if proc.stdout and not proc.stdout.endswith("\\n"):
                    handle.write("\\n")
            if proc.returncode != 0:
                raise subprocess.CalledProcessError(proc.returncode, cmd)


        def first_existing(paths):
            for path in paths:
                if path.exists():
                    return path
            return None


        def recursive_replace(value, replacements):
            if isinstance(value, str):
                result = value
                for source, target in replacements:
                    result = result.replace(source, target)
                return result
            if isinstance(value, list):
                return [recursive_replace(item, replacements) for item in value]
            if isinstance(value, dict):
                return {{str(key): recursive_replace(item, replacements) for key, item in value.items()}}
            return value


        def build_replacements(*, out_root, output_mirror_uri, input_rows):
            replacements = []
            output_prefix = str(Path(out_root).resolve())
            replacements.append((output_prefix, output_mirror_uri.rstrip("/")))
            for row in input_rows:
                local_path = str(row.get("path_or_uri", "")).strip()
                source_uri = str(row.get("source_url_or_uri", "")).strip()
                if local_path and source_uri and "://" not in local_path:
                    replacements.append((str(Path(local_path).expanduser().resolve()), source_uri))
            replacements.sort(key=lambda item: len(item[0]), reverse=True)
            return replacements


        def backup_if_missing(path: Path):
            backup = Path(str(path) + ".orig")
            if path.exists() and not backup.exists():
                shutil.copy2(path, backup)


        def default_row_description(*, model_description, set_name):
            lower = set_name.lower()
            if lower.endswith("_up"):
                return "Up-regulated genes from " + model_description.rstrip(".") + "."
            if lower.endswith("_dn"):
                return "Down-regulated genes from " + model_description.rstrip(".") + "."
            return model_description


        def patch_gmt(gmt_path: Path, model_description: str):
            if not gmt_path.exists():
                return
            backup_if_missing(gmt_path)
            lines = []
            with gmt_path.open("r", encoding="utf-8") as handle:
                for raw_line in handle:
                    line = raw_line.rstrip("\\n")
                    if not line:
                        lines.append("")
                        continue
                    parts = line.split("\\t")
                    if len(parts) >= 2:
                        parts[1] = default_row_description(model_description=model_description, set_name=parts[0])
                    lines.append("\\t".join(parts))
            gmt_path.write_text("\\n".join(lines) + "\\n", encoding="utf-8")


        def patch_meta(meta_path: Path, *, model_payload, model_description, replacements):
            if not meta_path.exists():
                return
            backup_if_missing(meta_path)
            payload = read_json(meta_path)
            payload = recursive_replace(payload, replacements)
            payload["description"] = model_description
            payload.setdefault("gene_set", {{}})
            if isinstance(payload["gene_set"], dict):
                payload["gene_set"]["description"] = model_description
            payload["model"] = model_payload
            payload["inputs"] = model_payload.get("inputs", {{}})
            payload["naming"] = model_payload.get("naming", {{}})
            write_json(meta_path, payload)


        def patch_provenance(prov_path: Path, *, model_description, replacements):
            if not prov_path.exists():
                return
            backup_if_missing(prov_path)
            payload = read_json(prov_path)
            payload = recursive_replace(payload, replacements)
            if isinstance(payload, dict):
                for root in payload.values():
                    if isinstance(root, dict) and isinstance(root.get("nodes"), list):
                        for node in root["nodes"]:
                            if isinstance(node, dict) and node.get("type") == "GeneSet":
                                node["description"] = model_description
                                props = node.setdefault("c2m2_properties", {{}})
                                if isinstance(props, dict):
                                    props["description"] = model_description
            write_json(prov_path, payload)


        def write_model_json(path: Path, payload):
            write_json(path, payload)


        def build_model_payload(*, library_config, partition, model, options, input_row):
            pattern = str(model.get("gene_set_pattern", "")).strip()
            return {{
                "schema_version": "1",
                "library": library_config["library_name"],
                "library_slug": library_config["library_slug"],
                "archetype": library_config["archetype"],
                "workflow_archetype": library_config.get("workflow_archetype", ""),
                "extractor_archetype": model.get("extractor_archetype") or library_config.get("extractor_archetype", library_config["archetype"]),
                "environment_profile": library_config.get("environment_profile", ""),
                "model_id": model["model_id"],
                "model_group": model["model_family"],
                "model_label": model["model_label"],
                "partition_id": partition["partition_id"],
                "partition_label": partition["partition_label"],
                "workflow_name": ARCHETYPE_SPEC["workflow_category"],
                "extractor_name": ARCHETYPE_SPEC["workflow_category"],
                "parameters": options,
                "inputs": {{
                    "organism": library_config["organism"],
                    "genome_build": library_config["genome_build"],
                    "input_id": input_row["input_id"],
                    "input_role": input_row["input_role"],
                    "workflow_stage": input_row.get("workflow_stage", ""),
                    "source_url_or_uri": input_row["source_url_or_uri"],
                    "format": input_row["format"],
                }},
                "naming": {{
                    "comparison_style": model.get("comparison_style", "") or ARCHETYPE,
                    "partition_label": partition["partition_label"],
                    "gene_set_pattern": pattern,
                }},
            }}


        def detect_delimiter(path: Path, explicit_delimiter: str | None = None) -> str:
            if explicit_delimiter:
                return explicit_delimiter
            name = path.name.lower()
            if name.endswith(".csv") or name.endswith(".csv.gz"):
                return ","
            return "\\t"


        def filename_stem(path: Path) -> str:
            name = path.name
            for suffix in (".tsv.gz", ".csv.gz", ".txt.gz", ".tsv", ".csv", ".txt"):
                if name.endswith(suffix):
                    return name[: -len(suffix)]
            return path.stem


        def normalize_term_label(value: str) -> str:
            text = re.sub(r"[^A-Za-z0-9]+", "_", value.strip())
            text = re.sub(r"_+", "_", text).strip("_")
            return text or "term"


        def detect_matrix_delimiter(path: Path, explicit_delimiter: str | None = None) -> str:
            if explicit_delimiter:
                return explicit_delimiter
            name = path.name.lower()
            if name.endswith(".csv") or name.endswith(".csv.gz"):
                return ","
            return "\\t"


        def load_mapping_table(path: Path, *, key_column: str, value_column: str, delimiter: str | None = None):
            mapping = {{}}
            detected_delimiter = detect_matrix_delimiter(path, delimiter)
            with open_text_auto(path) as handle:
                reader = csv.DictReader(handle, delimiter=detected_delimiter)
                if reader.fieldnames is None:
                    raise SystemExit(f"Mapping file has no header: {{path}}")
                fieldnames = set(reader.fieldnames)
                if key_column not in fieldnames or value_column not in fieldnames:
                    raise SystemExit(
                        f"Mapping file {{path}} missing required columns {{key_column!r}}/{{value_column!r}}. "
                        f"Columns: {{sorted(fieldnames)}}"
                    )
                for row in reader:
                    key = str(row.get(key_column, "")).strip()
                    value = str(row.get(value_column, "")).strip()
                    if key and value and key not in mapping:
                        mapping[key] = value
            return mapping


        def prepare_table_directory_marker_library(*, input_path: Path, workflow_dir: Path, model, options, partition):
            if not input_path.is_dir():
                raise SystemExit(f"table_directory_marker_library expects a directory input, got: {{input_path}}")
            workflow_dir.mkdir(parents=True, exist_ok=True)
            glob_pattern = str(options.get("workflow_glob", "*"))
            explicit_delimiter = str(options.get("workflow_delimiter", "")).strip() or None
            workflow_output = workflow_dir / "prepared_unsigned_term_gene.tsv"
            manifest_path = workflow_dir / "workflow_manifest.json"
            gene_id_column = str(options.get("workflow_gene_id_column", options.get("gene_id_column", "gene_id")))
            gene_symbol_column = str(options.get("workflow_gene_symbol_column", options.get("gene_symbol_column", "gene_symbol")))
            score_column = str(options.get("workflow_score_column", options.get("score_column", ""))).strip()
            term_column = str(options.get("workflow_term_column", "")).strip()
            term_prefix = str(options.get("workflow_term_prefix", options.get("term_prefix", ""))).strip()
            file_term_strategy = str(options.get("workflow_term_strategy", "filename")).strip() or "filename"
            source_files = sorted(path for path in input_path.rglob(glob_pattern) if path.is_file())
            if not source_files:
                raise SystemExit(f"No source files matched workflow_glob={{glob_pattern!r}} under {{input_path}}")
            n_rows = 0
            with workflow_output.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    delimiter="\\t",
                    fieldnames=["term", "gene_id", "gene_symbol", "score"],
                    lineterminator="\\n",
                )
                writer.writeheader()
                for source_path in source_files:
                    delimiter = detect_delimiter(source_path, explicit_delimiter)
                    with open_text_auto(source_path) as source_handle:
                        reader = csv.DictReader(source_handle, delimiter=delimiter)
                        if reader.fieldnames is None:
                            continue
                        fieldnames = set(reader.fieldnames)
                        if gene_id_column not in fieldnames:
                            raise SystemExit(
                                f"Missing workflow gene_id column {{gene_id_column!r}} in {{source_path}}. "
                                f"Columns: {{sorted(fieldnames)}}"
                            )
                        if gene_symbol_column not in fieldnames:
                            raise SystemExit(
                                f"Missing workflow gene_symbol column {{gene_symbol_column!r}} in {{source_path}}. "
                                f"Columns: {{sorted(fieldnames)}}"
                            )
                        if score_column and score_column not in fieldnames:
                            raise SystemExit(
                                f"Missing workflow score column {{score_column!r}} in {{source_path}}. "
                                f"Columns: {{sorted(fieldnames)}}"
                            )
                        if term_column and term_column not in fieldnames:
                            raise SystemExit(
                                f"Missing workflow term column {{term_column!r}} in {{source_path}}. "
                                f"Columns: {{sorted(fieldnames)}}"
                            )
                        base_term = filename_stem(source_path)
                        for row in reader:
                            if term_column:
                                term_value = str(row.get(term_column, "")).strip()
                            elif file_term_strategy == "filename":
                                term_value = base_term
                            else:
                                term_value = base_term
                            term_value = normalize_term_label(term_value)
                            if term_prefix:
                                term_value = f"{{term_prefix}}_{{term_value}}"
                            gene_id = str(row.get(gene_id_column, "")).strip()
                            gene_symbol = str(row.get(gene_symbol_column, "")).strip()
                            if not gene_id and not gene_symbol:
                                continue
                            score_value = str(row.get(score_column, "")).strip() if score_column else ""
                            if not score_value:
                                score_value = "1"
                            writer.writerow(
                                {{
                                    "term": term_value,
                                    "gene_id": gene_id,
                                    "gene_symbol": gene_symbol,
                                    "score": score_value,
                                }}
                            )
                            n_rows += 1
            write_json(
                manifest_path,
                {{
                    "workflow_archetype": WORKFLOW_ARCHETYPE,
                    "partition_id": partition["partition_id"],
                    "model_id": model["model_id"],
                    "input_path": str(input_path),
                    "source_files": [str(path) for path in source_files],
                    "workflow_output": str(workflow_output),
                    "n_source_files": len(source_files),
                    "n_rows": n_rows,
                    "workflow_options": {{
                        "workflow_glob": glob_pattern,
                        "workflow_term_strategy": file_term_strategy,
                        "workflow_term_column": term_column,
                        "workflow_gene_id_column": gene_id_column,
                        "workflow_gene_symbol_column": gene_symbol_column,
                        "workflow_score_column": score_column,
                        "workflow_term_prefix": term_prefix,
                    }},
                }},
            )
            return workflow_output


        def prepare_matrix_signature_library(*, input_path: Path, workflow_dir: Path, model, options, partition):
            if not input_path.is_file():
                raise SystemExit(f"matrix_signature_library expects a file input, got: {{input_path}}")
            workflow_dir.mkdir(parents=True, exist_ok=True)
            matrix_delimiter = detect_matrix_delimiter(input_path, str(options.get("workflow_delimiter", "")).strip() or None)
            feature_id_column = str(options.get("workflow_feature_id_column", "")).strip()
            direct_gene_symbol_column = str(options.get("workflow_gene_symbol_column", "")).strip()
            direct_gene_id_column = str(options.get("workflow_gene_id_output_column", "gene_id")).strip() or "gene_id"
            sign_threshold = float(options.get("workflow_sign_threshold", 0))
            abs_score_min = float(options.get("workflow_abs_score_min", 0))
            emit_zero_rows = parse_bool(options.get("workflow_emit_zero_rows"), False)
            positive_label = str(options.get("workflow_positive_label", "+")).strip() or "+"
            negative_label = str(options.get("workflow_negative_label", "-")).strip() or "-"
            term_prefix = str(options.get("workflow_term_prefix", options.get("term_prefix", ""))).strip()

            mapping_input_id = str(options.get("workflow_mapping_input_id", "")).strip()
            mapping_key_column = str(options.get("workflow_mapping_key_column", "")).strip()
            mapping_value_column = str(options.get("workflow_mapping_value_column", "")).strip()
            mapping_delimiter = str(options.get("workflow_mapping_delimiter", "")).strip() or None
            mapping_table = {{}}
            mapping_path = None
            if mapping_input_id:
                bundle = load_bundle()
                input_lookup = input_map(bundle)
                if mapping_input_id not in input_lookup:
                    raise SystemExit(f"workflow_mapping_input_id not found in bundle inputs: {{mapping_input_id}}")
                mapping_row = input_lookup[mapping_input_id]
                mapping_path = resolve_input_path(mapping_row)
                if not mapping_key_column or not mapping_value_column:
                    raise SystemExit(
                        "matrix_signature_library with workflow_mapping_input_id also requires "
                        "workflow_mapping_key_column and workflow_mapping_value_column"
                    )
                mapping_table = load_mapping_table(
                    mapping_path,
                    key_column=mapping_key_column,
                    value_column=mapping_value_column,
                    delimiter=mapping_delimiter,
                )

            workflow_output = workflow_dir / "prepared_signed_term_gene.tsv"
            manifest_path = workflow_dir / "workflow_manifest.json"
            n_rows = 0
            n_terms = 0
            missing_mapping_values = 0
            with open_text_auto(input_path) as handle, workflow_output.open("w", encoding="utf-8", newline="") as out_handle:
                reader = csv.DictReader(handle, delimiter=matrix_delimiter)
                if reader.fieldnames is None:
                    raise SystemExit(f"Matrix input has no header: {{input_path}}")
                fieldnames = list(reader.fieldnames)
                if feature_id_column:
                    if feature_id_column not in fieldnames:
                        raise SystemExit(
                            f"Matrix input {{input_path}} missing workflow_feature_id_column {{feature_id_column!r}}. "
                            f"Columns: {{fieldnames}}"
                        )
                    signature_columns = [name for name in fieldnames if name != feature_id_column]
                elif direct_gene_symbol_column:
                    if direct_gene_symbol_column not in fieldnames:
                        raise SystemExit(
                            f"Matrix input {{input_path}} missing workflow_gene_symbol_column {{direct_gene_symbol_column!r}}. "
                            f"Columns: {{fieldnames}}"
                        )
                    signature_columns = [name for name in fieldnames if name != direct_gene_symbol_column]
                else:
                    raise SystemExit(
                        "matrix_signature_library requires either workflow_feature_id_column plus mapping input, "
                        "or workflow_gene_symbol_column for direct matrix parsing"
                    )
                writer = csv.DictWriter(
                    out_handle,
                    delimiter="\\t",
                    fieldnames=["term", "gene_id", "gene_symbol", "score", "sign"],
                    lineterminator="\\n",
                )
                writer.writeheader()
                normalized_terms = []
                for signature_name in signature_columns:
                    term_name = normalize_term_label(signature_name)
                    if term_prefix:
                        term_name = f"{{term_prefix}}_{{term_name}}"
                    normalized_terms.append((signature_name, term_name))
                n_terms = len(normalized_terms)
                for row in reader:
                    if feature_id_column:
                        feature_id = str(row.get(feature_id_column, "")).strip()
                        gene_symbol = mapping_table.get(feature_id, "")
                        gene_id = feature_id
                        if not gene_symbol:
                            missing_mapping_values += 1
                            continue
                    else:
                        gene_symbol = str(row.get(direct_gene_symbol_column, "")).strip()
                        gene_id = gene_symbol
                    if not gene_symbol:
                        continue
                    for raw_term, normalized_term in normalized_terms:
                        raw_value = str(row.get(raw_term, "")).strip()
                        if raw_value == "":
                            continue
                        try:
                            numeric_value = float(raw_value)
                        except ValueError:
                            continue
                        if abs(numeric_value) < abs_score_min:
                            continue
                        if numeric_value > sign_threshold:
                            sign_value = positive_label
                        elif numeric_value < -sign_threshold:
                            sign_value = negative_label
                        elif emit_zero_rows:
                            sign_value = positive_label
                        else:
                            continue
                        writer.writerow(
                            {{
                                "term": normalized_term,
                                "gene_id": gene_id,
                                "gene_symbol": gene_symbol,
                                "score": str(abs(numeric_value)),
                                "sign": sign_value,
                            }}
                        )
                        n_rows += 1
            write_json(
                manifest_path,
                {{
                    "workflow_archetype": WORKFLOW_ARCHETYPE,
                    "partition_id": partition["partition_id"],
                    "model_id": model["model_id"],
                    "input_path": str(input_path),
                    "mapping_input_path": str(mapping_path) if mapping_path else "",
                    "workflow_output": str(workflow_output),
                    "n_terms": n_terms,
                    "n_rows": n_rows,
                    "missing_mapping_values": missing_mapping_values,
                    "workflow_options": {{
                        "workflow_feature_id_column": feature_id_column,
                        "workflow_gene_symbol_column": direct_gene_symbol_column,
                        "workflow_mapping_input_id": mapping_input_id,
                        "workflow_mapping_key_column": mapping_key_column,
                        "workflow_mapping_value_column": mapping_value_column,
                        "workflow_sign_threshold": sign_threshold,
                        "workflow_abs_score_min": abs_score_min,
                        "workflow_term_prefix": term_prefix,
                    }},
                }},
            )
            return workflow_output


        def prepare_workflow_input(*, workflow_archetype, input_path: Path, workflow_dir: Path, model, options, partition):
            if workflow_archetype == "simple_converter":
                return input_path
            if workflow_archetype == "table_directory_marker_library":
                return prepare_table_directory_marker_library(
                    input_path=input_path,
                    workflow_dir=workflow_dir,
                    model=model,
                    options=options,
                    partition=partition,
                )
            if workflow_archetype == "matrix_signature_library":
                return prepare_matrix_signature_library(
                    input_path=input_path,
                    workflow_dir=workflow_dir,
                    model=model,
                    options=options,
                    partition=partition,
                )
            raise SystemExit(
                f"Generated package does not yet implement workflow_archetype={{workflow_archetype!r}}. "
                "Use a simple-converter archetype or extend the workflow generator."
            )


        def find_artifacts(extractor_dir: Path):
            gmt_path = extractor_dir / "genesets.gmt"
            meta_path = first_existing([extractor_dir / "geneset.meta.json"])
            prov_path = first_existing([extractor_dir / "geneset.provenance.json"])
            return gmt_path, meta_path, prov_path
        """
    )


def build_generated_build_script(library_name: str, library_slug: str) -> str:
    return textwrap.dedent(
        f"""\
        #!/usr/bin/env python3
        from __future__ import annotations

        import argparse
        import json
        import subprocess
        import sys
        from pathlib import Path

        from generated_library_runtime import (
            input_map,
            library_root,
            load_bundle,
            model_manifest_map,
            parse_bool,
        )


        def build_parser():
            parser = argparse.ArgumentParser()
            parser.add_argument("--dig_dir", required=True)
            parser.add_argument("--out_root", default=str(library_root() / "outputs" / "{library_slug}_all_models"))
            parser.add_argument("--python_bin", default=sys.executable or "python3")
            parser.add_argument("--models", default="all")
            parser.add_argument("--partitions", default="all")
            parser.add_argument("--overwrite", action="store_true")
            return parser


        def resolve_csv(csv_text, valid_ids):
            if csv_text == "all":
                return list(valid_ids)
            requested = [item.strip() for item in csv_text.split(",") if item.strip()]
            unknown = [item for item in requested if item not in valid_ids]
            if unknown:
                raise SystemExit("Unknown IDs: " + ",".join(unknown))
            return requested


        def main():
            args = build_parser().parse_args()
            bundle = load_bundle()
            inputs = input_map(bundle)
            manifest_map = model_manifest_map(bundle)
            all_partition_ids = [row["partition_id"] for row in bundle["partitions"] if parse_bool(row.get("enabled"), True)]
            all_model_ids = [row["model_id"] for row in bundle["models"] if parse_bool(row.get("enabled"), True)]
            partition_ids = resolve_csv(args.partitions, all_partition_ids)
            model_ids = resolve_csv(args.models, all_model_ids)
            out_root = Path(args.out_root).expanduser().resolve()
            run_script = library_root() / "src" / "run_{library_slug}_model.py"

            for partition in bundle["partitions"]:
                if partition["partition_id"] not in partition_ids:
                    continue
                input_row = inputs[partition["input_id"]]
                for model in bundle["models"]:
                    if model["model_id"] not in model_ids:
                        continue
                    model_manifest = manifest_map[model["model_id"]]
                    cmd = [
                        str(Path(args.python_bin).resolve()),
                        str(run_script),
                        "--dig_dir", str(Path(args.dig_dir).expanduser().resolve()),
                        "--out_root", str(out_root),
                        "--partition_id", partition["partition_id"],
                        "--model_id", model["model_id"],
                    ]
                    if args.overwrite:
                        cmd.append("--overwrite")
                    subprocess.run(cmd, check=True)
            return 0


        if __name__ == "__main__":
            raise SystemExit(main())
        """
    )


def build_generated_run_model_script(library_name: str, library_slug: str) -> str:
    return textwrap.dedent(
        f"""\
        #!/usr/bin/env python3
        from __future__ import annotations

        import argparse
        import json
        import os
        import shutil
        from pathlib import Path

        from generated_library_runtime import (
            ARCHETYPE,
            ARCHETYPE_SPEC,
            backup_if_missing,
            build_converter_command,
            build_model_payload,
            build_replacements,
            config_dir,
            description_template_map,
            find_artifacts,
            input_map,
            library_root,
            load_bundle,
            model_manifest_map,
            parse_bool,
            patch_gmt,
            patch_meta,
            patch_provenance,
            prepare_workflow_input,
            render_template,
            resolve_input_path,
            run_command,
            write_model_json,
            write_json,
        )


        def build_parser():
            parser = argparse.ArgumentParser()
            parser.add_argument("--dig_dir", required=True)
            parser.add_argument("--out_root", required=True)
            parser.add_argument("--partition_id", required=True)
            parser.add_argument("--model_id", required=True)
            parser.add_argument("--python_bin", default=os.environ.get("PYTHON_BIN") or "python3")
            parser.add_argument("--overwrite", action="store_true")
            return parser


        def main():
            args = build_parser().parse_args()
            bundle = load_bundle()
            inputs = input_map(bundle)
            model_manifest = model_manifest_map(bundle)
            templates = description_template_map(bundle)
            library_config = bundle["library_config"]
            workflow_manifest = bundle["workflow_manifest"]
            out_root = Path(args.out_root).expanduser().resolve()
            partition = next((row for row in bundle["partitions"] if row["partition_id"] == args.partition_id), None)
            if partition is None:
                raise SystemExit(f"Unknown partition_id: {{args.partition_id}}")
            model = next((row for row in bundle["models"] if row["model_id"] == args.model_id), None)
            if model is None:
                raise SystemExit(f"Unknown model_id: {{args.model_id}}")
            input_row = inputs[partition["input_id"]]
            input_path = resolve_input_path(input_row)
            options = json.loads(model_manifest[args.model_id]["options_json"]) if str(model_manifest[args.model_id].get("options_json", "")).strip() else {{}}

            model_root = out_root / "genesets" / partition["partition_id"] / "models" / model["model_id"]
            workflow_dir = model_root / "workflow"
            extractor_dir = model_root / "extractor"
            if model_root.exists():
                if not args.overwrite:
                    raise SystemExit(f"Output already exists: {{model_root}}\\nRe-run with --overwrite to replace it.")
                shutil.rmtree(model_root)
            workflow_dir.mkdir(parents=True, exist_ok=True)
            extractor_dir.mkdir(parents=True, exist_ok=True)

            dig_dir = Path(args.dig_dir).expanduser().resolve()
            env = os.environ.copy()
            env["PYTHONPATH"] = str(dig_dir / "src")
            log_path = model_root / "run.log"
            converter_input_path = prepare_workflow_input(
                workflow_archetype=str(workflow_manifest.get("workflow_archetype", library_config.get("workflow_archetype", "simple_converter"))),
                input_path=input_path,
                workflow_dir=workflow_dir,
                model=model,
                options=options,
                partition=partition,
            )
            command = build_converter_command(
                python_bin=Path(args.python_bin).expanduser().resolve(),
                dig_dir=dig_dir,
                archetype=ARCHETYPE,
                options=options,
                input_path=converter_input_path,
                out_dir=extractor_dir,
                library_config=library_config,
                partition=partition,
                model=model,
            )
            run_command(command, cwd=dig_dir, env=env, log_path=log_path)

            commands_md = model_root / "commands.md"
            commands_md.write_text("$ " + " ".join(command) + "\\n", encoding="utf-8")

            model_payload = build_model_payload(
                library_config=library_config,
                partition=partition,
                model=model,
                options=options,
                input_row=input_row,
            )
            write_model_json(extractor_dir / "geneset.model.json", model_payload)

            description_template = templates.get(args.model_id, ARCHETYPE_SPEC["description_template"])
            model_description = render_template(
                description_template,
                {{
                    "library_name": library_config["library_name"],
                    "library_slug": library_config["library_slug"],
                    "partition_id": partition["partition_id"],
                    "partition_label": partition["partition_label"],
                    "model_id": model["model_id"],
                    "model_label": model["model_label"],
                    "organism": library_config["organism"],
                    "genome_build": library_config["genome_build"],
                }},
            )
            replacements = build_replacements(
                out_root=out_root,
                output_mirror_uri=str(library_config.get("output_mirror_uri", f"submission://{{library_config['library_slug']}}_all_models")),
                input_rows=bundle["inputs"],
            )

            gmt_path, meta_path, prov_path = find_artifacts(extractor_dir)
            patch_gmt(gmt_path, model_description)
            if meta_path is not None:
                patch_meta(meta_path, model_payload=model_payload, model_description=model_description, replacements=replacements)
            if prov_path is not None:
                patch_provenance(prov_path, model_description=model_description, replacements=replacements)
            manifest_path = model_root / "output_manifest.json"
            write_json(
                manifest_path,
                {{
                    "library_name": library_config["library_name"],
                    "archetype": ARCHETYPE,
                    "partition_id": partition["partition_id"],
                    "model_id": model["model_id"],
                    "input_path": str(input_path),
                    "converter_input_path": str(converter_input_path),
                    "command": command,
                }},
            )
            return 0


        if __name__ == "__main__":
            raise SystemExit(main())
        """
    )


def build_generated_validate_script(library_name: str, library_slug: str) -> str:
    return textwrap.dedent(
        f"""\
        #!/usr/bin/env python3
        from __future__ import annotations

        import argparse
        import json
        from pathlib import Path


        def build_parser():
            parser = argparse.ArgumentParser()
            parser.add_argument("--out_root", required=True)
            return parser


        def main():
            args = build_parser().parse_args()
            out_root = Path(args.out_root).expanduser().resolve()
            errors = []
            warnings = []
            gmt_files = sorted(out_root.rglob("genesets.gmt"))
            meta_files = sorted(out_root.rglob("geneset.meta.json"))
            prov_files = sorted(out_root.rglob("geneset.provenance.json"))
            model_files = sorted(out_root.rglob("geneset.model.json"))
            if not gmt_files:
                errors.append("No genesets.gmt files found")
            if not meta_files:
                errors.append("No geneset.meta.json files found")
            if not prov_files:
                errors.append("No geneset.provenance.json files found")
            if not model_files:
                errors.append("No geneset.model.json files found")
            for path in meta_files + prov_files:
                text = path.read_text(encoding="utf-8", errors="ignore")
                if "/home/" in text or "/Users/" in text or "/humgen/" in text:
                    errors.append(f"Local path leak detected in {{path}}")
            for path in gmt_files:
                with path.open("r", encoding="utf-8") as handle:
                    for line_no, line in enumerate(handle, 1):
                        parts = line.rstrip("\\n").split("\\t")
                        if len(parts) >= 2 and not parts[1].strip():
                            errors.append(f"Empty GMT description in {{path}} line {{line_no}}")
            payload = {{
                "out_root": str(out_root),
                "n_gmt_files": len(gmt_files),
                "n_meta_files": len(meta_files),
                "n_provenance_files": len(prov_files),
                "n_model_files": len(model_files),
                "warnings": warnings,
                "errors": errors,
            }}
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 1 if errors else 0


        if __name__ == "__main__":
            raise SystemExit(main())
        """
    )


def scaffold(args: argparse.Namespace) -> int:
    bundle_root = load_bundle_source(args.bundle_dir, args.bundle_zip)
    errors, warnings, context = validate_bundle_dir(bundle_root)
    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    assert context is not None
    out_dir = Path(args.extractor_root).expanduser().resolve() / (args.library_name or context["library_manifest"]["library_name"])
    write_scaffold_files(out_dir, context, runnable=False)
    print(f"Wrote scaffold: {out_dir}")
    return 0


def generate_package(args: argparse.Namespace) -> int:
    bundle_root = load_bundle_source(args.bundle_dir, args.bundle_zip)
    errors, warnings, context = validate_bundle_dir(bundle_root)
    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    assert context is not None
    archetype = infer_extractor_archetype(context["library_manifest"])
    if archetype not in ARCHETYPES:
        raise SystemExit(
            "This bundle is not template-compatible for one-shot package generation.\n"
            "Set library_manifest.json extractor_archetype (or legacy archetype) to one of: " + ", ".join(sorted(ARCHETYPES))
        )
    out_dir = Path(args.out_dir).expanduser().resolve()
    if out_dir.exists() and any(out_dir.iterdir()) and not args.force:
        raise SystemExit(f"Package output directory already exists and is not empty: {out_dir}\nRe-run with --force to reuse it.")
    ensure_dir(out_dir)
    write_scaffold_files(out_dir, context, runnable=True)
    print(f"Wrote runnable generated package: {out_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bundle-driven onboarding and template-compatible package generator for geneset-extractor-dev.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_list = subparsers.add_parser("list-archetypes", help="List supported template-compatible archetypes.")
    parser_list.set_defaults(func=list_archetypes)

    parser_list_workflow = subparsers.add_parser("list-workflow-archetypes", help="List supported workflow archetypes.")
    parser_list_workflow.set_defaults(func=list_workflow_archetypes)

    parser_list_env = subparsers.add_parser("list-environment-profiles", help="List supported environment profiles.")
    parser_list_env.set_defaults(func=list_environment_profiles)

    parser_init = subparsers.add_parser("init", help="Initialize a new onboarding bundle.")
    parser_init.add_argument("--library_name", required=True)
    parser_init.add_argument("--out_dir", required=True)
    parser_init.add_argument("--archetype", choices=sorted(ARCHETYPES), default="")
    parser_init.add_argument("--workflow_archetype", choices=sorted(WORKFLOW_ARCHETYPES), default="")
    parser_init.add_argument("--environment_profile", choices=sorted(ENVIRONMENT_PROFILES), default="")
    parser_init.add_argument("--force", action="store_true")
    parser_init.set_defaults(func=init_bundle)

    parser_questionnaire = subparsers.add_parser("questionnaire", help="Update questionnaire.json fields.")
    parser_questionnaire.add_argument("--bundle_dir", required=True)
    parser_questionnaire.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    parser_questionnaire.set_defaults(func=questionnaire)

    parser_input = subparsers.add_parser("add-input", help="Append a row to inputs_manifest.tsv.")
    parser_input.add_argument("--bundle_dir", required=True)
    parser_input.add_argument("--input_id", required=True)
    parser_input.add_argument("--path_or_uri", required=True)
    parser_input.add_argument("--input_role", required=True)
    parser_input.add_argument("--workflow_stage", default="workflow_input")
    parser_input.add_argument("--format", required=True)
    parser_input.add_argument("--is_external_input", default="true")
    parser_input.add_argument("--required_for_rerun", default="true")
    parser_input.add_argument("--source_url_or_uri", default="")
    parser_input.add_argument("--partition_scope", default="")
    parser_input.add_argument("--notes", default="")
    parser_input.set_defaults(func=add_input)

    parser_partition = subparsers.add_parser("add-partition", help="Append a row to partition_plan.tsv.")
    parser_partition.add_argument("--bundle_dir", required=True)
    parser_partition.add_argument("--partition_id", required=True)
    parser_partition.add_argument("--partition_label", required=True)
    parser_partition.add_argument("--partition_type", required=True)
    parser_partition.add_argument("--partition_group", default="")
    parser_partition.add_argument("--input_id", required=True)
    parser_partition.add_argument("--enabled", default="true")
    parser_partition.add_argument("--notes", default="")
    parser_partition.set_defaults(func=add_partition)

    parser_model = subparsers.add_parser("add-model", help="Append a row to model_plan.tsv.")
    parser_model.add_argument("--bundle_dir", required=True)
    parser_model.add_argument("--model_id", required=True)
    parser_model.add_argument("--model_family", required=True)
    parser_model.add_argument("--model_label", required=True)
    parser_model.add_argument("--input_mode", required=True)
    parser_model.add_argument("--workflow_variant", default="")
    parser_model.add_argument("--extractor_archetype", default="")
    parser_model.add_argument("--signed_output", required=True)
    parser_model.add_argument("--gene_set_pattern", required=True)
    parser_model.add_argument("--comparison_style", default="")
    parser_model.add_argument("--distinct_algorithmic_feature", required=True)
    parser_model.add_argument("--description", required=True)
    parser_model.add_argument("--options_json", default="{}")
    parser_model.add_argument("--enabled", default="true")
    parser_model.set_defaults(func=add_model)

    parser_validate = subparsers.add_parser("validate", help="Validate a bundle directory.")
    parser_validate.add_argument("--bundle_dir", required=True)
    parser_validate.set_defaults(func=validate)

    parser_package = subparsers.add_parser("package", help="Zip a validated bundle directory.")
    parser_package.add_argument("--bundle_dir", required=True)
    parser_package.add_argument("--out_zip", required=True)
    parser_package.set_defaults(func=package_bundle)

    parser_inspect = subparsers.add_parser("inspect", help="Inspect a bundle directory or bundle zip.")
    parser_inspect.add_argument("--bundle_dir")
    parser_inspect.add_argument("--bundle_zip")
    parser_inspect.set_defaults(func=inspect_bundle)

    parser_validate_zip = subparsers.add_parser("validate-bundle", help="Validate a bundle zip.")
    parser_validate_zip.add_argument("--bundle_zip", required=True)
    parser_validate_zip.set_defaults(func=validate_bundle_zip)

    parser_scaffold = subparsers.add_parser("scaffold", help="Generate a maintainer-side scaffold from a bundle.")
    parser_scaffold.add_argument("--bundle_dir")
    parser_scaffold.add_argument("--bundle_zip")
    parser_scaffold.add_argument("--extractor_root", required=True)
    parser_scaffold.add_argument("--library_name")
    parser_scaffold.set_defaults(func=scaffold)

    parser_generate = subparsers.add_parser("generate-package", help="Generate a runnable package from a template-compatible bundle.")
    parser_generate.add_argument("--bundle_dir")
    parser_generate.add_argument("--bundle_zip")
    parser_generate.add_argument("--out_dir", required=True)
    parser_generate.add_argument("--force", action="store_true")
    parser_generate.set_defaults(func=generate_package)

    return parser


def list_archetypes(args: argparse.Namespace) -> int:
    print(json.dumps(ARCHETYPES, indent=2, sort_keys=True))
    return 0


def list_workflow_archetypes(args: argparse.Namespace) -> int:
    print(json.dumps(WORKFLOW_ARCHETYPES, indent=2, sort_keys=True))
    return 0


def list_environment_profiles(args: argparse.Namespace) -> int:
    print(json.dumps(ENVIRONMENT_PROFILES, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
