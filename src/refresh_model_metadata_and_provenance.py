#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import os
import shlex
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Patch geneset metadata descriptions for one model output directory "
            "and rewrite provenance for every affected geneset."
        )
    )
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--model_dir", required=True)
    parser.add_argument("--description_template_tsv", required=True)
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument("--dig_dir", required=True)
    parser.add_argument("--provenance_mirror_local_prefix")
    parser.add_argument("--provenance_mirror_remote_prefix")
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


def run_command(cmd: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    print("$ " + shell_join(cmd), flush=True)
    subprocess.run(cmd, cwd=str(cwd), env=env, check=True)


def main() -> int:
    args = parse_args()
    model_dir = Path(args.model_dir).resolve()
    dig_dir = Path(args.dig_dir).resolve()
    if not dig_dir.exists() or not dig_dir.is_dir():
        raise SystemExit(f"Missing dig-gene-set-extractors directory: {dig_dir}")
    template_map = read_template_map(Path(args.description_template_tsv).resolve())
    template = template_map.get(args.model_id, "")
    if not template:
        raise SystemExit(f"No description_template found for model_id={args.model_id}")
    metadata_paths = discover_metadata_paths(model_dir)

    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH", "").strip()
    dig_pythonpath = str(dig_dir / "src")
    env["PYTHONPATH"] = dig_pythonpath if not existing_pythonpath else f"{dig_pythonpath}{os.pathsep}{existing_pythonpath}"

    for metadata_path in metadata_paths:
        cmd = [
            str(Path(args.python_bin).resolve()),
            "-m",
            "geneset_extractors.cli",
            "metadata",
            "patch",
            str(metadata_path),
            "--description_template",
            template,
        ]
        if args.provenance_mirror_local_prefix:
            cmd.extend(["--provenance_mirror_local_prefix", args.provenance_mirror_local_prefix])
        if args.provenance_mirror_remote_prefix:
            cmd.extend(["--provenance_mirror_remote_prefix", args.provenance_mirror_remote_prefix])
        run_command(cmd, cwd=dig_dir, env=env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
