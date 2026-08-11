"""Isolated workspace support for adopting legacy gene-set libraries.

This module deliberately keeps all Git mutation inside a contributor-provided
workspace.  It is an orchestration layer over the normal submission validator;
it does not introduce another submission format.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adoption import adoption_report, inventory_legacy
from .coordinated import coordinated_validate
from .legacy_compare import compare_gmt
from .receipt import write_receipt
from .scaffold import scaffold
from .validator import validate_submission
from .yaml_loader import load

CANONICAL_DIG = "https://github.com/flannick/dig-gene-set-extractors.git"
CANONICAL_WRAPPER = "https://github.com/broadinstitute/geneset-extractor-dev.git"
DEFAULT_BASE_BRANCH = "main"
WORKSPACE_MANIFEST = ".adoption-workspace.yaml"


def _run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)


def _git(repo: Path, *args: str) -> str:
    completed = _run(["git", *args], repo)
    if completed.returncode:
        raise ValueError(completed.stderr.strip() or completed.stdout.strip() or f"git {' '.join(args)} failed")
    return completed.stdout.strip()


def _same_or_descendant(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _inside_git_repository(path: Path) -> bool:
    probe = path if path.exists() else path.parent
    return _run(["git", "rev-parse", "--show-toplevel"], probe).returncode == 0


def validate_workspace_location(workspace: Path, legacy: Path) -> tuple[Path, Path]:
    """Validate that the workspace is separate and empty before cloning."""
    workspace = workspace.expanduser().resolve()
    legacy = legacy.expanduser().resolve()
    if not legacy.is_dir():
        raise ValueError(f"existing legacy directory does not exist: {legacy}")
    unsafe = (
        workspace == legacy
        or _same_or_descendant(workspace, legacy)
        or _same_or_descendant(legacy, workspace)
        or _inside_git_repository(workspace)
    )
    if unsafe:
        raise ValueError("Adoption workspace must be a separate directory. Example: --workspace ~/gene-set-adoptions/my_library")
    if workspace.exists() and any(workspace.iterdir()):
        raise ValueError(f"Adoption workspace must be empty: {workspace}")
    return workspace, legacy


def _fork_urls(github_user: str | None, dig_fork: str | None, wrapper_fork: str | None) -> tuple[str, str]:
    if github_user:
        dig_fork = dig_fork or f"https://github.com/{github_user}/dig-gene-set-extractors.git"
        wrapper_fork = wrapper_fork or f"https://github.com/{github_user}/geneset-extractor-dev.git"
    if not dig_fork or not wrapper_fork:
        raise ValueError("pass --github-user or both --dig-fork and --wrapper-fork")
    return dig_fork, wrapper_fork


def _clone_fork(url: str, destination: Path, upstream: str, base_branch: str, work_branch: str) -> None:
    completed = _run(["git", "clone", "--origin", "origin", url, str(destination)])
    if completed.returncode:
        raise ValueError(f"could not clone contributor fork {url}: {completed.stderr.strip()}")
    _git(destination, "remote", "add", "upstream", upstream)
    _git(destination, "fetch", "upstream", base_branch)
    _git(destination, "checkout", "-B", work_branch, f"upstream/{base_branch}")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _legacy_reference(legacy: Path, inventory: dict[str, Any]) -> dict[str, Any]:
    outputs = []
    for item in inventory.get("gene_set_outputs", []):
        if isinstance(item, dict) and item.get("path"):
            outputs.append({"path": str(legacy / str(item["path"])), "checksum": "sha256:" + str(item.get("sha256", "")), "comparison": "set_equivalent"})
    return {"schema_version": "1.0.0", "reference_outputs": outputs}


def create_workspace(
    *,
    existing: Path,
    workspace: Path,
    library_id: str,
    display_name: str | None,
    pattern: str,
    github_user: str | None,
    dig_fork: str | None,
    wrapper_fork: str | None,
    base_branch: str = DEFAULT_BASE_BRANCH,
) -> Path:
    workspace, legacy = validate_workspace_location(workspace, existing)
    dig_fork, wrapper_fork = _fork_urls(github_user, dig_fork, wrapper_fork)
    workspace.mkdir(parents=True, exist_ok=True)
    work_branch = f"adopt/{library_id}"
    try:
        _clone_fork(dig_fork, workspace / "dig-gene-set-extractors", CANONICAL_DIG, base_branch, work_branch)
        _clone_fork(wrapper_fork, workspace / "geneset-extractor-dev", CANONICAL_WRAPPER, base_branch, work_branch)
        inventory = inventory_legacy(legacy)
        adoption_dir = workspace / "adoption"
        _write_json(adoption_dir / "inventory.json", inventory)
        _write_json(adoption_dir / "dependency_map.json", {"schema_version": "1.0.0", "intermediates": [{"path": item["path"], "producer": "TODO"} for item in inventory["possible_intermediates"]]})
        (adoption_dir / "adoption_report.md").write_text(adoption_report(inventory), encoding="utf-8")
        reference = _legacy_reference(legacy, inventory)
        _write_json(adoption_dir / "legacy_reference.json", reference)
        library = workspace / "geneset-extractor-dev" / library_id
        scaffold(library, library_id, display_name or library_id, pattern)
        submission = library / "submission.yaml"
        payload = load(submission)
        payload["submission_origin"] = {"type": "adopted", "legacy_inventory": "../../adoption/inventory.json"}
        payload["adoption"] = {"reference_outputs": reference["reference_outputs"]}
        _write_json(submission, payload)
        manifest = {
            "schema_version": "1.0.0", "library_id": library_id,
            "workspace": {"root": str(workspace)},
            "legacy": {"source_path": str(legacy), "read_only": True, "inventory": "adoption/inventory.json", "reference": "adoption/legacy_reference.json"},
            "repositories": {
                "dig": {"path": "dig-gene-set-extractors", "origin": dig_fork, "upstream": CANONICAL_DIG, "base_branch": base_branch, "work_branch": work_branch},
                "wrapper": {"path": "geneset-extractor-dev", "origin": wrapper_fork, "upstream": CANONICAL_WRAPPER, "base_branch": base_branch, "work_branch": work_branch},
            },
            "submission": {"wrapper_library_path": f"geneset-extractor-dev/{library_id}"},
            "verification": {"last_result": None, "last_receipt": None, "workspace_digest": None},
        }
        _write_json(workspace / WORKSPACE_MANIFEST, manifest)
        (workspace / "AI_ADOPTION_PROMPT.md").write_text(_workspace_prompt(workspace, manifest, inventory), encoding="utf-8")
        (workspace / "reports").mkdir(); (workspace / "work").mkdir(); (workspace / "legacy").mkdir()
        return workspace
    except Exception:
        # The directory was required to be empty; leaving diagnostics is safer than deleting it.
        raise


def _workspace_prompt(workspace: Path, manifest: dict[str, Any], inventory: dict[str, Any]) -> str:
    return f"""# AI adoption instructions

