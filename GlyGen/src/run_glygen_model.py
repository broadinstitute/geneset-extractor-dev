#!/usr/bin/env python3
"""Run one GlyGen model through DIG and the shared metadata refresh path."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def _snapshot_sha256(directory: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(directory.rglob("*.json")):
        digest.update(path.relative_to(directory).as_posix().encode() + b"\0" + _sha256(path).encode() + b"\n")
    return "sha256:" + digest.hexdigest()


def _source_uris(path: Path | None) -> dict[Path, str]:
    if path is None:
        return {}
    rows = path.read_text(encoding="utf-8").splitlines()
    header = rows[0].split("\t") if rows else []
    if "local_path" not in header or "source_uri" not in header:
        raise SystemExit("LOCAL_INPUT_SOURCE_MAP_TSV must include local_path and source_uri")
    local_index, uri_index = header.index("local_path"), header.index("source_uri")
    result: dict[Path, str] = {}
    for line in rows[1:]:
        fields = line.split("\t")
        if len(fields) <= max(local_index, uri_index):
            continue
        local, uri = fields[local_index].strip(), fields[uri_index].strip()
        if local and uri:
            candidate = Path(local).expanduser()
            result[(candidate if candidate.is_absolute() else path.parent / candidate).resolve()] = uri
    return result


def _write_source_manifest(path: Path, sources: dict[str, Path], source_uris: dict[Path, str]) -> None:
    payload: dict[str, dict[str, str]] = {}
    for role, source in sources.items():
        resolved = source.resolve()
        payload[role] = {
            "url": source_uris.get(resolved, resolved.as_uri()),
            "version": _snapshot_sha256(resolved) if resolved.is_dir() else _sha256(resolved),
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"sources": payload}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run(command: list[str], env: dict[str, str]) -> None:
    print("$ " + " ".join(command), flush=True)
    subprocess.run(command, check=True, env=env)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_id", required=True, choices=("HZ1", "HZ2"))
    parser.add_argument("--run_root", required=True)
    parser.add_argument("--dig_repo", required=True)
    parser.add_argument("--unicarbkb")
    parser.add_argument("--harvard")
    parser.add_argument("--glyconnect")
    parser.add_argument("--masterlist")
    parser.add_argument("--cache_dir")
    parser.add_argument("--local_input_source_map_tsv")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    dig = Path(args.dig_repo).resolve()
    if not (dig / "src/geneset_extractors").is_dir(): raise SystemExit("--dig_repo must identify a dig-gene-set-extractors checkout")
    if args.model_id == "HZ1":
        names = ("unicarbkb", "harvard", "glyconnect", "masterlist")
        sources = {f"glygen_v1_12_1_{name}": Path(getattr(args, name) or "").resolve() for name in names}
    else:
        sources = {"glygen_api_cache_snapshot": Path(args.cache_dir or "").resolve()}
    invalid = (lambda path: not path.is_file()) if args.model_id == "HZ1" else (lambda path: not path.is_dir())
    if any(invalid(path) for path in sources.values()):
        raise SystemExit("missing declared GlyGen model input")
    model_root = Path(args.run_root).resolve() / args.model_id
    if model_root.exists():
        if not args.overwrite: raise SystemExit(f"output already exists for model={args.model_id}: {model_root}; pass --overwrite")
        shutil.rmtree(model_root)
    workflow, extractor = model_root / "workflow", model_root / "extractor"
    source_map = _source_uris(Path(args.local_input_source_map_tsv).resolve()) if args.local_input_source_map_tsv else {}
    _write_source_manifest(workflow / "source_manifest.json", sources, source_map)
    env = {**os.environ, "PYTHONPATH": str(dig / "src") + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")}
    if args.model_id == "HZ1":
        command = [sys.executable, "-m", "geneset_extractors.cli", "convert", "glygen_glycosylated_proteins", "--model_id", "HZ1", "--out_dir", str(extractor)]
        for name in ("unicarbkb", "harvard", "glyconnect", "masterlist"):
            command.extend([f"--{name}", str(sources[f"glygen_v1_12_1_{name}"])])
    else:
        command = [sys.executable, "-m", "geneset_extractors.cli", "convert", "glygen_glycan_synthesizing_enzymes", "--model_id", "HZ2", "--cache_dir", str(sources["glygen_api_cache_snapshot"]), "--workflow_dir", str(workflow), "--out_dir", str(extractor)]
    _run(command, env)
    refresh = ["bash", str(root.parent / "run/refresh_model_metadata_and_provenance.sh"), "--model_id", args.model_id, "--model_dir", str(model_root), "--description_template_tsv", str(root / "config/model_description_templates.tsv"), "--python_bin", sys.executable]
    if args.local_input_source_map_tsv: refresh.extend(["--local_input_source_map_tsv", args.local_input_source_map_tsv])
    _run(refresh, {**env, "DIG_DIR": str(dig), "PYTHON_BIN": sys.executable})
    return 0


if __name__ == "__main__": raise SystemExit(main())
