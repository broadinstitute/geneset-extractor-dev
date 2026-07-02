#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import importlib
import json
import os
import re
import shlex
import subprocess
import sys
import shutil
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

DIRECTORY_ARG_PLACEHOLDERS = {
    "--raw_asctb_dir": "/path/to/raw_asctb_dir",
    "--asctb_dir": "/path/to/asctb_dir",
    "--raw_counts_dir": "/path/to/raw_counts_dir",
    "--dea_dir": "/path/to/dea_dir",
}

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEV_REPO_ROOT = WORKSPACE_ROOT / "geneset-extractor-dev"
KNOWN_LIBRARIES = ("GTEx", "MoTrPAC", "HuBMAP", "LINCS_L1000")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Patch geneset metadata descriptions for one model output directory "
            "and rewrite provenance for every affected geneset."
        )
    )
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--model_dir", required=True)
    parser.add_argument("--description_template_tsv")
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument("--dig_dir", required=True)
    parser.add_argument("--provenance_mirror_local_prefix")
    parser.add_argument("--provenance_mirror_remote_prefix")
    parser.add_argument("--local_input_source_map_tsv")
    parser.add_argument("--show_template_vars", action="store_true")
    return parser.parse_args()


def shell_join(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def read_template_map(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = set(reader.fieldnames or [])
        if "model_id" not in fieldnames or "description_template" not in fieldnames:
            raise SystemExit(
                "description template TSV must include columns: model_id, description_template"
            )
        mapping: dict[str, str] = {}
        for row in reader:
            model_id = str(row.get("model_id", "")).strip()
            template = str(row.get("description_template", "")).strip()
            if model_id:
                mapping[model_id] = template
    if not mapping:
        raise SystemExit(f"No model templates found in {path}")
    return mapping


def read_input_source_map(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = set(reader.fieldnames or [])
        if "local_path" not in fieldnames or "source_uri" not in fieldnames:
            raise SystemExit("source map TSV must include columns: local_path, source_uri")
        mapping: dict[str, str] = {}
        for row in reader:
            local_path = str(row.get("local_path", "")).strip()
            source_uri = str(row.get("source_uri", "")).strip()
            if not local_path and not source_uri:
                continue
            if not local_path or not source_uri:
                raise SystemExit("source map TSV rows must provide both local_path and source_uri")
            if local_path in mapping:
                if mapping[local_path] != source_uri:
                    raise SystemExit(
                        f"Conflicting source_uri values for duplicate local_path in source map TSV: {local_path}"
                    )
                continue
            mapping[local_path] = source_uri
    if not mapping:
        raise SystemExit(f"No source map rows found in {path}")
    return dict(sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True))


def parse_gmt_rows(path: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for line in handle:
            rows.append(line.rstrip("\n").split("\t"))
    return rows


def write_gmt_rows(path: Path, rows: list[list[str]]) -> None:
    path.write_text(
        "\n".join("\t".join(row) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
        newline="\n",
    )


def split_gmt_set_name(set_name: str) -> tuple[str, str | None]:
    lower_name = set_name.lower()
    for suffix, direction in (("_up", "up"), ("_dn", "dn"), ("_down", "dn")):
        if lower_name.endswith(suffix):
            return set_name[: -len(suffix)], direction
    return set_name, None


def strip_trailing_period(text: str) -> str:
    return str(text).strip().rstrip(".")


def replace_header_gene_set_kind(header: str, direction: str | None) -> str:
    if not direction:
        return header
    label = "up-gene set" if direction == "up" else "down-gene set"
    for needle in (" gene-set library ", " gene set ", " gene-set library", " gene set"):
        if needle in header:
            return header.replace(needle, f" {label} ", 1).rstrip()
    return f"{header} {label}".strip()


def model_lookup_context(model_payload: dict[str, object], set_name: str) -> dict[str, object]:
    naming = model_payload.get("naming", {}) if isinstance(model_payload.get("naming"), dict) else {}
    inputs = model_payload.get("inputs", {}) if isinstance(model_payload.get("inputs"), dict) else {}
    stem, direction = split_gmt_set_name(set_name)
    context: dict[str, object] = {
        "model": model_payload,
        "set_name": set_name,
        "set_stem": stem,
        "direction": direction or "",
    }
    for key, value in naming.items():
        context.setdefault(str(key), value)
    for key, value in inputs.items():
        context.setdefault(str(key), value)
    if not context.get("comparison_label"):
        library = str(model_payload.get("library", "")).strip()
        model_group = str(model_payload.get("model_group", "")).strip()
        if library == "MoTrPAC":
            if stem.startswith("MoTrPAC_"):
                comparison_label = stem[len("MoTrPAC_") :]
            else:
                comparison_label = stem
            if model_group == "TR" and comparison_label.endswith("_TrainingVsControl"):
                comparison_label = comparison_label[: -len("_TrainingVsControl")] + " training-versus-control"
            context["comparison_label"] = comparison_label.replace("_", " ")
    return context


TEMPLATE_VAR_PATTERN = re.compile(r"\{([^{}]+)\}")


def resolve_template_value(context: dict[str, object], path: str) -> str:
    current: object = context
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return ""
    if current is None:
        return ""
    return str(current)


def expand_description_template(template: str, model_payload: dict[str, object], set_name: str) -> str:
    context = model_lookup_context(model_payload, set_name)
    return TEMPLATE_VAR_PATTERN.sub(lambda match: resolve_template_value(context, match.group(1).strip()), template)


def split_description(description: str) -> tuple[str, str]:
    text = str(description).strip()
    if ": " in text:
        head, tail = text.split(": ", 1)
        return head.strip(), strip_trailing_period(tail)
    return strip_trailing_period(text), ""


def extract_term_after_prefix(stem: str, prefix: str) -> str:
    if stem.startswith(prefix):
        return stem[len(prefix) :]
    return stem


def gtex_row_description(model_payload: dict[str, object], base_description: str, direction: str, stem: str) -> str:
    header, body = split_description(base_description)
    header = replace_header_gene_set_kind(header, direction)
    naming = model_payload.get("naming", {}) if isinstance(model_payload.get("naming"), dict) else {}
    comparison_style = str(naming.get("comparison_style", "")).strip()
    if comparison_style == "age_pair":
        comparison_age = str(naming.get("comparison_age_label", "")).strip()
        reference_age = str(naming.get("reference_age_label", "")).strip()
        higher_lower = "higher" if direction == "up" else "lower"
        match = re.match(
            r"(?P<method>.+?) in (?P<comparison>.+?) relative to (?P<reference>.+?),(?P<rest>.*)$",
            body,
        )
        if match:
            method = strip_trailing_period(match.group("method"))
            rest = strip_trailing_period(match.group("rest"))
            clause = f"genes with {higher_lower} expression in {comparison_age} relative to {reference_age}, identified by {method}"
            if rest:
                clause += f", {rest}"
            return f"{header}: {clause}."
        return f"{header}: genes with {higher_lower} expression in {comparison_age} relative to {reference_age}, identified by {body}."
    association = "positive" if direction == "up" else "negative"
    return f"{header}: genes with {association} association with increasing age, identified by {body}."


def motrpac_tw_condition_phrase(stem: str) -> str:
    label = extract_term_after_prefix(stem, "MoTrPAC_")
    parts = [part for part in label.split("_") if part]
    if len(parts) >= 3 and parts[-2].lower() in {"female", "male"}:
        return f"at {parts[-1]} in {parts[-2].lower()} trained animals relative to matched controls"
    if len(parts) >= 2:
        return f"at {parts[-1]} in trained animals relative to matched controls"
    return f"for {label.replace('_', ' ')} relative to matched controls"


def normalize_library_body(body: str) -> str:
    stripped = strip_trailing_period(body)
    lowered = stripped.lower()
    if lowered.startswith("library built "):
        return stripped[len("library ") :]
    return stripped


def motrpac_row_description(model_payload: dict[str, object], base_description: str, direction: str, stem: str) -> str:
    header, body = split_description(base_description)
    model_group = str(model_payload.get("model_group", "")).strip()
    if model_group in {"TR", "TW"}:
        header = replace_header_gene_set_kind(header, direction)
        higher_lower = "higher" if direction == "up" else "lower"
        if model_group == "TR":
            clause = f"genes with {higher_lower} expression in trained animals relative to controls, identified by {body}"
        else:
            clause = f"genes with {higher_lower} expression {motrpac_tw_condition_phrase(stem)}, identified by {body}"
        return f"{header}: {clause}."
    label = extract_term_after_prefix(stem, "MoTrPAC_").replace("_", " ")
    polarity = "positive" if direction == "up" else "negative"
    model_id = str(model_payload.get("model_id", "")).strip()
    normalized = normalize_library_body(body)
    return (
        f"MoTrPAC rat endurance-training aggregated {'up-gene set' if direction == 'up' else 'down-gene set'} "
        f"for {label} using model {model_id}: genes with {polarity} aggregated training-response signal for {label}, "
        f"derived from {normalized}."
    )


def lincs_row_description(model_payload: dict[str, object], base_description: str, direction: str, stem: str) -> str:
    _header, body = split_description(base_description)
    model_id = str(model_payload.get("model_id", "")).strip()
    term_prefix = ""
    parameters = model_payload.get("parameters", {}) if isinstance(model_payload.get("parameters"), dict) else {}
    term_prefix = str(parameters.get("term_prefix", "")).strip()
    term = extract_term_after_prefix(stem, f"{term_prefix}_").replace("_", " ")
    if model_id == "HZ1":
        return (
            f"LINCS L1000 chemical perturbation {'up-gene set' if direction == 'up' else 'down-gene set'} "
            f"for {term} using model {model_id}: genes {'increased' if direction == 'up' else 'decreased'} "
            f"after chemical perturbation by {term}, derived from {normalize_library_body(body)}."
        )
    return (
        f"LINCS L1000 CRISPR knockout {'up-gene set' if direction == 'up' else 'down-gene set'} "
        f"for {term} using model {model_id}: genes {'increased' if direction == 'up' else 'decreased'} "
        f"after CRISPR knockout of {term}, derived from {normalize_library_body(body)}."
    )


def hubmap_row_description(model_payload: dict[str, object], base_description: str, stem: str) -> str:
    _header, body = split_description(base_description)
    model_id = str(model_payload.get("model_id", "")).strip()
    term = extract_term_after_prefix(stem, "HuBMAP_").replace("_", " ")
    return (
        f"HuBMAP ASCT+B marker gene set for {term} using model {model_id}: "
        f"marker genes for {term}, derived from {normalize_library_body(body)}."
    )


def render_gmt_row_description(set_name: str, model_payload: dict[str, object], template: str) -> str:
    stem, direction = split_gmt_set_name(set_name)
    base_description = expand_description_template(template, model_payload, set_name)
    library = str(model_payload.get("library", "")).strip()
    if library == "GTEx" and direction:
        return gtex_row_description(model_payload, base_description, direction, stem)
    if library == "MoTrPAC" and direction:
        return motrpac_row_description(model_payload, base_description, direction, stem)
    if library == "LINCS_L1000" and direction:
        return lincs_row_description(model_payload, base_description, direction, stem)
    if library == "HuBMAP":
        return hubmap_row_description(model_payload, base_description, stem)
    return base_description


def discover_gmt_paths(model_dir: Path) -> list[Path]:
    return sorted((model_dir / "extractor").rglob("genesets.gmt"))


def rewrite_gmt_descriptions(
    *,
    model_dir: Path,
    template_map: dict[str, str],
) -> None:
    gmt_paths = discover_gmt_paths(model_dir)
    if not gmt_paths:
        return
    set_name_to_payload: dict[str, dict[str, object]] = {}
    for gmt_path in sorted(gmt_paths, key=lambda path: len(path.parts), reverse=True):
        sidecar_path = gmt_path.with_name("geneset.model.json")
        if not sidecar_path.exists():
            continue
        model_payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
        if not isinstance(model_payload, dict):
            continue
        for row in parse_gmt_rows(gmt_path):
            if row and row[0] and row[0] not in set_name_to_payload:
                set_name_to_payload[row[0]] = model_payload

    for gmt_path in gmt_paths:
        sidecar_path = gmt_path.with_name("geneset.model.json")
        fallback_payload: dict[str, object] | None = None
        if sidecar_path.exists():
            payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                fallback_payload = payload
        rows = parse_gmt_rows(gmt_path)
        changed = False
        for row in rows:
            if len(row) < 3 or not row[0]:
                continue
            model_payload = set_name_to_payload.get(row[0], fallback_payload)
            if not model_payload:
                continue
            model_id = str(model_payload.get("model_id", "")).strip()
            template = template_map.get(model_id, "")
            if not template:
                continue
            while len(row) < 3:
                row.append("")
            description = render_gmt_row_description(row[0], model_payload, template)
            if row[1] != description:
                row[1] = description
                changed = True
        if changed:
            write_gmt_rows(gmt_path, rows)


def read_manifest_meta_paths(manifest_path: Path, extractor_dir: Path) -> list[Path]:
    meta_paths: list[Path] = []
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            rel_path = str(row.get("meta_path", "")).strip()
            if rel_path:
                meta_paths.append((extractor_dir / rel_path).resolve())
    return meta_paths


def discover_metadata_paths(model_dir: Path) -> list[Path]:
    extractor_dir = model_dir / "extractor"
    if not extractor_dir.exists() or not extractor_dir.is_dir():
        raise SystemExit(f"Missing extractor directory: {extractor_dir}")
    manifest_path = extractor_dir / "manifest.tsv"
    if manifest_path.exists():
        meta_paths = read_manifest_meta_paths(manifest_path, extractor_dir)
    else:
        single_meta = extractor_dir / "geneset.meta.json"
        meta_paths = [single_meta] if single_meta.exists() else []
    deduped: list[Path] = []
    seen: set[Path] = set()
    for meta_path in meta_paths:
        if meta_path not in seen:
            deduped.append(meta_path)
            seen.add(meta_path)
    if not deduped:
        raise SystemExit(f"No geneset.meta.json files found under {extractor_dir}")
    for meta_path in deduped:
        if not meta_path.exists():
            raise SystemExit(f"Missing metadata file listed for refresh: {meta_path}")
    return deduped


def ensure_model_sidecar(metadata_path: Path, model_id: str) -> None:
    sidecar_path = metadata_path.with_name("geneset.model.json")
    if sidecar_path.exists():
        return
    sidecar_path.write_text(
        json.dumps({"model_id": model_id}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_orig_once(path: Path) -> None:
    if not path.exists() or not path.is_file():
        return
    orig_path = Path(f"{path}.orig")
    if orig_path.exists():
        return
    shutil.copy2(path, orig_path)


def snapshot_originals(metadata_paths: list[Path]) -> None:
    for metadata_path in metadata_paths:
        write_orig_once(metadata_path)
        write_orig_once(metadata_path.with_name("geneset.provenance.json"))


def restore_from_originals(metadata_paths: list[Path]) -> None:
    for metadata_path in metadata_paths:
        for path in (metadata_path, metadata_path.with_name("geneset.provenance.json")):
            orig_path = Path(f"{path}.orig")
            if orig_path.exists():
                shutil.copy2(orig_path, path)


def snapshot_gmt_originals(model_dir: Path) -> None:
    for gmt_path in discover_gmt_paths(model_dir):
        write_orig_once(gmt_path)


def restore_gmt_from_originals(model_dir: Path) -> None:
    for gmt_path in discover_gmt_paths(model_dir):
        orig_path = Path(f"{gmt_path}.orig")
        if orig_path.exists():
            shutil.copy2(orig_path, gmt_path)


def run_command(cmd: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    print("$ " + shell_join(cmd), flush=True)
    subprocess.run(cmd, cwd=str(cwd), env=env, check=True)


@contextmanager
def prepend_sys_path(path: Path):
    path_text = str(path)
    sys.path.insert(0, path_text)
    try:
        yield
    finally:
        try:
            sys.path.remove(path_text)
        except ValueError:
            pass


def read_tsv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def resolve_tsv_value(path: Path, *, key_field: str, key_value: str, value_field: str) -> str:
    for row in read_tsv_rows(path):
        if str(row.get(key_field, "")).strip() == key_value:
            return str(row.get(value_field, "")).strip()
    return ""


def infer_library_name(
    *,
    description_template_tsv: str | None,
    metadata_paths: list[Path],
) -> str:
    if description_template_tsv:
        template_path = Path(description_template_tsv).resolve()
        for part in template_path.parts:
            if part in KNOWN_LIBRARIES:
                return part
    for metadata_path in metadata_paths:
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        gene_set = payload.get("gene_set", {})
        if isinstance(gene_set, dict):
            name = str(gene_set.get("name", "")).strip()
            if name.startswith("GTEx_"):
                return "GTEx"
            if name.startswith("MoTrPAC_"):
                return "MoTrPAC"
            if name.startswith("HuBMAP_"):
                return "HuBMAP"
            if name.startswith("LINCS_L1000_"):
                return "LINCS_L1000"
    raise SystemExit("Unable to infer library for model refresh. Provide --description_template_tsv from a library config.")


def gtex_model_group(model_id: str) -> str:
    if str(model_id).startswith("AB"):
        return "AB"
    if str(model_id).startswith("AC"):
        return "AC"
    if str(model_id).startswith("HZ"):
        return "HZ"
    raise SystemExit(f"Unsupported GTEx model_id for standalone refresh: {model_id}")


def regenerate_gtex_model_sidecars(args: argparse.Namespace, model_dir: Path, env: dict[str, str]) -> None:
    tissue_id = model_dir.parent.parent.name
    models_root = model_dir.parent
    tissue_list_tsv = DEV_REPO_ROOT / "GTEx" / "config" / "broad_tissue_list.tsv"
    tissue_label = (
        resolve_tsv_value(tissue_list_tsv, key_field="tissue_id", key_value=tissue_id, value_field="tissue_name")
        or resolve_tsv_value(tissue_list_tsv, key_field="tissue_id", key_value=tissue_id, value_field="tissue_label")
    )
    if not tissue_label:
        raise SystemExit(f"Unable to resolve GTEx tissue label for tissue_id={tissue_id}")
    group = gtex_model_group(args.model_id)
    if group == "AB":
        cmd = [
            str(Path(args.python_bin).resolve()),
            str(DEV_REPO_ROOT / "GTEx" / "src" / "run_age_binned_model.py"),
            "--model_id",
            args.model_id,
            "--tissue_id",
            tissue_id,
            "--tissue_label",
            tissue_label,
            "--run_root",
            str(models_root),
            "--python_bin",
            str(Path(args.python_bin).resolve()),
            "--dig_dir",
            str(Path(args.dig_dir).resolve()),
            "--age_binned_model_manifest",
            str(DEV_REPO_ROOT / "GTEx" / "config" / "age_binned_model_manifest.tsv"),
            "--tissue_column",
            "SMTS",
            "--tissue_value",
            tissue_label,
            "--write_model_only",
        ]
    elif group == "AC":
        cmd = [
            str(Path(args.python_bin).resolve()),
            str(DEV_REPO_ROOT / "GTEx" / "src" / "run_continuous_age_model.py"),
            "--tissue_id",
            tissue_id,
            "--tissue_label",
            tissue_label,
            "--model_ids",
            args.model_id,
            "--run_root",
            str(models_root),
            "--python_bin",
            str(Path(args.python_bin).resolve()),
            "--rscript_bin",
            os.environ.get("RSCRIPT_BIN", "Rscript"),
            "--dig_dir",
            str(Path(args.dig_dir).resolve()),
            "--continuous_age_model_manifest",
            str(DEV_REPO_ROOT / "GTEx" / "config" / "continuous_age_model_manifest.tsv"),
            "--tissue_column",
            "SMTS",
            "--tissue_value",
            tissue_label,
            "--write_model_only",
        ]
    else:
        cmd = [
            str(Path(args.python_bin).resolve()),
            str(DEV_REPO_ROOT / "GTEx" / "src" / "run_hz_notebook_model.py"),
            "--model_id",
            args.model_id,
            "--tissue_id",
            tissue_id,
            "--tissue_label",
            tissue_label,
            "--run_root",
            str(models_root),
            "--python_bin",
            str(Path(args.python_bin).resolve()),
            "--rscript_bin",
            os.environ.get("RSCRIPT_BIN", "Rscript"),
            "--dig_dir",
            str(Path(args.dig_dir).resolve()),
            "--tissue_column",
            "SMTS",
            "--tissue_value",
            tissue_label,
            "--write_model_only",
        ]
    run_command(cmd, cwd=WORKSPACE_ROOT, env=env)


def regenerate_motrpac_model_sidecars(args: argparse.Namespace, model_dir: Path, env: dict[str, str]) -> None:
    model_list_tsv = DEV_REPO_ROOT / "MoTrPAC" / "config" / "model_list.tsv"
    model_family = resolve_tsv_value(model_list_tsv, key_field="model_id", key_value=args.model_id, value_field="model_family")
    if not model_family:
        raise SystemExit(f"Unable to resolve MoTrPAC model family for model_id={args.model_id}")
    if model_family in {"training", "timewise"}:
        tissue_id = model_dir.parent.parent.name
        tissue_list_tsv = DEV_REPO_ROOT / "MoTrPAC" / "config" / "tissue_list.tsv"
        tissue_label = resolve_tsv_value(tissue_list_tsv, key_field="tissue_id", key_value=tissue_id, value_field="tissue_label")
        transcript_tissue_label = resolve_tsv_value(tissue_list_tsv, key_field="tissue_id", key_value=tissue_id, value_field="transcript_tissue_label")
        if not tissue_label or not transcript_tissue_label:
            raise SystemExit(f"Unable to resolve MoTrPAC tissue labels for tissue_id={tissue_id}")
        model_manifest_tsv = DEV_REPO_ROOT / "MoTrPAC" / "config" / "model_manifest.tsv"
        extractor_dir = model_dir / "extractor"
        with prepend_sys_path(DEV_REPO_ROOT / "MoTrPAC" / "src"):
            if model_family == "training":
                module = importlib.import_module("run_motrpac_training_model")
                settings_by_model = module.load_model_settings(model_manifest_tsv)
                module.write_model_sidecar(
                    path=extractor_dir / "geneset.model.json",
                    model_id=args.model_id,
                    tissue_id=tissue_id,
                    tissue_label=tissue_label,
                    settings=settings_by_model[args.model_id],
                )
                return
            module = importlib.import_module("run_motrpac_timewise_model")
            settings_by_model = module.load_model_settings(model_manifest_tsv)
            settings = settings_by_model[args.model_id]
            if (extractor_dir / "manifest.tsv").exists():
                module.write_grouped_model_sidecars(
                    extractor_out=extractor_dir,
                    model_id=args.model_id,
                    tissue_id=tissue_id,
                    tissue_label=tissue_label,
                    settings=settings,
                )
            else:
                payload = {
                    "schema_version": "1",
                    "library": "MoTrPAC",
                    "model_id": args.model_id,
                    "model_group": "TW",
                    "model_label": "timewise",
                    "workflow_name": (
                        "motrpac_timepoint"
                        if module.manifest_value(settings, "workflow_stratify_scheme", "sex_timepoint") == "timepoint"
                        else "motrpac_timewise"
                    ),
                    "extractor_name": "rna_deg_multi",
                    "parameters": {
                        "stratify_scheme": module.manifest_value(settings, "workflow_stratify_scheme", "sex_timepoint"),
                        "covariates": module.manifest_value(settings, "workflow_covariates", "none"),
                        "min_samples_per_group": module.manifest_value(settings, "workflow_min_samples_per_group", "5"),
                        "postprocess_mode": settings["extractor_postprocess_mode"],
                        "score_mode": settings["extractor_score_mode"],
                        "select": settings["extractor_select"],
                    },
                    "inputs": {
                        "tissue_id": tissue_id,
                        "tissue_label": tissue_label or tissue_id,
                        "organism": "human",
                        "genome_build": "hg38",
                    },
                    "naming": {
                        "comparison_style": module.manifest_value(settings, "workflow_stratify_scheme", "sex_timepoint"),
                        "gene_set_pattern": "MoTrPAC_<tissue>_<sex_or_timepoint>_up|dn",
                    },
                }
                module.write_text(
                    extractor_dir / "geneset.model.json",
                    json.dumps(payload, indent=2, sort_keys=True) + "\n",
                )
        return

    with prepend_sys_path(DEV_REPO_ROOT / "MoTrPAC" / "src"):
        if model_family == "hz_released_dea":
            module = importlib.import_module("run_motrpac_hz_released_dea_model")
            settings_by_model = module.load_model_settings(DEV_REPO_ROOT / "MoTrPAC" / "config" / "model_manifest.tsv")
            module.write_model_sidecar(
                path=model_dir / "extractor" / "geneset.model.json",
                model_id=args.model_id,
                settings=settings_by_model[args.model_id],
            )
            return
        if model_family == "hz_raw_aggregated":
            module = importlib.import_module("run_motrpac_hz_raw_aggregated_model")
            settings_by_model = module.row_map(module.read_tsv(DEV_REPO_ROOT / "MoTrPAC" / "config" / "model_manifest.tsv"), "model_id")
            module.write_model_sidecar(
                path=model_dir / "extractor" / "geneset.model.json",
                model_id=args.model_id,
                settings=settings_by_model[args.model_id],
            )
            return
    raise SystemExit(f"Unsupported MoTrPAC model family for standalone refresh: {model_family}")


def regenerate_hubmap_model_sidecars(args: argparse.Namespace, model_dir: Path) -> None:
    with prepend_sys_path(DEV_REPO_ROOT / "HuBMAP" / "src"):
        module = importlib.import_module("run_hubmap_hz_model")
        settings_by_model = module.load_model_settings(DEV_REPO_ROOT / "HuBMAP" / "config" / "model_manifest.tsv")
        module.write_model_sidecar(
            path=model_dir / "extractor" / "geneset.model.json",
            model_id=args.model_id,
            settings=settings_by_model[args.model_id],
        )


def regenerate_lincs_model_sidecars(args: argparse.Namespace, model_dir: Path) -> None:
    with prepend_sys_path(DEV_REPO_ROOT / "LINCS_L1000" / "src"):
        module = importlib.import_module("run_lincs_l1000_hz_model")
        settings_by_model = module.load_model_settings(DEV_REPO_ROOT / "LINCS_L1000" / "config" / "model_manifest.tsv")
        workflow_name = module.model_workflow_info(args.model_id)[1]
        term_prefix = module.lincs_term_prefix(args.model_id)
        module.write_model_sidecar(
            path=model_dir / "extractor" / "geneset.model.json",
            model_id=args.model_id,
            settings=settings_by_model[args.model_id],
            workflow_name=workflow_name,
            term_prefix=term_prefix,
        )


def regenerate_model_sidecars(
    *,
    args: argparse.Namespace,
    model_dir: Path,
    metadata_paths: list[Path],
    env: dict[str, str],
) -> None:
    library_name = infer_library_name(
        description_template_tsv=args.description_template_tsv,
        metadata_paths=metadata_paths,
    )
    if library_name == "GTEx":
        regenerate_gtex_model_sidecars(args, model_dir, env)
        return
    if library_name == "MoTrPAC":
        regenerate_motrpac_model_sidecars(args, model_dir, env)
        return
    if library_name == "HuBMAP":
        regenerate_hubmap_model_sidecars(args, model_dir)
        return
    if library_name == "LINCS_L1000":
        regenerate_lincs_model_sidecars(args, model_dir)
        return
    raise SystemExit(f"Unsupported library for standalone model-sidecar regeneration: {library_name}")


def parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    parsed = urlparse(s3_uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise SystemExit(f"Expected S3 URI like s3://bucket/prefix, got: {s3_uri}")
    return parsed.netloc, parsed.path.lstrip("/")


def is_within_directory(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def extract_file_paths_from_provenance(provenance_path: Path) -> list[Path]:
    try:
        payload = json.loads(provenance_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Unable to parse provenance JSON {provenance_path}: {exc}") from exc

    all_input_paths: set[Path] = set()
    all_generated_paths: set[Path] = set()
    for graph in payload.values():
        if not isinstance(graph, dict):
            continue
        file_path_by_id: dict[str, Path] = {}
        for node in graph.get("nodes", []):
            if not isinstance(node, dict) or node.get("type") != "File":
                continue
            node_id = node.get("id")
            if not isinstance(node_id, str):
                continue
            c2m2_properties = node.get("c2m2_properties") or {}
            candidate = c2m2_properties.get("local_id") or node.get("dcc_url") or node.get("drc_url")
            if not isinstance(candidate, str) or not candidate.startswith("/"):
                continue
            file_path_by_id[node_id] = Path(candidate)

        input_paths: set[Path] = set()
        generated_paths: set[Path] = set()
        for edge in graph.get("edges", []):
            if not isinstance(edge, dict):
                continue
            source = edge.get("source")
            target = edge.get("target")
            label = edge.get("label")
            if (
                isinstance(source, str)
                and isinstance(target, str)
                and source.startswith("file:")
                and target.startswith("analysis:")
                and label in ("data input", "metadata input")
            ):
                source_path = file_path_by_id.get(source)
                if source_path is not None:
                    input_paths.add(source_path)
            if (
                isinstance(source, str)
                and isinstance(target, str)
                and source.startswith("analysis:")
                and target.startswith("file:")
            ):
                target_path = file_path_by_id.get(target)
                if target_path is not None:
                    generated_paths.add(target_path)

        all_input_paths.update(input_paths)
        all_generated_paths.update(generated_paths)

    return sorted(all_input_paths.difference(all_generated_paths))


def build_unique_input_relative_paths(paths: list[Path]) -> dict[Path, str]:
    unique_paths = sorted(set(paths))
    if not unique_paths:
        return {}

    suffix_lengths = {path: 1 for path in unique_paths}
    while True:
        by_suffix: dict[str, list[Path]] = {}
        for path in unique_paths:
            path_parts = [part for part in path.parts if part != "/"]
            suffix_length = min(suffix_lengths[path], len(path_parts))
            suffix = "/".join(path_parts[-suffix_length:])
            by_suffix.setdefault(suffix, []).append(path)

        collisions = [group for group in by_suffix.values() if len(group) > 1]
        if not collisions:
            resolved: dict[Path, str] = {}
            for suffix, group in by_suffix.items():
                if len(group) == 1:
                    resolved[group[0]] = suffix
            return resolved

        progressed = False
        for group in collisions:
            for path in group:
                path_parts = [part for part in path.parts if part != "/"]
                if suffix_lengths[path] < len(path_parts):
                    suffix_lengths[path] += 1
                    progressed = True
        if not progressed:
            return {path: path.as_posix().lstrip("/") for path in unique_paths}


def rewrite_json_value(value: object, replacements: dict[str, str]) -> object:
    if isinstance(value, dict):
        return {key: rewrite_json_value(inner, replacements) for key, inner in value.items()}
    if isinstance(value, list):
        return [rewrite_json_value(inner, replacements) for inner in value]
    if isinstance(value, str):
        updated = value
        for local_path, remote_uri in replacements.items():
            updated = updated.replace(local_path, remote_uri)
        return updated
    return value


def sanitize_command_directory_args(command: object) -> object:
    if isinstance(command, str):
        try:
            tokens = shlex.split(command)
        except ValueError:
            return command
        sanitized = sanitize_command_directory_args(tokens)
        if isinstance(sanitized, list):
            return shlex.join(str(token) for token in sanitized)
        return command
    if isinstance(command, list):
        sanitized = [str(token) for token in command]
        index = 0
        while index < len(sanitized):
            placeholder = DIRECTORY_ARG_PLACEHOLDERS.get(sanitized[index])
            if placeholder and index + 1 < len(sanitized):
                sanitized[index + 1] = placeholder
                index += 2
                continue
            index += 1
        return sanitized
    return command


def sanitize_directory_args_in_json(value: object) -> object:
    if isinstance(value, dict):
        rewritten: dict[str, object] = {}
        for key, inner in value.items():
            if key in {"command", "observed_command"}:
                rewritten[key] = sanitize_command_directory_args(inner)
            else:
                rewritten[key] = sanitize_directory_args_in_json(inner)
        return rewritten
    if isinstance(value, list):
        return [sanitize_directory_args_in_json(inner) for inner in value]
    return value


def metadata_snapshot_path(metadata_path: Path) -> Path:
    orig_path = Path(f"{metadata_path}.orig")
    return orig_path if orig_path.exists() else metadata_path


def provenance_snapshot_path(metadata_path: Path) -> Path:
    provenance_path = metadata_path.with_name("geneset.provenance.json")
    orig_path = Path(f"{provenance_path}.orig")
    return orig_path if orig_path.exists() else provenance_path


def build_output_replacements(
    *,
    local_output_root: Path,
    provenance_mirror_remote_prefix: str,
) -> dict[str, str]:
    resolved_local_root = local_output_root.resolve()
    normalized_remote_root = provenance_mirror_remote_prefix.rstrip("/")
    replacements = {
        str(resolved_local_root): normalized_remote_root,
        resolved_local_root.as_uri(): normalized_remote_root,
    }
    return dict(sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True))


def build_execution_replacements(dig_dir: Path) -> dict[str, str]:
    resolved_dig_dir = dig_dir.resolve()
    cli_py = resolved_dig_dir / "src" / "geneset_extractors" / "cli.py"
    replacements: dict[str, str] = {
        str(resolved_dig_dir): "dig-gene-set-extractors",
        resolved_dig_dir.as_uri(): "dig-gene-set-extractors",
    }
    if cli_py.exists():
        replacements[str(cli_py.resolve())] = "geneset_extractors.cli"
        replacements[cli_py.resolve().as_uri()] = "geneset_extractors.cli"
    return dict(sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True))


def build_source_input_replacements(
    *,
    metadata_paths: list[Path],
    local_output_root: Path,
    source_map: dict[str, str],
) -> dict[str, str]:
    input_paths: set[Path] = set()
    for metadata_path in metadata_paths:
        provenance_path = provenance_snapshot_path(metadata_path)
        if not provenance_path.exists():
            continue
        for source_path in extract_file_paths_from_provenance(provenance_path):
            if is_within_directory(source_path, local_output_root):
                continue
            input_paths.add(source_path)

    replacements: dict[str, str] = {}
    for source_path in sorted(input_paths):
        source_key = str(source_path)
        source_uri = source_map.get(source_key)
        if not source_uri:
            continue
        replacements[source_key] = source_uri
        replacements[source_path.as_uri()] = source_uri
    return dict(sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True))


def rewrite_metadata_and_provenance(
    *,
    metadata_paths: list[Path],
    rewrite_passes: list[dict[str, str]],
) -> None:
    if not any(rewrite_passes):
        return
    for metadata_path in metadata_paths:
        for path in (metadata_path, metadata_path.with_name("geneset.provenance.json")):
            if not path.exists():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            rewritten = sanitize_directory_args_in_json(payload)
            for replacements in rewrite_passes:
                if not replacements:
                    continue
                rewritten = rewrite_json_value(rewritten, replacements)
            path.write_text(json.dumps(rewritten, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    model_dir = Path(args.model_dir).resolve()
    dig_dir = Path(args.dig_dir).resolve()
    if not dig_dir.exists() or not dig_dir.is_dir():
        raise SystemExit(f"Missing dig-gene-set-extractors directory: {dig_dir}")
    template = ""
    if not args.show_template_vars:
        if not args.description_template_tsv:
            raise SystemExit("--description_template_tsv is required unless --show_template_vars is used")
        template_map = read_template_map(Path(args.description_template_tsv).resolve())
        template = template_map.get(args.model_id, "")
        if not template:
            raise SystemExit(f"No description_template found for model_id={args.model_id}")
    metadata_paths = discover_metadata_paths(model_dir)
    source_map: dict[str, str] = {}
    if args.local_input_source_map_tsv:
        source_map_path = Path(args.local_input_source_map_tsv).resolve()
        if not source_map_path.exists():
            raise SystemExit(f"Missing source map TSV: {source_map_path}")
        source_map = read_input_source_map(source_map_path)
    snapshot_originals(metadata_paths)
    snapshot_gmt_originals(model_dir)
    restore_from_originals(metadata_paths)
    restore_gmt_from_originals(model_dir)

    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH", "").strip()
    dig_pythonpath = str(dig_dir / "src")
    env["PYTHONPATH"] = dig_pythonpath if not existing_pythonpath else f"{dig_pythonpath}{os.pathsep}{existing_pythonpath}"
    regenerate_model_sidecars(
        args=args,
        model_dir=model_dir,
        metadata_paths=metadata_paths,
        env=env,
    )

    for metadata_path in metadata_paths:
        ensure_model_sidecar(metadata_path, args.model_id)
        cmd = [
            str(Path(args.python_bin).resolve()),
            "-m",
            "geneset_extractors.cli",
            "metadata",
            "patch",
            str(metadata_path),
        ]
        if args.show_template_vars:
            cmd.append("--show_template_vars")
        else:
            cmd.extend(["--description_template", template])
        run_command(cmd, cwd=dig_dir, env=env)

    local_output_root = (
        Path(args.provenance_mirror_local_prefix).resolve()
        if args.provenance_mirror_local_prefix
        else model_dir
    )
    replacements: dict[str, str] = {}
    if args.provenance_mirror_remote_prefix:
        replacements.update(
            build_output_replacements(
                local_output_root=local_output_root,
                provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
            )
        )
    if source_map:
        replacements.update(
            build_source_input_replacements(
                metadata_paths=metadata_paths,
                local_output_root=local_output_root,
                source_map=source_map,
            )
        )
    replacements.update(build_execution_replacements(dig_dir))
    rewrite_passes: list[dict[str, str]] = []
    if replacements:
        rewrite_passes.append(dict(sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True)))
    if rewrite_passes:
        rewrite_metadata_and_provenance(
            metadata_paths=metadata_paths,
            rewrite_passes=rewrite_passes,
        )
    if not args.show_template_vars:
        rewrite_gmt_descriptions(
            model_dir=model_dir,
            template_map=template_map,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
