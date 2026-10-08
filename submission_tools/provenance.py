"""Thin public wrapper for DIG's persisted-provenance conversion command."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def convert(input_path: Path, *, dig_repo: Path | None, dig_python: str | None,
            metadata: Path | None, output: Path | None, recursive: bool, overwrite: bool) -> int:
    """Delegate without parsing or transforming legacy provenance locally."""
    root = Path(__file__).resolve().parents[1]
    dig = (dig_repo or Path(os.environ.get("DIG_REPO", root.parent / "dig-gene-set-extractors"))).resolve()
    if not (dig / "src" / "geneset_extractors").is_dir():
        print("ERROR: --dig-repo (or DIG_REPO) must identify a dig-gene-set-extractors checkout.", file=sys.stderr)
        return 2
    python = dig_python or sys.executable
    env = {**os.environ, "PYTHONPATH": str(dig / "src") + os.pathsep + os.environ.get("PYTHONPATH", "")}
    command = [python, "-m", "geneset_extractors.cli", "provenance", "convert", str(input_path)]
    if metadata is not None: command.extend(["--metadata", str(metadata)])
    if output is not None: command.extend(["--out", str(output)])
    if recursive: command.append("--recursive")
    if overwrite: command.append("--overwrite")
    probe = subprocess.run([python, "-m", "geneset_extractors.cli", "provenance", "convert", "--help"], cwd=dig, env=env, text=True, capture_output=True, check=False)
    if probe.returncode != 0:
        print("ERROR: the selected DIG installation does not support `provenance convert`; install a DIG version that provides this command.", file=sys.stderr)
        return 2
    # No capture: DIG owns per-file progress, final summary, stderr, and exit status.
    return subprocess.run(command, cwd=dig, env=env, check=False).returncode
