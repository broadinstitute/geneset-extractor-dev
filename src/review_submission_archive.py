#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from library_onboard import ARCHETYPES, ensure_dir, extract_bundle_zip, read_json, read_tsv


LOCAL_PATH_PATTERNS = (
    "/home/",
    "/Users/",
    "/humgen/",
    "/var/",
    "/tmp/",
)

URI_PREFIX_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
WINDOWS_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")
PATH_TOKEN_RE = re.compile(r"(/[^ \t\n\r\"']+|[A-Za-z]:[\\/][^ \t\n\r\"']+)")


@dataclass
class ReviewContext:
    submission_zip: Path
    review_root: Path
    unpack_root: Path
    reports_root: Path
    archive_root: Path
    package_root: Path | None
    outputs_root: Path | None
    library_config: dict[str, Any] | None
    bundle_manifest: dict[str, Any] | None
    model_rows: list[dict[str, str]]
    partition_rows: list[dict[str, str]]
    archetype: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Review a collaborator submission archive and emit maintainer-side validation reports."
    )
    parser.add_argument("--submission_zip", required=True, help="Submission archive produced by a collaborator.")
    parser.add_argument("--review_root", required=True, help="Directory where the review bundle will be written.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing review_root if it already exists.",
    )
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def make_md(title: str, status: str, summary_lines: list[str], findings: list[str] | None = None) -> str:
    lines = [f"# {title}", "", f"- Status: `{status}`"]
    if summary_lines:
        lines.append("")
        lines.extend(f"- {line}" for line in summary_lines)
    if findings:
        lines.append("")
        lines.append("## Findings")
        lines.append("")
        lines.extend(f"- {line}" for line in findings)
    lines.append("")
    return "\n".join(lines)


def prepare_review_root(review_root: Path, overwrite: bool) -> tuple[Path, Path]:
    if review_root.exists():
        if not overwrite:
            raise SystemExit(f"Review root already exists: {review_root}. Use --overwrite to replace it.")
        shutil.rmtree(review_root)
    unpack_root = review_root / "unpacked_submission"
    reports_root = review_root / "reports"
    ensure_dir(unpack_root)
    ensure_dir(reports_root)
    return unpack_root, reports_root


def find_archive_root(unpack_root: Path) -> Path:
    children = [path for path in unpack_root.iterdir() if path.is_dir()]
    if len(children) == 1:
        return children[0]
    return unpack_root


def detect_package_root(archive_root: Path) -> Path | None:
    direct = archive_root / "code"
    if direct.is_dir():
        return direct
    if (archive_root / "config").is_dir() and (archive_root / "run").is_dir() and (archive_root / "src").is_dir():
        return archive_root
    matches = sorted(
        {
            path.parent.parent
            for path in archive_root.rglob("bundle_manifest.json")
            if path.parent.name == "config"
        }
    )
    return matches[0] if matches else None


def detect_outputs_root(archive_root: Path) -> Path | None:
    direct = archive_root / "outputs"
    if direct.is_dir():
        return direct
    candidate_names = ("genesets", "logs", "validation")
    if any((archive_root / name).exists() for name in candidate_names):
        return archive_root
    output_dirs = []
    for path in archive_root.rglob("*"):
        if path.is_dir() and path.name in {"outputs", "genesets"}:
            output_dirs.append(path)
    if not output_dirs:
        return None
    direct_outputs = [path for path in output_dirs if path.name == "outputs"]
    return (direct_outputs or output_dirs)[0]


def load_optional_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    return read_json(path)


