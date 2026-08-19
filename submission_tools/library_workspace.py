"""Isolated workspaces for creating new gene-set libraries.

This reuses the conservative Git, fork, staging, and coordination primitives
from :mod:`adoption_workspace`; unlike adoption, it never inventories or
compares a legacy library.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import adoption_workspace as shared
from .coordinated import coordinated_validate
from .receipt import write_receipt
from .scaffold import scaffold
from .validator import validate_submission
from .yaml_loader import load

WORKSPACE_MANIFEST = ".submission-workspace.yaml"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _input_files(inputs: Path) -> list[Path]:
    root = inputs.expanduser().resolve()
    if root.is_file():
        return [root]
    if root.is_dir():
        return sorted(path for path in root.rglob("*") if path.is_file() and ".git" not in path.parts)
    raise ValueError(f"input path does not exist: {inputs}")


def inventory_inputs(inputs: Path) -> dict[str, Any]:
    files = _input_files(inputs)
    if not files:
        raise ValueError(f"input directory contains no files: {inputs}")
    source = inputs.expanduser().resolve()
    return {
        "schema_version": "1.0.0",
        "source_path": str(source),
        "read_only": True,
        "files": [
            {
                "path": str(path),
                "relative_path": str(path.relative_to(source)) if source.is_dir() else path.name,
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
                "suffix": "".join(path.suffixes),
            }
            for path in files
        ],
    }


def _validate_location(workspace: Path, inputs: Path) -> tuple[Path, Path]:
    workspace = workspace.expanduser().resolve()
    inputs = inputs.expanduser().resolve()
    if workspace == inputs or shared._same_or_descendant(workspace, inputs) or shared._same_or_descendant(inputs, workspace):
        raise ValueError("New-library workspace must be separate from the read-only --inputs path")
    if shared._inside_git_repository(workspace):
        raise ValueError("New-library workspace must not be nested inside a Git repository")
    if workspace.exists() and any(workspace.iterdir()):
        raise ValueError(f"New-library workspace must be empty: {workspace}")
    return workspace, inputs


def _remote_branch_exists(url: str, branch: str) -> bool:
    completed = shared._run(["git", "ls-remote", "--exit-code", "--heads", url, branch])
    if completed.returncode == 0:
        return True
    # Exit 2 is an actual remote/transport error; do not mistake it for a
    # missing branch and risk colliding with an inaccessible branch.
    if completed.returncode not in {0, 2}:
        return False
    if completed.returncode == 2 and completed.stderr.strip():
        raise ValueError(f"could not inspect remote branch {branch}: {completed.stderr.strip()}")
    return False


def _input_id(index: int, path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9_]+", "_", path.stem).strip("_") or "input"
    return f"input_{index:02d}_{stem}".lower()


def _populate_input_manifest(library: Path, inventory: dict[str, Any]) -> None:
    lines = [
        "input_id\tsource_uri_or_access_instructions\tversion_release\tchecksum\taccess_method\tsmoke_full\tworkflow_stage\tredistribution_status\tcommitted_fixture\tfixture_path"
    ]
    sources = []
    for index, record in enumerate(inventory["files"], start=1):
        input_id = _input_id(index, Path(str(record["path"])))
        source_path = str(record["path"])
        lines.append("\t".join((input_id, source_path, "TODO: source release", "sha256:" + str(record["sha256"]), "local_read_only", "full", "workflow_input", "not_redistributable", "false", "")))
        sources.append({"name": input_id, "uri_or_identifier": source_path, "release": "TODO: source release", "access_restrictions": "local read-only source input; document publication access", "license": "TODO"})
    (library / "reproduction" / "input_manifest.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    submission = library / "submission.yaml"
    payload = load(submission)
    payload["submission_origin"] = {"type": "new"}
    payload["sources"] = sources
    submission.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _prompt(workspace: Path, manifest: dict[str, Any], inventory: dict[str, Any]) -> str:
    return f"""# AI instructions: new gene-set library

You are in an isolated new-library workspace: `{workspace}`. You may modify
only `./dig-gene-set-extractors`, `./geneset-extractor-dev`, `./work`,
`./reports`, and generated workspace metadata. Source inputs listed in
`inputs/input_inventory.json` are **READ ONLY**; do not move, rewrite, rename,
or copy large input data into either Git repository.

