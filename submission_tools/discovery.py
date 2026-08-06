"""Discover new-format submissions from submitted paths, never by library name."""
from __future__ import annotations

from pathlib import Path


def discover_submissions(repo_root: Path, changed_paths: list[str] | None = None) -> list[Path]:
    """Return sorted library roots containing submission.yaml.

    With changed paths, only a submission whose directory contains a changed
    path is returned.  This keeps legacy directories out of CI unless they opt
    into the new format by adding submission.yaml.
    """
    root = repo_root.resolve()
    candidates = sorted(root.rglob("submission.yaml"))
    if changed_paths is None:
        return [path.parent for path in candidates]
    changed = []
    for value in changed_paths:
        candidate = Path(value)
        if candidate.is_absolute():
            try:
                candidate = candidate.resolve().relative_to(root)
            except ValueError:
                continue
        if ".." not in candidate.parts:
            changed.append(candidate)
    result: list[Path] = []
    for submission in candidates:
        relative_root = submission.parent.relative_to(root)
        if any(path == relative_root / "submission.yaml" or relative_root in path.parents for path in changed):
            result.append(submission.parent)
    return result