def load_optional_tsv(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.is_file():
        return []
    return read_tsv(path)


def gather_context(args: argparse.Namespace) -> ReviewContext:
    submission_zip = Path(args.submission_zip).expanduser().resolve()
    if not submission_zip.is_file():
        raise SystemExit(f"Submission archive not found: {submission_zip}")
    review_root = Path(args.review_root).expanduser().resolve()
    unpack_root, reports_root = prepare_review_root(review_root, args.overwrite)
    archive_root = extract_bundle_zip(submission_zip, unpack_root)
    archive_root = find_archive_root(unpack_root) if archive_root == unpack_root else archive_root
    package_root = detect_package_root(archive_root)
    outputs_root = detect_outputs_root(archive_root)
    library_config = load_optional_json(package_root / "config" / "library_config.json" if package_root else None)
    bundle_manifest = load_optional_json(package_root / "config" / "bundle_manifest.json" if package_root else None)
    model_rows = load_optional_tsv(package_root / "config" / "model_list.tsv" if package_root else None)
    partition_rows = load_optional_tsv(package_root / "config" / "partition_list.tsv" if package_root else None)
    archetype = ""
    if library_config:
        archetype = str(library_config.get("archetype", "")).strip()
    elif bundle_manifest:
        archetype = str(bundle_manifest.get("archetype", "")).strip()
    return ReviewContext(
        submission_zip=submission_zip,
        review_root=review_root,
        unpack_root=unpack_root,
        reports_root=reports_root,
        archive_root=archive_root,
        package_root=package_root,
        outputs_root=outputs_root,
        library_config=library_config,
        bundle_manifest=bundle_manifest,
        model_rows=model_rows,
        partition_rows=partition_rows,
        archetype=archetype,
    )


def write_report_pair(
    reports_root: Path,
    stem: str,
    payload: dict[str, Any],
    title: str,
    status: str,
    summary_lines: list[str],
    findings: list[str] | None = None,
) -> None:
    write_json(reports_root / f"{stem}.json", payload)
    write_text(reports_root / f"{stem}.md", make_md(title, status, summary_lines, findings))


def stage_intake(ctx: ReviewContext) -> dict[str, Any]:
    payload = {
        "submission_zip": str(ctx.submission_zip),
        "review_root": str(ctx.review_root),
        "archive_root": str(ctx.archive_root),
        "package_root": str(ctx.package_root) if ctx.package_root else "",
        "outputs_root": str(ctx.outputs_root) if ctx.outputs_root else "",
        "library_name": str((ctx.library_config or {}).get("library_name", "")),
        "library_slug": str((ctx.library_config or {}).get("library_slug", "")),
        "archetype": ctx.archetype,
        "n_models": len(ctx.model_rows),
        "n_partitions": len(ctx.partition_rows),
    }
    findings = []
    if ctx.package_root is None:
        findings.append("No generated package root was detected.")
    if ctx.outputs_root is None:
        findings.append("No outputs root was detected.")
    status = "pass" if not findings else "fail"
    write_report_pair(
        ctx.reports_root,
        "intake_summary",
        payload,
        "Intake Summary",
        status,
        [
            f"Archive root: {ctx.archive_root}",
            f"Package root: {ctx.package_root or 'missing'}",
            f"Outputs root: {ctx.outputs_root or 'missing'}",
            f"Archetype: {ctx.archetype or 'missing'}",
            f"Models: {len(ctx.model_rows)}",
            f"Partitions: {len(ctx.partition_rows)}",
        ],
        findings,
    )
    return payload


def stage_structure(ctx: ReviewContext) -> dict[str, Any]:
    package_checks: dict[str, bool] = {}
    output_checks: dict[str, bool] = {}
    findings: list[str] = []
    if ctx.package_root:
        expected_package_paths = (
            "config/bundle_manifest.json",
            "config/library_config.json",
            "config/model_list.tsv",
            "config/model_manifest.tsv",
            "config/model_description_templates.tsv",
            "run",
            "src",
        )
        for relative in expected_package_paths:
            package_checks[relative] = (ctx.package_root / relative).exists()
        missing = [name for name, present in package_checks.items() if not present]
        findings.extend(f"Missing package path: {name}" for name in missing)
    else:
        findings.append("Generated package root missing.")
    if ctx.outputs_root:
        expected_output_paths = ("genesets",)
        for relative in expected_output_paths:
            output_checks[relative] = (ctx.outputs_root / relative).exists()
    else:
        findings.append("Outputs root missing.")
    status = "pass" if not findings else "fail"
    payload = {
        "package_root": str(ctx.package_root) if ctx.package_root else "",
        "outputs_root": str(ctx.outputs_root) if ctx.outputs_root else "",
        "package_checks": package_checks,
        "output_checks": output_checks,
        "findings": findings,
    }
    write_report_pair(
        ctx.reports_root,
        "structure_report",
        payload,
        "Structure Report",
        status,
        [
            f"Package checks passed: {sum(package_checks.values())}/{len(package_checks)}",
            f"Output checks passed: {sum(output_checks.values())}/{len(output_checks)}",
        ],
        findings,
    )
    return payload


def stage_archetype(ctx: ReviewContext) -> dict[str, Any]:
    findings: list[str] = []
    checks: dict[str, bool] = {}
    checks["archetype_present"] = bool(ctx.archetype)
    checks["archetype_supported"] = ctx.archetype in ARCHETYPES
    if ctx.model_rows:
        unique_families = sorted({row.get("model_family", "") for row in ctx.model_rows if row.get("model_family", "")})
        checks["model_rows_present"] = True
    else:
        unique_families = []
        checks["model_rows_present"] = False
    if not checks["archetype_present"]:
        findings.append("No archetype declared in library_config.json or bundle_manifest.json.")
    elif not checks["archetype_supported"]:
        findings.append(f"Unsupported archetype: {ctx.archetype}")
    else:
        expected_family = str(ARCHETYPES[ctx.archetype]["model_family"])
        mismatched_models = [
            row.get("model_id", "")
            for row in ctx.model_rows
            if str(row.get("model_family", "")).strip() != expected_family
        ]
        checks["model_family_matches_archetype"] = not mismatched_models
        if mismatched_models:
            findings.append(
                "Model rows do not match the expected archetype model_family: "
                + ", ".join(sorted(mismatched_models))
            )
    payload = {
        "archetype": ctx.archetype,
        "supported_archetypes": sorted(ARCHETYPES),
        "model_families_present": unique_families,
        "checks": checks,
        "findings": findings,
    }
    status = "pass" if not findings else "fail"
    write_report_pair(
        ctx.reports_root,
        "archetype_report",
        payload,
        "Archetype Report",
        status,
        [
            f"Declared archetype: {ctx.archetype or 'missing'}",
            f"Model families present: {', '.join(unique_families) if unique_families else 'none'}",
        ],
        findings,
    )
    return payload


def stage_artifacts(ctx: ReviewContext) -> dict[str, Any]:
    findings: list[str] = []
    all_files = list(ctx.outputs_root.rglob("*")) if ctx.outputs_root else []
    gmt_files = [path for path in all_files if path.is_file() and path.name == "genesets.gmt"]
    meta_files = [path for path in all_files if path.is_file() and path.name == "geneset.meta.json"]
    provenance_files = [path for path in all_files if path.is_file() and path.name == "geneset.provenance.json"]
    model_files = [path for path in all_files if path.is_file() and path.name == "geneset.model.json"]
    orig_files = [path for path in all_files if path.is_file() and path.suffix == ".orig"]
    if not gmt_files:
        findings.append("No genesets.gmt files were found.")
    if not meta_files:
        findings.append("No geneset.meta.json files were found.")
    if not provenance_files:
        findings.append("No geneset.provenance.json files were found.")
    if not model_files:
        findings.append("No geneset.model.json files were found.")
    payload = {
        "counts": {
            "gmt_files": len(gmt_files),
            "metadata_files": len(meta_files),
            "provenance_files": len(provenance_files),
            "model_files": len(model_files),
            "orig_files": len(orig_files),
        },
        "examples": {
            "gmt_files": [str(path.relative_to(ctx.outputs_root)) for path in gmt_files[:5]] if ctx.outputs_root else [],
            "metadata_files": [str(path.relative_to(ctx.outputs_root)) for path in meta_files[:5]] if ctx.outputs_root else [],
            "provenance_files": [str(path.relative_to(ctx.outputs_root)) for path in provenance_files[:5]] if ctx.outputs_root else [],
        },
        "findings": findings,
    }
    status = "pass" if not findings else "fail"
    write_report_pair(
        ctx.reports_root,
        "artifact_report",
        payload,
        "Artifact Report",
        status,
        [
            f"GMT files: {len(gmt_files)}",
            f"Metadata files: {len(meta_files)}",
            f"Provenance files: {len(provenance_files)}",
            f"Model sidecars: {len(model_files)}",
            f"Preserved originals: {len(orig_files)}",
        ],
        findings,
    )
    return payload


def iter_json_strings(value: Any) -> list[str]:
    values: list[str] = []
    if isinstance(value, str):
        values.append(value)
    elif isinstance(value, dict):
        for subvalue in value.values():
            values.extend(iter_json_strings(subvalue))
    elif isinstance(value, list):
        for subvalue in value:
            values.extend(iter_json_strings(subvalue))
    return values


def extract_local_like_strings(value: Any) -> list[str]:
    hits: set[str] = set()
    for text in iter_json_strings(value):
        if any(marker in text for marker in LOCAL_PATH_PATTERNS) or WINDOWS_PATH_RE.match(text):
            hits.add(text)
        for token in PATH_TOKEN_RE.findall(text):
            if any(marker in token for marker in LOCAL_PATH_PATTERNS) or WINDOWS_PATH_RE.match(token):
                hits.add(token)
    return sorted(hits)


def has_uri_or_url(value: str) -> bool:
    return bool(URI_PREFIX_RE.match(value))


def collect_analysis_commands(provenance_payload: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    for node in provenance_payload.get("nodes", []):
        if not isinstance(node, dict):
            continue
        if node.get("type") != "Analysis":
            continue
        command = node.get("command")
        if isinstance(command, str) and command.strip():
            commands.append(command)
    return commands


def stage_provenance(ctx: ReviewContext) -> dict[str, Any]:
    findings: list[str] = []
    local_path_hits: dict[str, list[str]] = {}
    description_mismatches: list[str] = []
    missing_descriptions: list[str] = []
    unstable_external_inputs: list[str] = []
    command_chain_failures: list[str] = []
    provenance_files = list(ctx.outputs_root.rglob("geneset.provenance.json")) if ctx.outputs_root else []
    for provenance_path in provenance_files:
        payload = read_json(provenance_path)
        relpath = str(provenance_path.relative_to(ctx.outputs_root)) if ctx.outputs_root else str(provenance_path)
        hits = extract_local_like_strings(payload)
        if hits:
            local_path_hits[relpath] = hits[:20]
        commands = collect_analysis_commands(payload)
        if not commands:
            command_chain_failures.append(f"{relpath}: no Analysis command nodes found")
        gene_set_descriptions = [
            node.get("description", "")
            for node in payload.get("nodes", [])
            if isinstance(node, dict) and node.get("type") == "GeneSet"
        ]
        if any(not str(description).strip() for description in gene_set_descriptions):
            missing_descriptions.append(f"{relpath}: empty GeneSet description")
        meta_path = provenance_path.with_name("geneset.meta.json")
        if meta_path.is_file():
            meta_payload = read_json(meta_path)
            meta_description = str(meta_payload.get("description", "")).strip()
            if not meta_description:
                missing_descriptions.append(f"{relpath}: empty metadata description")
            provenance_description = next((str(item).strip() for item in gene_set_descriptions if str(item).strip()), "")
            if meta_description and provenance_description and meta_description != provenance_description:
                description_mismatches.append(relpath)
        for node in payload.get("nodes", []):
            if not isinstance(node, dict):
                continue
            if node.get("type") != "File":
                continue
            role = str(node.get("role", ""))
            node_id = str(node.get("id", "")).strip()
            if role.startswith("output"):
                continue
            if node_id and not has_uri_or_url(node_id):
                if any(node_id.startswith(marker) for marker in LOCAL_PATH_PATTERNS) or WINDOWS_PATH_RE.match(node_id):
                    unstable_external_inputs.append(f"{relpath}: {node_id}")
    if local_path_hits:
        findings.append(f"Local path leakage detected in {len(local_path_hits)} provenance file(s).")
    if description_mismatches:
        findings.append(f"Metadata/provenance description mismatches detected in {len(description_mismatches)} file(s).")
    if missing_descriptions:
        findings.append(f"Missing descriptions detected in {len(missing_descriptions)} location(s).")
    if unstable_external_inputs:
        findings.append(f"Non-URI file nodes detected in {len(unstable_external_inputs)} provenance location(s).")
    if command_chain_failures:
        findings.append(f"Command-chain issues detected in {len(command_chain_failures)} provenance file(s).")
    payload = {
        "counts": {
            "provenance_files": len(provenance_files),
            "files_with_local_path_leakage": len(local_path_hits),
            "description_mismatches": len(description_mismatches),
            "missing_descriptions": len(missing_descriptions),
            "unstable_external_inputs": len(unstable_external_inputs),
            "command_chain_failures": len(command_chain_failures),
        },
        "examples": {
            "local_path_leakage": local_path_hits,
            "description_mismatches": description_mismatches[:20],
            "missing_descriptions": missing_descriptions[:20],
            "unstable_external_inputs": unstable_external_inputs[:20],
            "command_chain_failures": command_chain_failures[:20],
        },
        "findings": findings,
    }
    status = "pass" if not findings else "fail"
    write_report_pair(
        ctx.reports_root,
        "provenance_report",
        payload,
        "Provenance Report",
        status,
        [
            f"Provenance files scanned: {len(provenance_files)}",
            f"Files with local path leakage: {len(local_path_hits)}",
            f"Description mismatches: {len(description_mismatches)}",
            f"Missing descriptions: {len(missing_descriptions)}",
        ],
        findings,
    )
    return payload


def parse_gmt_line(line: str) -> tuple[str, str, list[str]]:
    fields = line.rstrip("\n").split("\t")
    if len(fields) < 3:
        return fields[0] if fields else "", "", []
    return fields[0], fields[1], fields[2:]


def stage_gmt(ctx: ReviewContext) -> dict[str, Any]:
    findings: list[str] = []
    empty_descriptions: list[str] = []
    malformed_lines: list[str] = []
    signed_name_issues: list[str] = []
    gmt_files = list(ctx.outputs_root.rglob("genesets.gmt")) if ctx.outputs_root else []
    expected_signed = bool(ARCHETYPES.get(ctx.archetype, {}).get("signed_output", False)) if ctx.archetype else False
    for gmt_path in gmt_files:
        relpath = str(gmt_path.relative_to(ctx.outputs_root)) if ctx.outputs_root else str(gmt_path)
        with gmt_path.open("r", encoding="utf-8") as handle:
            for index, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                name, description, genes = parse_gmt_line(line)
                if not genes:
                    malformed_lines.append(f"{relpath}:{index}")
                    continue
                if not description.strip():
                    empty_descriptions.append(f"{relpath}:{index}:{name}")
                if expected_signed and not (name.endswith("_up") or name.endswith("_dn")):
                    signed_name_issues.append(f"{relpath}:{index}:{name}")
    if empty_descriptions:
        findings.append(f"Empty GMT descriptions detected in {len(empty_descriptions)} row(s).")
    if malformed_lines:
        findings.append(f"Malformed GMT rows detected in {len(malformed_lines)} row(s).")
    if signed_name_issues:
        findings.append(f"Signed naming issues detected in {len(signed_name_issues)} GMT row(s).")
    payload = {
        "counts": {
            "gmt_files": len(gmt_files),
            "empty_descriptions": len(empty_descriptions),
            "malformed_lines": len(malformed_lines),
            "signed_name_issues": len(signed_name_issues),
        },
        "examples": {
            "empty_descriptions": empty_descriptions[:20],
            "malformed_lines": malformed_lines[:20],
            "signed_name_issues": signed_name_issues[:20],
        },
        "findings": findings,
    }
    status = "pass" if not findings else "fail"
    write_report_pair(
        ctx.reports_root,
        "gmt_report",
        payload,
        "GMT Report",
        status,
        [
            f"GMT files scanned: {len(gmt_files)}",
            f"Empty descriptions: {len(empty_descriptions)}",
            f"Malformed rows: {len(malformed_lines)}",
            f"Signed naming issues: {len(signed_name_issues)}",
        ],
        findings,
    )
    return payload


def stage_publishability(
    ctx: ReviewContext,
    structure_report: dict[str, Any],
    archetype_report: dict[str, Any],
    artifact_report: dict[str, Any],
    provenance_report: dict[str, Any],
    gmt_report: dict[str, Any],
) -> dict[str, Any]:
    major_failures = []
    if structure_report.get("findings"):
        major_failures.extend(structure_report["findings"])
    if archetype_report.get("findings"):
        major_failures.extend(archetype_report["findings"])
    if artifact_report.get("counts", {}).get("gmt_files", 0) == 0:
        major_failures.append("No GMT files found.")
    if artifact_report.get("counts", {}).get("provenance_files", 0) == 0:
        major_failures.append("No provenance files found.")
    if provenance_report.get("counts", {}).get("files_with_local_path_leakage", 0) > 0:
        major_failures.append("Local path leakage remains in provenance.")
    if provenance_report.get("counts", {}).get("command_chain_failures", 0) > 0:
        major_failures.append("At least one provenance file is missing Analysis command nodes.")
    minor_failures = []
    if provenance_report.get("counts", {}).get("description_mismatches", 0) > 0:
        minor_failures.append("Metadata/provenance descriptions differ.")
    if provenance_report.get("counts", {}).get("missing_descriptions", 0) > 0:
        minor_failures.append("Some metadata or GeneSet descriptions are empty.")
    if gmt_report.get("counts", {}).get("empty_descriptions", 0) > 0:
        minor_failures.append("Some GMT second-column descriptions are empty.")
    if gmt_report.get("counts", {}).get("signed_name_issues", 0) > 0:
        minor_failures.append("Some signed GMT names do not end in _up/_dn.")
    if major_failures:
        recommendation = "not_ready"
    elif minor_failures:
        recommendation = "ready_with_minor_repairs"
    else:
        recommendation = "ready"
    payload = {
        "recommendation": recommendation,
        "major_failures": major_failures,
        "minor_failures": minor_failures,
    }
    status = "pass" if recommendation == "ready" else ("warn" if recommendation == "ready_with_minor_repairs" else "fail")
    write_report_pair(
        ctx.reports_root,
        "publishability_summary",
        payload,
        "Publishability Summary",
        status,
        [
            f"Recommendation: {recommendation}",
            f"Major failures: {len(major_failures)}",
            f"Minor failures: {len(minor_failures)}",
        ],
        major_failures + minor_failures,
    )
    return payload


def main() -> int:
    args = parse_args()
    ctx = gather_context(args)
    stage_intake(ctx)
    structure_report = stage_structure(ctx)
    archetype_report = stage_archetype(ctx)
    artifact_report = stage_artifacts(ctx)
    provenance_report = stage_provenance(ctx)
    gmt_report = stage_gmt(ctx)
    publishability_report = stage_publishability(
        ctx,
        structure_report,
        archetype_report,
        artifact_report,
        provenance_report,
        gmt_report,
    )
    print(
        json.dumps(
            {
                "review_root": str(ctx.review_root),
                "recommendation": publishability_report["recommendation"],
                "reports_root": str(ctx.reports_root),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