DIG branch: `{manifest['repositories']['dig']['work_branch']}`
Wrapper branch: `{manifest['repositories']['wrapper']['work_branch']}`
Baseline: `{manifest['repositories']['dig']['base_branch']}`

All parsing, preprocessing, normalization, statistical modelling, differential
analysis, gene mapping, filtering, ranking, gene-set construction, and reusable
converters/workflows belong in `dig-gene-set-extractors`. The wrapper may only
hold declarative config, thin orchestration, access instructions, manifests,
provenance/description refresh configuration, and publication metadata.

First inspect `inputs/input_inventory.json` and create
`reports/AI_NEW_LIBRARY_PLAN.md` before major scientific decisions. It must
record input interpretation, assay type, comparisons, normalization, statistics,
filtering, ranking, naming, expected outputs, reusable DIG components, new DIG
work required, and unresolved scientific questions. Infer mechanical details
when supported by inputs, but do not silently invent scientific choices such as
contrasts, covariates, thresholds, mappings, or top-K rules.

Before implementing DIG code, inspect available contracts:

```bash
geneset-extractors submission list
geneset-extractors submission describe <identifier>
geneset-extractors submission validate <identifier>
```

Reuse scientifically equivalent DIG functionality. Add DIG fixtures, tests,
and a registered contract before adding a wrapper dispatcher. Populate the
generated input manifest with stable source release/access metadata; do not
commit raw/private sources. A finished submission must contain all committed
code and config necessary to regenerate outputs from declared inputs, with no
manual transformations or unexplained intermediates.