You are operating inside an isolated adoption workspace: `{workspace}`.

You may modify only:
- `./dig-gene-set-extractors`
- `./geneset-extractor-dev`
- generated adoption/report files inside this workspace

The original legacy submission at `{manifest['legacy']['source_path']}` is **READ ONLY**. Do not modify files outside this workspace.

DIG branch: `{manifest['repositories']['dig']['work_branch']}`
Wrapper branch: `{manifest['repositories']['wrapper']['work_branch']}`
Baseline branch: `{manifest['repositories']['dig']['base_branch']}`

All substantive source-data processing, statistical analysis, normalization, differential testing, gene mapping, ranking, gene-set construction, and reusable converters belong in `dig-gene-set-extractors`. The wrapper repository may only configure, dispatch, execute, refresh metadata/provenance, and publish.

Reconstruct every dependency from declared source inputs to final outputs. Every intermediate must be declared or produced by committed code. Preserve thresholds, mappings, contrasts, normalization, ranking, and model definitions; stop for approval before scientifically meaningful changes. Add smoke fixtures and tests, regenerate gene sets, compare them with the legacy reference, and run `python3 -m submission_tools verify-adoption --workspace {workspace}`.

Inventory: `adoption/inventory.json` ({len(inventory.get('gene_set_outputs', []))} legacy GMT candidates)
"""


def load_workspace(workspace: Path) -> tuple[Path, dict[str, Any]]:
    root = workspace.expanduser().resolve()
    path = root / WORKSPACE_MANIFEST
    if not path.is_file():
        raise ValueError(f"workspace manifest does not exist: {path}")
    manifest = load(path)
    if not isinstance(manifest, dict) or str(manifest.get("workspace", {}).get("root", "")) != str(root):
        raise ValueError("workspace manifest does not match the requested workspace")
    return root, manifest


def _workspace_paths(root: Path, manifest: dict[str, Any]) -> tuple[Path, Path, Path, Path]:
    repos = manifest.get("repositories", {})
    dig = root / str(repos.get("dig", {}).get("path", ""))
    wrapper = root / str(repos.get("wrapper", {}).get("path", ""))
    library = root / str(manifest.get("submission", {}).get("wrapper_library_path", ""))
    legacy = Path(str(manifest.get("legacy", {}).get("source_path", "")))
    return dig, wrapper, library, legacy


def _repo_safety(repo: Path, declared: dict[str, Any], role: str) -> list[str]:
    problems: list[str] = []
    if not (repo / ".git").exists():
        return [f"{role} is not a Git repository: {repo}"]
    for remote in ("origin", "upstream"):
        try:
            actual = _git(repo, "remote", "get-url", remote)
        except ValueError as exc:
            problems.append(f"{role} missing {remote}: {exc}"); continue
        expected = str(declared.get(remote, ""))
        if actual != expected:
            problems.append(f"{role} {remote} does not match workspace manifest")
    try:
        branch = _git(repo, "branch", "--show-current")
        if branch != str(declared.get("work_branch", "")):
            problems.append(f"{role} must be on {declared.get('work_branch')}, found {branch or 'detached HEAD'}")
    except ValueError as exc:
        problems.append(f"{role} branch check failed: {exc}")
    return problems


def _legacy_changed(root: Path, manifest: dict[str, Any], legacy: Path) -> list[str]:
    inventory_path = root / str(manifest["legacy"]["inventory"])
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    changed = []
    for group in ("code_files", "data_files", "gene_set_outputs", "environment_files"):
        for item in inventory.get(group, []):
            path = legacy / str(item["path"])
            if not path.is_file() or _sha256(path) != item.get("sha256"):
                changed.append(str(item["path"]))
    return changed


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _workspace_digest(root: Path, manifest: dict[str, Any]) -> str:
    dig, wrapper, library, _legacy = _workspace_paths(root, manifest)
    values = []
    for repo in (dig, wrapper):
        values.append(_git(repo, "rev-parse", "HEAD")); values.append(_git(repo, "status", "--porcelain"))
    if library.exists():
        for path in sorted(library.rglob("*")):
            if path.is_file() and ".git" not in path.parts:
                values.append(str(path.relative_to(root)) + ":" + _sha256(path))
    return hashlib.sha256("\n".join(values).encode()).hexdigest()


def _run_wrapper_submission_tests(wrapper: Path) -> tuple[bool, str] | None:
    """Run the lightweight submission-tool suite when this branch provides it.

    The command is intentionally local and deterministic.  It does not run
    download scripts and it is skipped only for minimal test repositories that
    do not contain the submission-tool test module.
    """
    test_module = wrapper / "tests" / "test_submission_tools.py"
    if not test_module.is_file():
        return None
    env = {**os.environ, "PYTHONPATH": str(wrapper) + os.pathsep + os.environ.get("PYTHONPATH", "")}
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_submission_tools"], cwd=wrapper,
        text=True, capture_output=True, env=env, check=False,
    )
    return completed.returncode == 0, completed.stderr.strip() or completed.stdout.strip()


def verify_workspace(workspace: Path) -> tuple[bool, list[str]]:
    root, manifest = load_workspace(workspace)
    dig, wrapper, library, legacy = _workspace_paths(root, manifest)
    messages: list[str] = []
    repos = manifest["repositories"]
    messages.extend("ERROR: " + item for item in _repo_safety(dig, repos["dig"], "DIG"))
    messages.extend("ERROR: " + item for item in _repo_safety(wrapper, repos["wrapper"], "wrapper"))
    if not legacy.is_dir():
        messages.append(f"ERROR: legacy source is missing: {legacy}")
    else:
        changed = _legacy_changed(root, manifest, legacy)
        messages.extend(f"ERROR: Legacy source changed during adoption: {item}" for item in changed)
    if not library.is_dir():
        messages.append(f"ERROR: wrapper library is missing: {library}")
    if any(message.startswith("ERROR:") for message in messages):
        return False, messages
    static = validate_submission(library)
    messages.extend(f"{issue.level.upper()}: wrapper {issue.code}: {issue.message}" for issue in static.issues)
    wrapper_tests = _run_wrapper_submission_tests(wrapper)
    if wrapper_tests is not None:
        passed, output = wrapper_tests
        messages.append(("INFO" if passed else "ERROR") + ": wrapper submission-tool tests " + ("passed" if passed else "failed: " + output))
    dirty = bool(_git(dig, "status", "--porcelain"))
    coordinated = coordinated_validate(library, dig, smoke=True, development_dig_checkout=dirty)
    messages.extend(f"{issue.level.upper()}: DIG {issue.code}: {issue.message}" for issue in coordinated.issues)
    # A migrated library supplies the actual reproduction command.  It is only
    # executed by this explicit local command, never by CI automation.
    payload = load(library / "submission.yaml")
    smoke = str(payload["reproduction"]["smoke_test_command"]).split()
    reproduced = _run(smoke, library)
    if reproduced.returncode:
        messages.append("ERROR: smoke reproduction failed: " + (reproduced.stderr.strip() or reproduced.stdout.strip()))
    reference_path = root / str(manifest["legacy"]["reference"])
    references = json.loads(reference_path.read_text(encoding="utf-8")).get("reference_outputs", [])
    candidates = [p for p in library.rglob("*.gmt") if "adoption" not in p.parts]
    if references and candidates:
        comparison = str(references[0].get("comparison", "set_equivalent"))
        passed, rows = compare_gmt(Path(str(references[0]["path"])), candidates[0], comparison, root / "adoption/comparison_report.tsv")
        if not passed:
            messages.append(f"ERROR: legacy comparison failed ({sum(row['status'] != 'unchanged' for row in rows)} differing gene sets)")
    elif references:
        messages.append("ERROR: no regenerated GMT was found for legacy comparison")
    receipt = library / "run_receipt.json"
    ok = not any(message.startswith("ERROR:") for message in messages)
    write_receipt(library / "submission.yaml", dig, {"ok": ok, "messages": messages}, receipt, ["python3", "-m", "submission_tools", "verify-adoption", "--workspace", str(root)])
    manifest["verification"] = {"last_result": "PASS" if ok else "FAILED", "last_receipt": str(receipt.relative_to(root)), "workspace_digest": _workspace_digest(root, manifest), "completed_at": datetime.now(timezone.utc).isoformat()}
    _write_json(root / WORKSPACE_MANIFEST, manifest)
    return ok, messages


_FORBIDDEN_NAMES = re.compile(r"(?:^|[._-])(secret|credential|token|password|\.env)(?:$|[._-])", re.I)
_FORBIDDEN_SUFFIXES = {".gmt", ".h5", ".h5ad", ".rds", ".parquet", ".zip", ".tar", ".gz", ".bam", ".cram"}


def _changed_paths(repo: Path) -> list[Path]:
    status = _git(repo, "status", "--porcelain=v1")
    paths: list[Path] = []
    for line in status.splitlines():
        if len(line) >= 4:
            raw = line[3:]
            if " -> " in raw:
                raw = raw.split(" -> ", 1)[1]
            candidate = repo / raw.rstrip("/")
            # Porcelain reports an untracked directory as one entry. Expand it
            # before staging so a hidden secret or large source file cannot be
            # smuggled in by staging the directory as a whole.
            if candidate.is_dir():
                paths.extend(path for path in candidate.rglob("*") if path.is_file())
            else:
                paths.append(candidate)
    return paths


def safe_stage(repo: Path, allowed_roots: tuple[str, ...]) -> list[str]:
    staged: list[str] = []
    for path in _changed_paths(repo):
        rel = path.relative_to(repo)
        if not any(str(rel) == root or str(rel).startswith(root.rstrip("/") + "/") for root in allowed_roots):
            raise ValueError(f"refusing to stage unrelated file: {rel}")
        if _FORBIDDEN_NAMES.search(path.name) or path.suffix.lower() in _FORBIDDEN_SUFFIXES:
            raise ValueError(f"refusing to stage suspicious or source-data file: {rel}")
        if path.exists() and path.is_file() and path.stat().st_size > 5 * 1024 * 1024:
            raise ValueError(f"refusing to stage large file: {rel}")
        completed = _run(["git", "add", "--", str(rel)], repo)
        if completed.returncode:
            raise ValueError(completed.stderr.strip() or f"could not stage {rel}")
        staged.append(str(rel))
    return staged


def _commit_if_changed(repo: Path, message: str, roots: tuple[str, ...]) -> str | None:
    staged = safe_stage(repo, roots)
    if not staged:
        return None
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _is_fork_origin(url: str, upstream: str) -> bool:
    def normalize(value: str) -> str:
        return value.rstrip("/").removesuffix(".git").replace("git@github.com:", "https://github.com/")
    return normalize(url) != normalize(upstream)


def _github_slug(url: str) -> str | None:
    normalized = url.rstrip("/").removesuffix(".git").replace("git@github.com:", "https://github.com/")
    match = re.fullmatch(r"https://github\.com/([^/]+/[^/]+)", normalized)
    return match.group(1) if match else None


def _github_owner(url: str) -> str | None:
    slug = _github_slug(url)
    return slug.split("/", 1)[0] if slug else None


def _open_draft_pr(repo: Path, declared: dict[str, Any], title: str, body: str) -> tuple[str | None, str]:
    """Open a draft PR when GitHub CLI is available; never make this mandatory."""
    gh = shutil.which("gh")
    if not gh:
        return None, f"gh is unavailable; create a draft PR manually from {declared['work_branch']}"
    authenticated = _run([gh, "auth", "status"], repo)
    if authenticated.returncode:
        return None, f"gh is not authenticated; create a draft PR manually from {declared['work_branch']}"
    upstream_slug = _github_slug(str(declared["upstream"]))
    owner = _github_owner(str(declared["origin"]))
    if not upstream_slug or not owner:
        return None, f"non-GitHub remotes; create a draft PR manually from {declared['work_branch']}"
    command = [gh, "pr", "create", "--repo", upstream_slug, "--base", str(declared["base_branch"]), "--head", f"{owner}:{declared['work_branch']}", "--draft", "--title", title, "--body", body]
    completed = _run(command, repo)
    if completed.returncode:
        return None, "gh could not create a draft PR: " + (completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout.strip().splitlines()[-1], "draft PR opened"


def submit_workspace(workspace: Path, *, yes: bool = False, allow_upstream_origin: bool = False) -> tuple[bool, list[str]]:
    root, manifest = load_workspace(workspace)
    dig, wrapper, library, legacy = _workspace_paths(root, manifest)
    verification = manifest.get("verification", {})
    if verification.get("last_result") != "PASS" or verification.get("workspace_digest") != _workspace_digest(root, manifest):
        return False, ["ERROR: verification is missing or stale; run verify-adoption again"]
    if _legacy_changed(root, manifest, legacy):
        return False, ["ERROR: legacy source changed during adoption"]
    messages: list[str] = []
    dig_changed = bool(_changed_paths(dig)); wrapper_changed = bool(_changed_paths(wrapper))
    if not dig_changed and not wrapper_changed:
        return False, ["ERROR: no changes are available to submit"]
    if not yes:
        return False, [
            "Changes to submit:",
            f"  dig-gene-set-extractors: {'changed' if dig_changed else 'unchanged'}",
            f"  geneset-extractor-dev: {'changed' if wrapper_changed else 'unchanged'}",
            "Re-run with --yes to commit and push only to contributor forks.",
        ]
    for repo, declared in ((dig, manifest["repositories"]["dig"]), (wrapper, manifest["repositories"]["wrapper"])):
        origin = _git(repo, "remote", "get-url", "origin")
        if not allow_upstream_origin and not _is_fork_origin(origin, str(declared["upstream"])):
            return False, [f"ERROR: refusing to push {repo.name}; origin is canonical upstream"]
    dig_sha = _commit_if_changed(dig, f"Add extractor support for {manifest['library_id']}", ("src", "tests", "docs", "pyproject.toml", "README.md")) if dig_changed else None
    if dig_sha:
        submission = library / "submission.yaml"; payload = load(submission); payload["dig"]["commit"] = dig_sha
        _write_json(submission, payload)
    if not dig_sha:
        submission = library / "submission.yaml"
        payload = load(submission)
        payload["paired_pull_requests"]["dig_gene_set_extractors"] = "N/A"
        _write_json(submission, payload)
    wrapper_sha = _commit_if_changed(wrapper, f"Add {manifest['library_id']} gene-set library", (manifest["library_id"], "docs", "submission_tools", "tests", "config", "run")) if (wrapper_changed or dig_sha) else None
    # Confirm the wrapper now points at the exact DIG commit before any push.
    if dig_sha:
        result = coordinated_validate(library, dig, development_dig_checkout=False)
        if not result.ok:
            return False, ["ERROR: coordinated validation failed after DIG pinning", *[issue.message for issue in result.issues]]
    for repo, declared in ((dig, manifest["repositories"]["dig"]), (wrapper, manifest["repositories"]["wrapper"])):
        if (repo == dig and dig_sha) or (repo == wrapper and wrapper_sha):
            completed = _run(["git", "push", "-u", "origin", str(declared["work_branch"])], repo)
            if completed.returncode:
                return False, [f"ERROR: push to contributor fork failed for {repo.name}: {completed.stderr.strip()}"]
    dig_pr: str | None = None
    if dig_sha:
        dig_pr, message = _open_draft_pr(
            dig, manifest["repositories"]["dig"], f"Add extractor support for {manifest['library_id']}",
            f"Adopted legacy library: {manifest['library_id']}\n\nRun verify-adoption before review.",
        )
        messages.append("DIG: " + message)
        if dig_pr:
            submission = library / "submission.yaml"; payload = load(submission)
            payload["paired_pull_requests"]["dig_gene_set_extractors"] = dig_pr
            _write_json(submission, payload)
            _commit_if_changed(wrapper, "Record paired pull request URLs", (manifest["library_id"],))
            completed = _run(["git", "push", "origin", str(manifest["repositories"]["wrapper"]["work_branch"])], wrapper)
            if completed.returncode:
                return False, ["ERROR: could not push paired DIG PR metadata: " + completed.stderr.strip()]
    wrapper_pr, message = _open_draft_pr(
        wrapper, manifest["repositories"]["wrapper"], f"Add {manifest['library_id']} gene-set library",
        f"Adopted legacy library: {manifest['library_id']}\n\nPinned DIG commit: {dig_sha or load(library / 'submission.yaml')['dig']['commit']}",
    )
    messages.append("Wrapper: " + message)
    if wrapper_pr:
        submission = library / "submission.yaml"; payload = load(submission)
        payload["paired_pull_requests"]["geneset_extractor_dev"] = wrapper_pr
        _write_json(submission, payload)
        _commit_if_changed(wrapper, "Record paired pull request URLs", (manifest["library_id"],))
        completed = _run(["git", "push", "origin", str(manifest["repositories"]["wrapper"]["work_branch"])], wrapper)
        if completed.returncode:
            return False, ["ERROR: could not push paired wrapper PR metadata: " + completed.stderr.strip()]
    messages.append("Branches pushed only to contributor forks; no pull request was merged.")
    return True, messages
