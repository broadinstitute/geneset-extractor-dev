#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import fnmatch
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
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
}


@dataclass(frozen=True)
class CandidateFile:
    local_path: Path
    relative_path: str
    s3_uri: str
    size_bytes: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish a local model-output tree to a mirrored S3 prefix.")
    parser.add_argument("--output_root", required=True, help="Local output directory to publish.")
    parser.add_argument("--s3_root", required=True, help="Destination S3 URI prefix, e.g. s3://bucket/prefix.")
    parser.add_argument(
        "--include_glob",
        action="append",
        default=[],
        help="Optional glob on relative paths to include. Can be passed multiple times.",
    )
    parser.add_argument(
        "--exclude_glob",
        action="append",
        default=[],
        help="Optional glob on relative paths to exclude. Can be passed multiple times.",
    )
    parser.add_argument(
        "--manifest_out",
        help="Optional TSV manifest path. Defaults to <output_root>/publish_manifest.tsv.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite objects that already exist in S3.")
    parser.add_argument("--dry_run", action="store_true", help="Evaluate and log actions without uploading.")
    parser.add_argument("--aws_cli_bin", default="aws", help="AWS CLI executable to use. Default: aws.")
    return parser.parse_args()


def ensure_directory(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise SystemExit(f"Missing {label}: {resolved}")
    if not resolved.is_dir():
        raise SystemExit(f"Expected {label} to be a directory: {resolved}")
    return resolved


def parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    parsed = urlparse(s3_uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise SystemExit(f"Expected S3 URI like s3://bucket/prefix, got: {s3_uri}")
    bucket = parsed.netloc
    prefix = parsed.path.lstrip("/")
    return bucket, prefix


def shell_join(parts: list[str]) -> str:
    return " ".join(_shell_quote(part) for part in parts)


def _shell_quote(text: str) -> str:
    return "'" + text.replace("'", "'\"'\"'") + "'"


def log_line(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(text.rstrip("\n") + "\n")


def should_skip_path(path: Path) -> bool:
    if path.is_symlink():
        return True
    if "__pycache__" in path.parts:
        return True
    if path.name in TRANSIENT_BASENAMES:
        return True
    if any(path.name.endswith(suffix) for suffix in TRANSIENT_SUFFIXES):
        return True
    return False


def matches_any_glob(relative_path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(relative_path, pattern) for pattern in patterns)


def iter_candidate_files(
    *,
    output_root: Path,
    s3_root: str,
    include_globs: list[str],
    exclude_globs: list[str],
) -> list[CandidateFile]:
    candidates: list[CandidateFile] = []
    normalized_s3_root = s3_root.rstrip("/")
    for path in sorted(output_root.rglob("*")):
        if should_skip_path(path):
            continue
        if not path.is_file():
            continue
        relative_path = path.relative_to(output_root).as_posix()
        if include_globs and not matches_any_glob(relative_path, include_globs):
            continue
        if exclude_globs and matches_any_glob(relative_path, exclude_globs):
            continue
        candidates.append(
            CandidateFile(
                local_path=path,
                relative_path=relative_path,
                s3_uri=f"{normalized_s3_root}/{relative_path}",
                size_bytes=path.stat().st_size,
            )
        )
    return candidates


def run_aws_command(
    args: list[str],
    *,
    log_path: Path,
) -> subprocess.CompletedProcess[str]:
    log_line(log_path, f"$ {shell_join(args)}")
    completed = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if completed.stdout:
        log_line(log_path, completed.stdout.rstrip("\n"))
    return completed


def s3_object_exists(
    *,
    aws_cli_bin: str,
    s3_uri: str,
    log_path: Path,
) -> tuple[bool, str]:
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


def upload_file(
    *,
    aws_cli_bin: str,
    local_path: Path,
    s3_uri: str,
    log_path: Path,
) -> tuple[bool, str]:
    completed = run_aws_command(
        [aws_cli_bin, "s3", "cp", str(local_path), s3_uri],
        log_path=log_path,
    )
    return completed.returncode == 0, (completed.stdout or "").strip()


def write_manifest(path: Path, rows: Iterable[dict[str, object]]) -> None:
    fieldnames = [
        "local_path",
        "relative_path",
        "s3_uri",
        "size_bytes",
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


def write_summary(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output_root = ensure_directory(Path(args.output_root), "output root")
    _bucket, _prefix = parse_s3_uri(args.s3_root)

    manifest_path = (
        Path(args.manifest_out).expanduser().resolve()
        if args.manifest_out
        else output_root / "publish_manifest.tsv"
    )
    log_path = output_root / "publish_outputs_to_s3.log"
    summary_path = output_root / "publish_summary.json"
    if log_path.exists():
        log_path.unlink()

    invocation = ["python3", str(Path(__file__).resolve()), *sys.argv[1:]]
    log_line(log_path, f"$ {shell_join(invocation)}")
    candidates = iter_candidate_files(
        output_root=output_root,
        s3_root=args.s3_root,
        include_globs=list(args.include_glob),
        exclude_globs=list(args.exclude_glob),
    )
    log_line(log_path, f"discovered_files={len(candidates)}")

    manifest_rows: list[dict[str, object]] = []
    uploaded_count = 0
    skipped_existing_count = 0
    failed_count = 0

    for candidate in candidates:
        exists, existence_error = s3_object_exists(
            aws_cli_bin=args.aws_cli_bin,
            s3_uri=candidate.s3_uri,
            log_path=log_path,
        )
        row: dict[str, object] = {
            "local_path": str(candidate.local_path),
            "relative_path": candidate.relative_path,
            "s3_uri": candidate.s3_uri,
            "size_bytes": candidate.size_bytes,
            "status": "",
            "upload_attempted": "false",
            "error_message": "",
        }
        if existence_error:
            row["status"] = "failed"
            row["error_message"] = existence_error
            failed_count += 1
            manifest_rows.append(row)
            continue
        if exists and not args.overwrite:
            row["status"] = "skipped_existing"
            skipped_existing_count += 1
            manifest_rows.append(row)
            continue

        row["upload_attempted"] = "true"
        if args.dry_run:
            row["status"] = "would_overwrite" if exists and args.overwrite else "would_upload"
            manifest_rows.append(row)
            continue

        ok, upload_output = upload_file(
            aws_cli_bin=args.aws_cli_bin,
            local_path=candidate.local_path,
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
    summary_payload = {
        "output_root": str(output_root),
        "s3_root": args.s3_root,
        "dry_run": bool(args.dry_run),
        "overwrite": bool(args.overwrite),
        "n_candidates": len(candidates),
        "n_uploaded": uploaded_count,
        "n_skipped_existing": skipped_existing_count,
        "n_failed": failed_count,
        "manifest_path": str(manifest_path),
        "log_path": str(log_path),
    }
    write_summary(summary_path, summary_payload)
    log_line(
        log_path,
        "summary "
        f"n_candidates={len(candidates)} "
        f"n_uploaded={uploaded_count} "
        f"n_skipped_existing={skipped_existing_count} "
        f"n_failed={failed_count}",
    )
    print(json.dumps(summary_payload, sort_keys=True))
    return 1 if failed_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