Create a low-cost smoke test that exercises the real DIG CLI path, representative
parsing, main transformation, GMT generation, metadata, and provenance when
feasible. Use `./verify-library` from this workspace; it deliberately imports
the workspace's `geneset-extractor-dev/submission_tools`. When it passes, use
`./submit-library` to create draft PRs only. Neither command merges a PR.
"""


def create_library_workspace(*, inputs: Path, workspace: Path, library_id: str, display_name: str | None, pattern: str, github_user: str | None, dig_fork: str | None, wrapper_fork: str | None, base_branch: str = shared.DEFAULT_BASE_BRANCH, work_branch: str | None = None, allow_upstream_origin: bool = False) -> Path:
    workspace, inputs = _validate_location(workspace, inputs)
    inventory = inventory_inputs(inputs)
    dig_fork, wrapper_fork = shared._fork_urls(github_user, dig_fork, wrapper_fork, allow_upstream_origin=allow_upstream_origin)
    work_branch = work_branch or f"submit/{library_id}"
    if _remote_branch_exists(dig_fork, work_branch) or _remote_branch_exists(wrapper_fork, work_branch):
        raise ValueError(f"remote branch {work_branch} already exists; use --work-branch or resume the existing workspace")
    workspace.mkdir(parents=True)
    shared._clone_fork(dig_fork, workspace / "dig-gene-set-extractors", shared.CANONICAL_DIG, base_branch, work_branch)
    shared._clone_fork(wrapper_fork, workspace / "geneset-extractor-dev", shared.CANONICAL_WRAPPER, base_branch, work_branch)
    library = workspace / "geneset-extractor-dev" / library_id
    scaffold(library, library_id, display_name or library_id, pattern)
    _populate_input_manifest(library, inventory)
    shared._write_json(workspace / "inputs" / "input_inventory.json", inventory)
    manifest = {
        "schema_version": "1.0.0", "workflow_type": "new_library", "library_id": library_id,
        "workspace": {"root": str(workspace), "upstream_origin_mode": allow_upstream_origin},
        "source_inputs": {"inventory": "inputs/input_inventory.json", "read_only": True},
        "repositories": {
            "dig": {"path": "dig-gene-set-extractors", "origin": dig_fork, "upstream": shared.CANONICAL_DIG, "base_branch": base_branch, "work_branch": work_branch},
            "wrapper": {"path": "geneset-extractor-dev", "origin": wrapper_fork, "upstream": shared.CANONICAL_WRAPPER, "base_branch": base_branch, "work_branch": work_branch},
        },
        "tooling": {"wrapper_commit": shared._git(workspace / "geneset-extractor-dev", "rev-parse", "HEAD"), "submission_tools_path": "geneset-extractor-dev/submission_tools"},
        "submission": {"wrapper_library_path": f"geneset-extractor-dev/{library_id}", "pattern": pattern},
        "verification": {"last_result": None, "last_receipt": None, "workspace_digest": None},
    }
    shared._write_json(workspace / WORKSPACE_MANIFEST, manifest)
    shared._write_workspace_helper(workspace / "verify-library", "verify-library")
    shared._write_workspace_helper(workspace / "submit-library", "submit-library")
    (workspace / "AI_NEW_LIBRARY_PROMPT.md").write_text(_prompt(workspace, manifest, inventory), encoding="utf-8")
    for name in ("reports", "work"):
        (workspace / name).mkdir()
    return workspace


def load_library_workspace(workspace: Path) -> tuple[Path, dict[str, Any]]:
    root = workspace.expanduser().resolve()
    path = root / WORKSPACE_MANIFEST
    if not path.is_file():
        raise ValueError(f"new-library workspace manifest does not exist: {path}")
    manifest = load(path)
    if not isinstance(manifest, dict) or manifest.get("workflow_type") != "new_library" or str(manifest.get("workspace", {}).get("root", "")) != str(root):
        raise ValueError("new-library workspace manifest does not match the requested workspace")
    return root, manifest


def _paths(root: Path, manifest: dict[str, Any]) -> tuple[Path, Path, Path]:
    repos = manifest["repositories"]
    return root / str(repos["dig"]["path"]), root / str(repos["wrapper"]["path"]), root / str(manifest["submission"]["wrapper_library_path"])


def _inputs_changed(root: Path, manifest: dict[str, Any]) -> list[str]:
    inventory = json.loads((root / str(manifest["source_inputs"]["inventory"])).read_text(encoding="utf-8"))
    changed = []
    for record in inventory.get("files", []):
        path = Path(str(record["path"]))
        if not path.is_file() or path.stat().st_size != record.get("size_bytes") or _sha256(path) != record.get("sha256"):
            changed.append(str(path))
    return changed


def _digest(root: Path, manifest: dict[str, Any]) -> str:
    dig, wrapper, library = _paths(root, manifest)
    values = [shared._git(dig, "rev-parse", "HEAD"), shared._git(dig, "status", "--porcelain"), shared._git(wrapper, "rev-parse", "HEAD"), shared._git(wrapper, "status", "--porcelain")]
    inventory = root / str(manifest["source_inputs"]["inventory"])
    values.append(_sha256(inventory))
    if library.is_dir():
        values.extend(str(path.relative_to(root)) + ":" + _sha256(path) for path in sorted(library.rglob("*")) if path.is_file() and ".git" not in path.parts)
    return hashlib.sha256("\n".join(values).encode()).hexdigest()


def _tooling(root: Path, manifest: dict[str, Any]) -> tuple[bool, Path, Path, str]:
    wrapper = root / str(manifest["repositories"]["wrapper"]["path"])
    expected = (wrapper / "submission_tools").resolve()
    active = Path(__file__).resolve().parent
    return active == expected, expected, active, str(manifest["tooling"].get("wrapper_commit", "unknown"))


def verify_library_workspace(workspace: Path) -> tuple[bool, list[str]]:
    root, manifest = load_library_workspace(workspace)
    tooling_ok, expected, active, commit = _tooling(root, manifest)
    if not tooling_ok:
        return False, ["ERROR: verify-library is running from a submission_tools implementation outside this new-library workspace.", f"Expected: {expected}", f"Active: {active}", f"Run: {root / 'verify-library'}"]
    dig, wrapper, library = _paths(root, manifest)
    messages = [f"INFO: Submission tooling repository: {wrapper}", f"INFO: Submission tooling commit: {commit}", f"INFO: Submission tooling module: {active}"]
    for role, repo, declared in (("DIG", dig, manifest["repositories"]["dig"]), ("wrapper", wrapper, manifest["repositories"]["wrapper"])):
        messages.extend("ERROR: " + issue for issue in shared._repo_safety(repo, declared, role))
        if shared._normalize_remote(str(declared["origin"])) == shared._normalize_remote(str(declared["upstream"])) and not manifest["workspace"].get("upstream_origin_mode"):
            messages.append(f"ERROR: {role} uses canonical upstream as origin without the recorded --allow-upstream-origin override")
    messages.extend(f"ERROR: source input changed: {item}" for item in _inputs_changed(root, manifest))
    if not library.is_dir():
        messages.append(f"ERROR: wrapper library is missing: {library}")
    if not any(message.startswith("ERROR:") for message in messages):
        static = validate_submission(library)
        messages.extend(f"{issue.level.upper()}: wrapper {issue.code}: {issue.message}" for issue in static.issues)
        wrapper_tests = shared._run_wrapper_submission_tests(wrapper)
        if wrapper_tests is not None:
            passed, output = wrapper_tests
            messages.append(("INFO" if passed else "ERROR") + ": wrapper submission-tool tests " + ("passed" if passed else "failed: " + output))
        payload = load(library / "submission.yaml")
        dirty = bool(shared._git(dig, "status", "--porcelain"))
        # Draft creation starts with a TODO DIG pin.  That is an explicit local
        # development state, whereas ready submissions still require an exact,
        # clean matching checkout.
        development = dirty or str(payload.get("submission_status", "draft")) != "ready"
        coordinated = coordinated_validate(library, dig, smoke=True, development_dig_checkout=development)
        messages.extend(f"{issue.level.upper()}: DIG {issue.code}: {issue.message}" for issue in coordinated.issues)
        smoke = str(payload["reproduction"]["smoke_test_command"]).split()
        reproduced = shared._run(smoke, library)
        if reproduced.returncode:
            messages.append("ERROR: smoke reproduction failed: " + (reproduced.stderr.strip() or reproduced.stdout.strip()))
        messages.extend(shared._check_declared_smoke_outputs(library, payload))
    ok = not any(message.startswith("ERROR:") for message in messages)
    receipt = library / "run_receipt.json"
    workspace_digest = _digest(root, manifest)
    write_receipt(
        library / "submission.yaml", dig,
        {"ok": ok, "messages": messages, "workflow_type": "new_library"}, receipt,
        [str(root / "verify-library")],
        {"workflow_type": "new_library", "workspace_digest": workspace_digest,
         "tooling_path": str(active), "tooling_commit": commit},
    )
    # The receipt itself is generated under the library and therefore changes
    # the workspace digest. Record the post-receipt value for stale-checking.
    manifest["verification"] = {"last_result": "PASS" if ok else "FAILED", "last_receipt": str(receipt.relative_to(root)), "workspace_digest": _digest(root, manifest), "completed_at": datetime.now(timezone.utc).isoformat()}
    shared._write_json(root / WORKSPACE_MANIFEST, manifest)
    return ok, messages


def submit_library_workspace(workspace: Path, *, yes: bool = False, allow_upstream_origin: bool = False) -> tuple[bool, list[str]]:
    root, manifest = load_library_workspace(workspace)
    tooling_ok, expected, active, _commit = _tooling(root, manifest)
    if not tooling_ok:
        return False, ["ERROR: submit-library is running from a submission_tools implementation outside this new-library workspace.", f"Expected: {expected}", f"Active: {active}", f"Run: {root / 'submit-library'}"]
    dig, wrapper, library = _paths(root, manifest)
    repositories = manifest["repositories"]
    problems = []
    for role, repo, declared in (("DIG", dig, repositories["dig"]), ("wrapper", wrapper, repositories["wrapper"])):
        problems.extend(shared._repo_safety(repo, declared, role))
        if shared._normalize_remote(str(declared["origin"])) == shared._normalize_remote(str(declared["upstream"])) and not manifest["workspace"].get("upstream_origin_mode"):
            problems.append(f"{role} uses canonical upstream as origin without the recorded --allow-upstream-origin override")
    if problems:
        return False, ["ERROR: " + problem for problem in problems]
    if _inputs_changed(root, manifest):
        return False, ["ERROR: source inputs changed; recreate or verify the workspace after resolving the change"]
    verification = manifest.get("verification", {})
    if verification.get("last_result") != "PASS" or verification.get("workspace_digest") != _digest(root, manifest):
        return False, ["ERROR: verification is missing or stale; run verify-library again"]
    dig_dirty, wrapper_dirty = bool(shared._changed_paths(dig)), bool(shared._changed_paths(wrapper))
    dig_pending = dig_dirty or shared._ahead_of_base(dig, str(repositories["dig"]["base_branch"]))
    wrapper_pending = wrapper_dirty or shared._ahead_of_base(wrapper, str(repositories["wrapper"]["base_branch"]))
    if not dig_pending and not wrapper_pending:
        return False, ["ERROR: no changes are available to submit"]
    if not yes:
        return False, ["Changes to submit:", f"  dig-gene-set-extractors: {'pending' if dig_pending else 'unchanged'}", f"  geneset-extractor-dev: {'pending' if wrapper_pending else 'unchanged'}", "Re-run with --yes to commit and push only to contributor forks."]
    for repo, declared in ((dig, repositories["dig"]), (wrapper, repositories["wrapper"])):
        if not allow_upstream_origin and not shared._is_fork_origin(shared._git(repo, "remote", "get-url", "origin"), str(declared["upstream"])):
            return False, [f"ERROR: refusing to push {repo.name}; origin is canonical upstream"]
    dig_sha = shared._commit_if_changed(dig, f"Add extractor support for {manifest['library_id']}", ("src", "tests", "docs", "pyproject.toml", "README.md", ".gitignore")) if dig_dirty else None
    payload = load(library / "submission.yaml")
    if dig_pending:
        payload["dig"]["commit"] = dig_sha or shared._git(dig, "rev-parse", "HEAD")
        payload["paired_pull_requests"]["dig_gene_set_extractors"] = "TBD"
    else:
        payload["paired_pull_requests"]["dig_gene_set_extractors"] = "N/A"
    shared._write_json(library / "submission.yaml", payload)
    wrapper_sha = shared._commit_if_changed(wrapper, f"Add {manifest['library_id']} gene-set library", (manifest["library_id"], "docs", "submission_tools", "tests", "config", "run", ".gitignore")) if shared._changed_paths(wrapper) else None
    wrapper_pending = wrapper_pending or wrapper_sha is not None
    if dig_pending:
        result = coordinated_validate(library, dig, development_dig_checkout=False)
        if not result.ok:
            return False, ["ERROR: coordinated validation failed after DIG pinning", *[issue.message for issue in result.issues]]
    messages: list[str] = []
    for repo, declared, pending in ((dig, repositories["dig"], dig_pending), (wrapper, repositories["wrapper"], wrapper_pending)):
        if pending:
            completed = shared._run(["git", "push", "-u", "origin", str(declared["work_branch"])], repo)
            if completed.returncode:
                return False, [f"ERROR: push to contributor fork failed for {repo.name}: {completed.stderr.strip()}"]
    if dig_pending:
        dig_pr, message = shared._open_draft_pr(dig, repositories["dig"], f"Add extractor support for {manifest['library_id']}", f"New gene-set library: {manifest['library_id']}\n\nRun verify-library before review.")
        messages.append("DIG: " + message)
        if dig_pr:
            payload = load(library / "submission.yaml")
            payload["paired_pull_requests"]["dig_gene_set_extractors"] = dig_pr
            shared._write_json(library / "submission.yaml", payload)
            shared._commit_if_changed(wrapper, "Record paired DIG pull request URL", (manifest["library_id"],))
            completed = shared._run(["git", "push", "origin", str(repositories["wrapper"]["work_branch"])], wrapper)
            if completed.returncode:
                return False, ["ERROR: could not push paired DIG PR metadata: " + completed.stderr.strip()]
    wrapper_pr, message = shared._open_draft_pr(wrapper, repositories["wrapper"], f"Add {manifest['library_id']} gene-set library", f"New gene-set library: {manifest['library_id']}")
    messages.append("Wrapper: " + message)
    if wrapper_pr:
        payload = load(library / "submission.yaml")
        payload["paired_pull_requests"]["geneset_extractor_dev"] = wrapper_pr
        shared._write_json(library / "submission.yaml", payload)
        shared._commit_if_changed(wrapper, "Record wrapper pull request URL", (manifest["library_id"],))
        completed = shared._run(["git", "push", "origin", str(repositories["wrapper"]["work_branch"])], wrapper)
        if completed.returncode:
            return False, ["ERROR: could not push wrapper PR metadata: " + completed.stderr.strip()]
    messages.append("Branches pushed only to contributor forks; no pull request was merged.")
    return True, messages
