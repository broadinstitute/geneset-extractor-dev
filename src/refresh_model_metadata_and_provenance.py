#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import shlex
import subprocess
import sys
import shutil
from pathlib import Path
from urllib.parse import urlparse


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
    parser.add_argument("--s3_input_root")
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
        if "source_uri" not in fieldnames:
            raise SystemExit("source map TSV must include columns: local_path, source_uri")
        path_column = ""
        if "local_path" in fieldnames:
            path_column = "local_path"
        elif "s3_uri" in fieldnames:
            path_column = "s3_uri"
        else:
            raise SystemExit("source map TSV must include columns: local_path, source_uri")
        mapping: dict[str, str] = {}
        for row in reader:
            local_path = str(row.get(path_column, "")).strip()
            source_uri = str(row.get("source_uri", "")).strip()
            if not local_path and not source_uri:
                continue
            if not local_path or not source_uri:
                raise SystemExit("source map TSV rows must provide both local_path and source_uri")
            if local_path in mapping:
                raise SystemExit(f"Duplicate local_path in source map TSV: {local_path}")
            mapping[local_path] = source_uri
    if not mapping:
        raise SystemExit(f"No source map rows found in {path}")
    return dict(sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True))


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


def run_command(cmd: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    print("$ " + shell_join(cmd), flush=True)
    subprocess.run(cmd, cwd=str(cwd), env=env, check=True)


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


def build_input_replacements(
    *,
    metadata_paths: list[Path],
    local_output_root: Path,
    s3_input_root: str,
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

    normalized_s3_root = s3_input_root.rstrip("/")
    replacements: dict[str, str] = {}
    grouped_parent_dirs = {
        parent
        for parent in {path.parent for path in input_paths}
        if len([path for path in input_paths if path.parent == parent]) > 1
    }

    directory_relative_paths = build_unique_input_relative_paths(sorted(grouped_parent_dirs))
    handled_paths: set[Path] = set()

    for directory_path, relative_dir in directory_relative_paths.items():
        remote_dir_uri = f"{normalized_s3_root}/{relative_dir}"
        replacements[str(directory_path)] = remote_dir_uri
        replacements[directory_path.as_uri()] = remote_dir_uri
        for source_path in sorted(path for path in input_paths if path.parent == directory_path):
            remote_uri = f"{remote_dir_uri}/{source_path.name}"
            replacements[str(source_path)] = remote_uri
            replacements[source_path.as_uri()] = remote_uri
            handled_paths.add(source_path)

    standalone_relative_paths = build_unique_input_relative_paths(sorted(input_paths.difference(handled_paths)))
    for source_path, relative_path in standalone_relative_paths.items():
        remote_uri = f"{normalized_s3_root}/{relative_path}"
        replacements[str(source_path)] = remote_uri
        replacements[source_path.as_uri()] = remote_uri
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
            rewritten = payload
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
    if args.s3_input_root:
        parse_s3_uri(args.s3_input_root)
    source_map: dict[str, str] = {}
    if args.local_input_source_map_tsv:
        source_map_path = Path(args.local_input_source_map_tsv).resolve()
        if not source_map_path.exists():
            raise SystemExit(f"Missing source map TSV: {source_map_path}")
        source_map = read_input_source_map(source_map_path)
    snapshot_originals(metadata_paths)
    restore_from_originals(metadata_paths)

    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH", "").strip()
    dig_pythonpath = str(dig_dir / "src")
    env["PYTHONPATH"] = dig_pythonpath if not existing_pythonpath else f"{dig_pythonpath}{os.pathsep}{existing_pythonpath}"

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
    if args.s3_input_root:
        replacements.update(
            build_input_replacements(
                metadata_paths=metadata_paths,
                local_output_root=local_output_root,
                s3_input_root=args.s3_input_root,
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
