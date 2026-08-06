"""Explicit, local coordination checks between a wrapper submission and DIG."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from .validator import ValidationResult, validate_submission
from .yaml_loader import load


def _run(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, env=env, check=False)


def _git(repo: Path, *args: str) -> tuple[bool, str]:
    result = _run(["git", *args], repo)
    return result.returncode == 0, result.stdout.strip() or result.stderr.strip()


def declared_identifiers(payload: dict[str, Any]) -> list[str]:
    dig = payload.get("dig", {})
    values = dig.get("identifiers", []) if isinstance(dig, dict) else []
    return [str(value) for value in values if str(value).strip() and str(value) != "TODO"]


def inspect_dig_checkout(repo: Path, declared_commit: str, allow_development: bool) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    ok, head = _git(repo, "rev-parse", "HEAD")
    if not ok:
        return [("error", f"not a usable DIG Git checkout: {head}")]
    ok, dirty = _git(repo, "status", "--porcelain")
    if not ok:
        issues.append(("error", f"could not inspect DIG status: {dirty}"))
    elif dirty and not allow_development:
        issues.append(("error", "DIG checkout is dirty; use --development-dig-checkout explicitly for local development"))
    if re.fullmatch(r"[0-9a-f]{40}", declared_commit):
        if head != declared_commit and not allow_development:
            issues.append(("error", f"DIG HEAD {head} does not match declared commit {declared_commit}"))
    elif not allow_development:
        issues.append(("error", "declared DIG commit is not a full SHA; use an explicit development override only for drafts"))
    return issues


def coordinated_validate(
    submission: Path,
    dig_repo: Path,
    *,
    dig_python: str = sys.executable,
    smoke: bool = False,
    development_dig_checkout: bool = False,
) -> ValidationResult:
    result = validate_submission(submission)
    if not result.ok:
        return result
    path = submission / "submission.yaml" if submission.is_dir() else submission
    payload = load(path)
    status = str(payload.get("submission_status", "draft"))
    dig = payload.get("dig", {}) if isinstance(payload.get("dig"), dict) else {}
    declared_commit = str(dig.get("commit", ""))
    if status == "ready" and not re.fullmatch(r"[0-9a-f]{40}", declared_commit):
        result.add("error", "dig_commit", "wrapper: ready submissions require a full lowercase DIG commit SHA")
        return result
    for level, message in inspect_dig_checkout(dig_repo.resolve(), declared_commit, development_dig_checkout):
        result.add(level, "dig_checkout", "DIG: " + message)
    if not result.ok:
        return result
    env = {**os.environ, "PYTHONPATH": str(dig_repo.resolve() / "src") + os.pathsep + os.environ.get("PYTHONPATH", "")}
    imported = _run([dig_python, "-c", "import geneset_extractors; print(geneset_extractors.__version__)"], dig_repo, env)
    if imported.returncode != 0:
        result.add("error", "dig_import", "DIG: CLI package is not importable: " + imported.stderr.strip())
        return result
    identifiers = declared_identifiers(payload)
    if not identifiers:
        if status == "ready":
            result.add("error", "dig_identifier", "DIG: ready submission has no declared identifiers")
        else:
            result.add("warning", "dig_identifier", "DIG: draft submission has no concrete identifiers; DIG checks skipped")
        return result
    for identifier in identifiers:
        command = [dig_python, "-m", "geneset_extractors.cli", "submission", "validate", identifier]
        checked = _run(command, dig_repo, env)
        if checked.returncode != 0:
            result.add("error", "dig_identifier", f"DIG: validation failed for {identifier}: {checked.stderr.strip() or checked.stdout.strip()}")
        elif not smoke:
            result.add("warning", "dig_smoke_skipped", f"DIG: {identifier} registration/import check passed; smoke execution not requested")
    return result
