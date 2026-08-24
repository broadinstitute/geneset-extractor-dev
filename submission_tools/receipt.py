from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_commit(root: Path) -> str:
    completed = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False)
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def write_receipt(submission_path: Path, dig_repo: Path, result: dict[str, Any], out_path: Path, command: list[str], workspace_context: dict[str, Any] | None = None) -> None:
    from .yaml_loader import load
    payload = load(submission_path)
    root = submission_path.parent
    receipt = {
        "schema_version": "1.0.0",
        "library_id": payload["library"]["id"],
        "wrapper_commit": _git_commit(root),
        "dig_commit": payload["dig"]["commit"],
        "submission_schema_version": payload["schema_version"],
        "input_manifest_digest": digest(root / payload["reproduction"]["input_manifest"]),
        "output_manifest_digest": digest(root / payload["expected_outputs"]["manifest"]),
        "environment": {"identifier": payload["environment"]["declaration"], "digest": hashlib.sha256(str(payload["environment"]["declaration"]).encode()).hexdigest()},
        "command": command,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "models_expected": [line.split("\t", 1)[0] for line in (root / payload["configs"]["model_config"]).read_text().splitlines()[1:] if line],
        "models_completed": [],
        "validation_result": result,
    }
    if workspace_context:
        # Isolated workflows add their workspace identity without changing the
        # base, versioned receipt contract used by ordinary validation.
        receipt["workspace"] = workspace_context
    adoption = payload.get("adoption")
    if isinstance(adoption, dict):
        policy = adoption.get("comparison_policy")
        if isinstance(policy, dict):
            receipt["adoption_comparison"] = {
                "mode": policy.get("mode", "exact_reproduction"),
                "claim": "scientifically comparable; not set-equivalent" if policy.get("mode") == "scientific_reimplementation" else "set-equivalent when declared mappings pass",
            }
    out_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_receipt(path: Path) -> bool:
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {"schema_version", "library_id", "wrapper_commit", "dig_commit", "submission_schema_version", "input_manifest_digest", "output_manifest_digest", "environment", "command", "started_at", "completed_at", "models_expected", "models_completed", "validation_result"}
    return isinstance(payload, dict) and required <= set(payload) and payload.get("schema_version") == "1.0.0"
