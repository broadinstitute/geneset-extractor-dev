#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from library_onboard import ensure_dir, extract_bundle_zip, read_json


REQUIRED_PACKAGE_DIRS = ("config", "run", "src")
OPTIONAL_PACKAGE_DIRS = ("planning",)
TOP_LEVEL_DOCS = ("README.md",)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage a collaborator submission package into a canonical library tree candidate."
    )
    parser.add_argument("--submission_zip", required=True, help="Collaborator submission archive.")
    parser.add_argument("--stage_root", required=True, help="Directory where the canonical staging tree will be written.")
    parser.add_argument(
        "--library_name",
        default="",
        help="Override the destination library directory name. Defaults to library_slug or library_name from config.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace the existing staged library directory if present.",
    )
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def extract_archive(submission_zip: Path, stage_root: Path) -> Path:
    unpack_root = stage_root / "_unpacked_submission"
    if unpack_root.exists():
        shutil.rmtree(unpack_root)
    ensure_dir(unpack_root)
    archive_root = extract_bundle_zip(submission_zip, unpack_root)
    if archive_root == unpack_root:
        children = [path for path in unpack_root.iterdir() if path.is_dir()]
        if len(children) == 1:
            return children[0]
    return archive_root


def detect_package_root(archive_root: Path) -> Path | None:
    if (archive_root / "code").is_dir():
        return archive_root / "code"
    if all((archive_root / name).exists() for name in REQUIRED_PACKAGE_DIRS):
        return archive_root
    matches = sorted(
        {
            path.parent.parent
            for path in archive_root.rglob("bundle_manifest.json")
            if path.parent.name == "config"
        }
    )
    return matches[0] if matches else None


def determine_library_dir_name(package_root: Path, explicit_name: str) -> str:
    if explicit_name.strip():
        return explicit_name.strip()
    library_config_path = package_root / "config" / "library_config.json"
    if library_config_path.is_file():
        payload = read_json(library_config_path)
        slug = str(payload.get("library_slug", "")).strip()
        if slug:
            return slug
        name = str(payload.get("library_name", "")).strip()
        if name:
            return name
    return package_root.name


def safe_name(name: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in name).strip("_") or "Library"


def copy_tree_if_present(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)
    return True


def build_report(
    submission_zip: Path,
    archive_root: Path,
    package_root: Path,
    staged_library_root: Path,
    copied_paths: list[str],
    missing_optional_paths: list[str],
) -> dict[str, Any]:
    return {
        "submission_zip": str(submission_zip),
        "archive_root": str(archive_root),
        "package_root": str(package_root),
        "staged_library_root": str(staged_library_root),
        "copied_paths": copied_paths,
        "missing_optional_paths": missing_optional_paths,
    }


def main() -> int:
    args = parse_args()
    submission_zip = Path(args.submission_zip).expanduser().resolve()
    if not submission_zip.is_file():
        raise SystemExit(f"Submission archive not found: {submission_zip}")
    stage_root = Path(args.stage_root).expanduser().resolve()
    ensure_dir(stage_root)
    archive_root = extract_archive(submission_zip, stage_root)
    package_root = detect_package_root(archive_root)
    if package_root is None:
        raise SystemExit("Unable to detect a generated package root in the submission archive.")
    library_dir_name = safe_name(determine_library_dir_name(package_root, args.library_name))
    staged_library_root = stage_root / library_dir_name
    if staged_library_root.exists():
        if not args.overwrite:
            raise SystemExit(
                f"Staged library directory already exists: {staged_library_root}. Use --overwrite to replace it."
            )
        shutil.rmtree(staged_library_root)
    ensure_dir(staged_library_root)

    copied_paths: list[str] = []
    for relative in REQUIRED_PACKAGE_DIRS:
        src = package_root / relative
        if not src.exists():
            raise SystemExit(f"Required package path missing: {src}")
        dst = staged_library_root / relative
        copy_tree_if_present(src, dst)
        copied_paths.append(relative)
    missing_optional_paths: list[str] = []
    for relative in OPTIONAL_PACKAGE_DIRS + TOP_LEVEL_DOCS:
        src = package_root / relative
        dst = staged_library_root / relative
        copied = copy_tree_if_present(src, dst)
        if copied:
            copied_paths.append(relative)
        else:
            missing_optional_paths.append(relative)

    report = build_report(
        submission_zip=submission_zip,
        archive_root=archive_root,
        package_root=package_root,
        staged_library_root=staged_library_root,
        copied_paths=copied_paths,
        missing_optional_paths=missing_optional_paths,
    )
    write_json(stage_root / "canonicalization_report.json", report)
    write_text(
        stage_root / "canonicalization_report.md",
        "\n".join(
            [
                "# Canonicalization Report",
                "",
                "- Status: `pass`",
                f"- Submission zip: {submission_zip}",
                f"- Archive root: {archive_root}",
                f"- Package root: {package_root}",
                f"- Staged library root: {staged_library_root}",
                f"- Copied paths: {', '.join(copied_paths)}",
                f"- Missing optional paths: {', '.join(missing_optional_paths) if missing_optional_paths else 'none'}",
                "",
            ]
        ),
    )
    print(
        json.dumps(
            {
                "stage_root": str(stage_root),
                "staged_library_root": str(staged_library_root),
                "canonicalization_report": str(stage_root / "canonicalization_report.json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
