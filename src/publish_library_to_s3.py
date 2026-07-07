#!/usr/bin/env python3

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urlparse


TRANSIENT_BASENAMES = {
    ".DS_Store",
    "Thumbs.db",
}

TRANSIENT_SUFFIXES = {
    ".swp",
    ".swo",
    ".tmp",
    ".bak",
    ".orig",
    ".filepart",
    ":Zone.Identifier",
}


class CandidateFile(object):
    def __init__(
        self,
        local_path,  # type: Path
        relative_path,  # type: str
        s3_uri,  # type: str
        size_bytes,  # type: int
        category,  # type: str
        requirement,  # type: str
        upload_path=None,  # type: Optional[Path]
    ):
        self.local_path = local_path
        self.relative_path = relative_path
        self.s3_uri = s3_uri
        self.size_bytes = size_bytes
        self.category = category
        self.requirement = requirement
        self.upload_path = upload_path


def parse_args():  # type: () -> argparse.Namespace
    parser = argparse.ArgumentParser(
        description=(
            "Publish one library run output tree to S3 without modifying local metadata or provenance files."
        )
    )
    parser.add_argument(
        "--local_output_root",
        required=True,
        help="Local output directory from a library run.",
    )
    parser.add_argument(
        "--s3_output_root",
        required=True,
        help="Destination S3 URI that mirrors the local output root.",
    )
    parser.add_argument(
        "--model_id",
        help="Optional comma-delimited model identifier list to publish from the library output tree, for example AB1,AC1,HZ1.",
    )
    parser.add_argument(
        "--manifest_out",
        help="Optional TSV manifest path. Defaults to <local_output_root>/publish_library_manifest.tsv.",
    )
    parser.add_argument(
        "--path_map_out",
        help="Optional TSV path for a compact local-path to remote-URI reference table.",
    )
    parser.add_argument(
        "--provenance_only_outputs",
        action="store_true",
        help=(
            "Upload only selected geneset.provenance.json files plus files under "
            "--local_output_root that are explicitly referenced by those provenance files."
        ),
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite objects that already exist in S3.")
    parser.add_argument("--dry_run", action="store_true", help="Evaluate and log actions without uploading.")
    parser.add_argument(
        "--force_publish",
        action="store_true",
        help="Skip S3 existence checks and prefix listings. For real uploads, requires --overwrite.",
    )
    parser.add_argument("--aws_cli_bin", default="aws", help="AWS CLI executable to use. Default: aws.")
    return parser.parse_args()


def ensure_directory(path, label):  # type: (Path, str) -> Path
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise SystemExit(f"Missing {label}: {resolved}")
    if not resolved.is_dir():
        raise SystemExit(f"Expected {label} to be a directory: {resolved}")
    return resolved


def is_within_directory(path, root):  # type: (Path, Path) -> bool
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def parse_s3_uri(s3_uri):  # type: (str) -> Tuple[str, str]
    parsed = urlparse(s3_uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise SystemExit(f"Expected S3 URI like s3://bucket/prefix, got: {s3_uri}")
    bucket = parsed.netloc
    prefix = parsed.path.lstrip("/")
    return bucket, prefix


def shell_join(parts):  # type: (List[str]) -> str
    return " ".join(_shell_quote(part) for part in parts)


def _shell_quote(text):  # type: (str) -> str
    return "'" + text.replace("'", "'\"'\"'") + "'"


def log_line(path, text):  # type: (Path, str) -> None
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(text.rstrip("\n") + "\n")


def should_skip_path(path):  # type: (Path) -> bool
    if path.is_symlink():
        return True
    if "__pycache__" in path.parts:
        return True
    if path.name in TRANSIENT_BASENAMES:
        return True
    if any(path.name.endswith(suffix) for suffix in TRANSIENT_SUFFIXES):
        return True
    return False


def parse_model_ids(raw_model_ids):  # type: (Optional[str]) -> List[str]
    if not raw_model_ids:
        return []
    model_ids = []  # type: List[str]
    seen = set()  # type: Set[str]
    for part in raw_model_ids.split(","):
        model_id = part.strip()
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        model_ids.append(model_id)
    return model_ids


def _parts_contain_model_id(parts, model_id):  # type: (Tuple[str, ...], str) -> bool
    for index in range(len(parts) - 1):
        if parts[index] == "models" and parts[index + 1] == model_id:
            return True
    return False


def path_matches_model_filter(path, local_output_root, model_ids):  # type: (Path, Path, List[str]) -> bool
    if not model_ids:
        return True
    try:
        relative_parts = path.relative_to(local_output_root).parts
    except ValueError:
        relative_parts = path.parts
    for model_id in model_ids:
        if _parts_contain_model_id(relative_parts, model_id):
            return True
        if _parts_contain_model_id(local_output_root.parts, model_id):
            return True
    return False


def iter_output_candidates(*, local_output_root, s3_output_root, excluded_paths=None, model_ids=None):  # type: (**Any) -> List[CandidateFile]
    candidates = []  # type: List[CandidateFile]
    normalized_s3_root = s3_output_root.rstrip("/")
    excluded_resolved_paths = set(path.resolve() for path in (excluded_paths or []))  # type: Set[Path]
    model_ids = model_ids or []
    print("scanning_output_tree root={0}".format(local_output_root), flush=True)
    for index, path in enumerate(sorted(local_output_root.rglob("*")), 1):
        if index == 1 or index % 5000 == 0:
            print("scanning_output_tree entries_seen={0} files_kept={1}".format(index, len(candidates)), flush=True)
        if should_skip_path(path) or not path.is_file():
            continue
        if path.resolve() in excluded_resolved_paths:
            continue
        if not path_matches_model_filter(path, local_output_root, model_ids):
            continue
        relative_path = path.relative_to(local_output_root).as_posix()
        candidates.append(
            CandidateFile(
                local_path=path,
                relative_path=relative_path,
                s3_uri=f"{normalized_s3_root}/{relative_path}",
                size_bytes=path.stat().st_size,
                category="output",
                requirement="local_output_root",
                upload_path=None,
            )
        )
    print("scanning_output_tree complete files_kept={0}".format(len(candidates)), flush=True)
    return candidates


def iter_provenance_paths(local_output_root, model_ids=None):  # type: (Path, Optional[List[str]]) -> List[Path]
    paths = []
    model_ids = model_ids or []
    print("scanning_provenance_files root={0}".format(local_output_root), flush=True)
    for index, path in enumerate(sorted(local_output_root.rglob("geneset.provenance.json")), 1):
        if index == 1 or index % 250 == 0:
            print("scanning_provenance_files found={0}".format(index), flush=True)
        if should_skip_path(path):
            continue
        if not path_matches_model_filter(path, local_output_root, model_ids):
            continue
        paths.append(path)
    print("scanning_provenance_files complete found={0}".format(len(paths)), flush=True)
    return paths


def _candidate_strings_from_file_node(node):  # type: (Dict[str, Any]) -> List[str]
    values = []  # type: List[str]
    c2m2_properties = node.get("c2m2_properties") or {}
    for candidate in (
        c2m2_properties.get("local_id"),
        node.get("dcc_url"),
        node.get("drc_url"),
    ):
        if isinstance(candidate, str) and candidate not in values:
            values.append(candidate)
    return values


def _normalize_s3_uri_prefix(s3_uri):  # type: (str) -> str
    return s3_uri.rstrip("/")


def _map_mirrored_remote_candidate_to_local_path(
    candidate,  # type: str
    local_output_root,  # type: Path
    s3_output_root,  # type: Optional[str]
):  # type: (...) -> Optional[Path]
    if not s3_output_root:
        return None
    normalized_output_root = _normalize_s3_uri_prefix(s3_output_root)
    if candidate == normalized_output_root:
        return local_output_root.resolve()
    prefix = normalized_output_root + "/"
    if not candidate.startswith(prefix):
        return None
    relative_path = candidate[len(prefix) :]
    if not relative_path:
        return None
    return (local_output_root / relative_path).resolve()


def _resolve_provenance_file_candidate(
    candidate,  # type: str
    local_output_root,  # type: Path
    s3_output_root=None,  # type: Optional[str]
):  # type: (...) -> Optional[Path]
    if not candidate:
        return None

    mirrored_local_path = _map_mirrored_remote_candidate_to_local_path(
        candidate,
        local_output_root,
        s3_output_root,
    )
    if mirrored_local_path is not None:
        if mirrored_local_path.exists() and mirrored_local_path.is_file() and not should_skip_path(mirrored_local_path):
            return mirrored_local_path

    parsed = urlparse(candidate)

    candidate_texts = []  # type: List[str]
    if parsed.scheme or candidate.startswith("//"):
        path_text = parsed.path.lstrip("/")
        if path_text:
            candidate_texts.append(path_text)
            path_parts = [part for part in Path(path_text).parts if part not in ("", "/")]
            for marker in ("genesets", "workflow", "extractor", "models"):
                if marker in path_parts:
                    suffix = "/".join(path_parts[path_parts.index(marker) :])
                    if suffix and suffix not in candidate_texts:
                        candidate_texts.append(suffix)
    else:
        candidate_texts.append(candidate)

    candidate_paths = []  # type: List[Path]
    for candidate_text in candidate_texts:
        path = Path(candidate_text)
        if path.is_absolute():
            candidate_paths.append(path)
        else:
            candidate_paths.append((local_output_root.parent / path))
            candidate_paths.append(local_output_root / path)
            candidate_paths.append(local_output_root / path.name)

    seen = set()  # type: Set[Path]
    for candidate_path in candidate_paths:
        try:
            resolved = candidate_path.resolve()
        except Exception:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if not resolved.exists() or not resolved.is_file() or should_skip_path(resolved):
            continue
        return resolved
    return None


def extract_local_output_paths_from_provenance(
    provenance_path,  # type: Path
    local_output_root,  # type: Path
    s3_output_root=None,  # type: Optional[str]
):  # type: (...) -> List[Path]
    try:
        payload = json.loads(provenance_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Unable to parse provenance JSON {provenance_path}: {exc}") from exc

    paths = set()  # type: Set[Path]
    for graph in payload.values():
        for node in graph.get("nodes", []):
            if node.get("type") != "File":
                continue
            for candidate in _candidate_strings_from_file_node(node):
                resolved = _resolve_provenance_file_candidate(candidate, local_output_root, s3_output_root=s3_output_root)
                if resolved is None:
                    continue
                if is_within_directory(resolved, local_output_root):
                    paths.add(resolved)
    return sorted(paths)


def extract_existing_file_paths_from_provenance(provenance_path):  # type: (Path) -> List[Path]
    try:
        payload = json.loads(provenance_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Unable to parse provenance JSON {provenance_path}: {exc}") from exc

    all_input_paths = set()  # type: Set[Path]
    all_generated_paths = set()  # type: Set[Path]
    for graph in payload.values():
        file_path_by_id = {}  # type: Dict[str, Path]
        for node in graph.get("nodes", []):
            if node.get("type") != "File":
                continue
            node_id = node.get("id")
            if not isinstance(node_id, str):
                continue
            c2m2_properties = node.get("c2m2_properties") or {}
            candidate = c2m2_properties.get("local_id") or node.get("dcc_url") or node.get("drc_url")
            if not isinstance(candidate, str) or not candidate.startswith("/"):
                continue
            path = Path(candidate)
            if path.exists() and path.is_file() and not should_skip_path(path):
                file_path_by_id[node_id] = path.resolve()

        input_paths = set()  # type: Set[Path]
        generated_paths = set()  # type: Set[Path]
        for edge in graph.get("edges", []):
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


def build_unique_input_relative_paths(paths):  # type: (List[Path]) -> Dict[Path, str]
    unique_paths = sorted(set(paths))
    if not unique_paths:
        return {}

    suffix_lengths = {path: 1 for path in unique_paths}  # type: Dict[Path, int]

    while True:
        by_suffix = {}  # type: Dict[str, List[Path]]
        for path in unique_paths:
            path_parts = [part for part in path.parts if part != "/"]
            suffix_length = min(suffix_lengths[path], len(path_parts))
            suffix = "/".join(path_parts[-suffix_length:])
            by_suffix.setdefault(suffix, []).append(path)

        collisions = [group for group in by_suffix.values() if len(group) > 1]
        if not collisions:
            resolved = {}  # type: Dict[Path, str]
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


def resolve_input_candidates_from_provenance(
    *,
    local_output_root,  # type: Path
    output_candidates,  # type: List[CandidateFile]
    provenance_paths,  # type: List[Path]
    s3_input_root,  # type: str
):  # type: (**Any) -> List[CandidateFile]
    normalized_s3_root = s3_input_root.rstrip("/")
    by_path = {}  # type: Dict[Path, CandidateFile]
    output_file_paths = {candidate.local_path.resolve() for candidate in output_candidates}  # type: Set[Path]

    print("resolving_provenance_inputs files={0}".format(len(provenance_paths)), flush=True)
    for index, provenance_path in enumerate(provenance_paths, 1):
        if index == 1 or index % 100 == 0 or index == len(provenance_paths):
            print(
                "resolving_provenance_inputs {0}/{1} unique_inputs={2}".format(
                    index,
                    len(provenance_paths),
                    len(by_path),
                ),
                flush=True,
            )
        provenance_rel = provenance_path.relative_to(local_output_root).as_posix()
        for source_path in extract_existing_file_paths_from_provenance(provenance_path):
            if source_path in output_file_paths:
                continue
            if is_within_directory(source_path, local_output_root):
                continue
            existing = by_path.get(source_path)
            requirement = f"provenance:{provenance_rel}"
            if existing:
                prior = {part for part in existing.requirement.split(" | ") if part}
                prior.add(requirement)
                requirement = " | ".join(sorted(prior))
            by_path[source_path] = CandidateFile(
                local_path=source_path,
                relative_path="",
                s3_uri="",
                size_bytes=source_path.stat().st_size,
                category="input",
                requirement=requirement,
                upload_path=None,
            )

    relative_paths = build_unique_input_relative_paths(list(by_path.keys()))
    for source_path, candidate in by_path.items():
        candidate.relative_path = relative_paths[source_path]
        candidate.s3_uri = f"{normalized_s3_root}/{candidate.relative_path}"

    print("resolving_provenance_inputs complete unique_inputs={0}".format(len(by_path)), flush=True)
    return sorted(by_path.values(), key=lambda candidate: candidate.relative_path)


def filter_output_candidates_to_provenance_paths(
    *,
    local_output_root,  # type: Path
    output_candidates,  # type: List[CandidateFile]
    provenance_paths,  # type: List[Path]
    s3_output_root=None,  # type: Optional[str]
):  # type: (**Any) -> List[CandidateFile]
    if not provenance_paths:
        return []

    by_path = {candidate.local_path.resolve(): candidate for candidate in output_candidates}  # type: Dict[Path, CandidateFile]
    keep_paths = set(path.resolve() for path in provenance_paths)  # type: Set[Path]

    print("filtering_output_candidates_to_provenance files={0}".format(len(provenance_paths)), flush=True)
    for index, provenance_path in enumerate(provenance_paths, 1):
        if index == 1 or index % 100 == 0 or index == len(provenance_paths):
            print(
                "filtering_output_candidates_to_provenance {0}/{1} kept_paths={2}".format(
                    index,
                    len(provenance_paths),
                    len(keep_paths),
                ),
                flush=True,
            )
        keep_paths.update(
            extract_local_output_paths_from_provenance(
                provenance_path,
                local_output_root,
                s3_output_root=s3_output_root,
            )
        )

    filtered = []  # type: List[CandidateFile]
    for path in sorted(keep_paths):
        candidate = by_path.get(path)
        if candidate is not None:
            filtered.append(candidate)
    print(
        "filtering_output_candidates_to_provenance complete filtered_files={0}".format(len(filtered)),
        flush=True,
    )
    return filtered


def run_aws_command(
    args,  # type: List[str]
    *,
    log_path,  # type: Path
):  # type: (**Any) -> subprocess.CompletedProcess
    log_line(log_path, f"$ {shell_join(args)}")
    try:
        child_env = os.environ.copy()
        child_env["AWS_PAGER"] = ""
        completed = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            universal_newlines=True,
            check=False,
            env=child_env,
        )
    except FileNotFoundError as exc:
        raise SystemExit(f"Missing AWS CLI executable: {args[0]}") from exc
    if completed.stdout:
        log_line(log_path, completed.stdout.rstrip("\n"))
    return completed


def s3_object_exists(
    *,
    aws_cli_bin,  # type: str
    s3_uri,  # type: str
    log_path,  # type: Path
):  # type: (**Any) -> Tuple[bool, str]
    bucket, key = parse_s3_uri(s3_uri)
    completed = run_aws_command(
        [aws_cli_bin, "s3api", "head-object", "--bucket", bucket, "--key", key],
        log_path=log_path,
    )
    if completed.returncode == 0:
        return True, ""
    stdout = completed.stdout or ""
    if "Not Found" in stdout or "404" in stdout:
        return False, ""
    return False, stdout.strip()


def list_s3_keys_under_prefix(
    *,
    aws_cli_bin,  # type: str
    s3_uri_root,  # type: str
    log_path,  # type: Path
):  # type: (**Any) -> Tuple[Set[str], str]
    bucket, prefix = parse_s3_uri(s3_uri_root)
    keys = set()  # type: Set[str]
    continuation_token = None  # type: Optional[str]

    while True:
        command = [aws_cli_bin, "s3api", "list-objects-v2", "--bucket", bucket, "--prefix", prefix]
        if continuation_token:
            command.extend(["--continuation-token", continuation_token])
        completed = run_aws_command(command, log_path=log_path)
        if completed.returncode != 0:
            return set(), (completed.stdout or "").strip()
        try:
            payload = json.loads(completed.stdout or "{}")
        except Exception as exc:
            return set(), "Unable to parse list-objects-v2 response for {0}: {1}".format(s3_uri_root, exc)
        for item in payload.get("Contents", []):
            key = item.get("Key")
            if isinstance(key, str):
                keys.add(key)
        if not payload.get("IsTruncated"):
            break
        continuation_token = payload.get("NextContinuationToken")
        if not continuation_token:
            break

    return keys, ""


def upload_file(
    *,
    aws_cli_bin,  # type: str
    local_path,  # type: Path
    s3_uri,  # type: str
    log_path,  # type: Path
):  # type: (**Any) -> Tuple[bool, str]
    completed = run_aws_command(
        [aws_cli_bin, "s3", "cp", str(local_path), s3_uri],
        log_path=log_path,
    )
    return completed.returncode == 0, (completed.stdout or "").strip()


def write_manifest(path, rows):  # type: (Path, Iterable[Dict[str, Any]]) -> None
    fieldnames = [
        "category",
        "local_path",
        "relative_path",
        "s3_uri",
        "size_bytes",
        "requirement",
        "status",
        "upload_attempted",
        "error_message",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_path_map(path, rows):  # type: (Path, Iterable[Dict[str, Any]]) -> None
    fieldnames = [
        "category",
        "local_path",
        "remote_uri",
        "relative_path",
        "requirement",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_summary(path, payload):  # type: (Path, Dict[str, Any]) -> None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_publisher_artifact_paths(*, log_path, manifest_path, summary_path, path_map_path):  # type: (**Any) -> Set[Path]
    paths = {
        log_path.resolve(),
        manifest_path.resolve(),
        summary_path.resolve(),
    }  # type: Set[Path]
    if path_map_path is not None:
        paths.add(path_map_path.resolve())
    return paths


def main():  # type: () -> int
    args = parse_args()
    if args.force_publish and not args.dry_run and not args.overwrite:
        raise SystemExit("--force_publish requires --overwrite for non-dry-run uploads.")
    local_output_root = ensure_directory(Path(args.local_output_root), "local output root")
    _bucket, _prefix = parse_s3_uri(args.s3_output_root)
    model_ids = parse_model_ids(args.model_id)

    manifest_path = (
        Path(args.manifest_out).expanduser().resolve()
        if args.manifest_out
        else local_output_root / "publish_library_manifest.tsv"
    )
    path_map_path = (
        Path(args.path_map_out).expanduser().resolve()
        if args.path_map_out
        else None
    )
    log_path = local_output_root / "publish_library_to_s3.log"
    summary_path = local_output_root / "publish_summary.json"
    if log_path.exists():
        log_path.unlink()

    invocation = ["python3", str(Path(__file__).resolve()), *sys.argv[1:]]
    log_line(log_path, f"$ {shell_join(invocation)}")
    publisher_artifact_paths = build_publisher_artifact_paths(
        log_path=log_path,
        manifest_path=manifest_path,
        summary_path=summary_path,
        path_map_path=path_map_path,
    )

    output_candidates = iter_output_candidates(
        local_output_root=local_output_root,
        s3_output_root=args.s3_output_root,
        excluded_paths=publisher_artifact_paths,
        model_ids=model_ids,
    )
    provenance_paths = iter_provenance_paths(local_output_root, model_ids=model_ids)
    if args.provenance_only_outputs:
        output_candidates = filter_output_candidates_to_provenance_paths(
            local_output_root=local_output_root,
            output_candidates=output_candidates,
            provenance_paths=provenance_paths,
            s3_output_root=args.s3_output_root,
        )
    log_line(log_path, f"discovered_output_files={len(output_candidates)}")
    log_line(log_path, f"scanned_provenance_files={len(provenance_paths)}")
    print(
        "publish_library_to_s3 outputs={0} provenance_files={1}".format(
            len(output_candidates),
            len(provenance_paths),
        ),
        flush=True,
    )

    candidates = output_candidates
    manifest_rows = []  # type: List[Dict[str, Any]]
    uploaded_count = 0
    skipped_existing_count = 0
    failed_count = 0
    output_bucket, output_prefix = parse_s3_uri(args.s3_output_root)
    output_existing_keys = set()  # type: Set[str]
    if args.force_publish:
        print("force_publish=true", flush=True)
    else:
        print("listing_s3 output_prefix={0}".format(args.s3_output_root), flush=True)
        output_existing_keys, output_list_error = list_s3_keys_under_prefix(
            aws_cli_bin=args.aws_cli_bin,
            s3_uri_root=args.s3_output_root,
            log_path=log_path,
        )
        if output_list_error:
            raise SystemExit("Unable to list existing S3 output objects: {0}".format(output_list_error))

    total_candidates = len(candidates)
    for index, candidate in enumerate(candidates, 1):
        if index == 1 or index % 25 == 0 or index == total_candidates:
            print(
                "checking_s3 {0}/{1} category={2} path={3}".format(
                    index,
                    total_candidates,
                    candidate.category,
                    candidate.relative_path,
                ),
                flush=True,
            )
        row = {
            "category": candidate.category,
            "local_path": str(candidate.local_path),
            "relative_path": candidate.relative_path,
            "s3_uri": candidate.s3_uri,
            "size_bytes": candidate.size_bytes,
            "requirement": candidate.requirement,
            "status": "",
            "upload_attempted": "false",
            "error_message": "",
        }
        if args.force_publish:
            exists = False
        else:
            candidate_bucket, candidate_key = parse_s3_uri(candidate.s3_uri)
            exists = candidate_bucket == output_bucket and candidate_key in output_existing_keys
        if exists and not args.overwrite:
            row["status"] = "skipped_existing"
            skipped_existing_count += 1
            manifest_rows.append(row)
            continue

        row["upload_attempted"] = "true"
        if args.dry_run:
            if args.force_publish:
                row["status"] = "would_upload_unchecked"
            else:
                row["status"] = "would_overwrite" if exists and args.overwrite else "would_upload"
            manifest_rows.append(row)
            continue

        ok, upload_output = upload_file(
            aws_cli_bin=args.aws_cli_bin,
            local_path=candidate.upload_path or candidate.local_path,
            s3_uri=candidate.s3_uri,
            log_path=log_path,
        )
        if ok:
            row["status"] = "overwritten" if exists and args.overwrite else "uploaded"
            uploaded_count += 1
        else:
            row["status"] = "failed"
            row["error_message"] = upload_output
            failed_count += 1
        manifest_rows.append(row)

    write_manifest(manifest_path, manifest_rows)
    if path_map_path is not None:
        path_map_rows = []
        for candidate in candidates:
            path_map_rows.append(
                {
                    "category": candidate.category,
                    "local_path": str(candidate.local_path),
                    "remote_uri": candidate.s3_uri,
                    "relative_path": candidate.relative_path,
                    "requirement": candidate.requirement,
                }
            )
        write_path_map(path_map_path, path_map_rows)
    summary_payload = {
        "local_output_root": str(local_output_root),
        "s3_output_root": args.s3_output_root,
        "model_id": args.model_id,
        "model_ids": model_ids,
        "provenance_only_outputs": bool(args.provenance_only_outputs),
        "dry_run": bool(args.dry_run),
        "overwrite": bool(args.overwrite),
        "force_publish": bool(args.force_publish),
        "n_output_candidates": len(output_candidates),
        "n_provenance_files": len(provenance_paths),
        "n_uploaded": uploaded_count,
        "n_skipped_existing": skipped_existing_count,
        "n_failed": failed_count,
        "manifest_path": str(manifest_path),
        "path_map_path": str(path_map_path) if path_map_path is not None else None,
        "log_path": str(log_path),
    }
    write_summary(summary_path, summary_payload)
    log_line(
        log_path,
        "summary "
        f"n_output_candidates={len(output_candidates)} "
        f"n_provenance_files={len(provenance_paths)} "
        f"n_uploaded={uploaded_count} "
        f"n_skipped_existing={skipped_existing_count} "
        f"n_failed={failed_count}",
    )
    print(json.dumps(summary_payload, sort_keys=True))
    return 1 if failed_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
