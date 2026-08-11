from __future__ import annotations

import json
import inspect
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from submission_tools.adoption import adopt, adoption_status, inventory_legacy
from submission_tools import adoption_workspace
from submission_tools.adoption_workspace import DEFAULT_BASE_BRANCH, _is_fork_origin, _open_draft_pr, _workspace_digest, _write_json, create_workspace, load_workspace, safe_stage, submit_workspace, validate_workspace_location, verify_workspace
from submission_tools.legacy_compare import compare_gmt
from submission_tools.validator import validate_submission


class LegacyAdoptionTest(unittest.TestCase):
    def legacy_library(self, root: Path) -> Path:
        legacy = root / "legacy"
        legacy.mkdir()
        (legacy / "prepare.py").write_text("# /home/example/input\nprint('manually inspect data')\n", encoding="utf-8")
        (legacy / "run.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        (legacy / "counts.tsv").write_text("gene\tcount\nA\t1\n", encoding="utf-8")
        (legacy / "environment.yml").write_text("name: legacy\n", encoding="utf-8")
        (legacy / "old.gmt").write_text("set_a\tna\tA\tB\n", encoding="utf-8")
        return legacy

    def test_inventory_detects_common_legacy_materials(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            inventory = inventory_legacy(self.legacy_library(Path(temp)))
        self.assertEqual(len(inventory["code_files"]), 2)
        self.assertEqual(len(inventory["data_files"]), 1)
        self.assertEqual(inventory["gene_set_outputs"][0]["n_gene_sets"], 1)
        self.assertTrue(inventory["environment_files"])
        self.assertTrue(inventory["nonportable_findings"])
        self.assertTrue(inventory["manual_step_findings"])

    def test_adopt_does_not_modify_legacy_and_creates_valid_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            legacy = self.legacy_library(root)
            before = (legacy / "old.gmt").read_bytes()
            adopted = adopt(legacy, root / "Adopted", "Adopted")
            self.assertEqual((legacy / "old.gmt").read_bytes(), before)
            self.assertTrue(validate_submission(adopted).ok)
            payload = json.loads((adopted / "submission.yaml").read_text(encoding="utf-8"))
            self.assertEqual(payload["submission_origin"]["type"], "adopted")
            for name in ("inventory.json", "dependency_map.json", "adoption_report.md", "AI_ADOPTION_PROMPT.md"):
                self.assertTrue((adopted / "adoption" / name).is_file())

    def test_compare_modes_and_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old, new = root / "old.gmt", root / "new.gmt"
            old.write_text("set\tna\tA\tB\n", encoding="utf-8")
            new.write_text("set\tna\tB\tA\n", encoding="utf-8")
            self.assertFalse(compare_gmt(old, new, "exact")[0])
            self.assertTrue(compare_gmt(old, new, "set_equivalent")[0])
            adopted = adopt(self.legacy_library(root), root / "Adopted", "Adopted")
            completed = subprocess.run([sys.executable, "-m", "submission_tools", "compare-legacy", "--legacy", str(old), "--new", str(new), "--mode", "report_only"], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            states = dict((name, ok) for name, ok, _ in adoption_status(adopted))
            self.assertTrue(states["INVENTORIED"])
            self.assertTrue(states["NEW_FORMAT_VALID"])
            self.assertFalse(states["READY"])

    def test_library_comparison_writes_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            adopted = adopt(self.legacy_library(root), root / "Adopted", "Adopted")
            generated = adopted / "outputs/old.gmt"
            generated.parent.mkdir()
            generated.write_text("set_a\tna\tB\tA\n", encoding="utf-8")
            completed = subprocess.run([sys.executable, "-m", "submission_tools", "compare-legacy", "--library", str(adopted)], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((adopted / "adoption/comparison_report.tsv").exists())
            self.assertTrue((adopted / "adoption/comparison_summary.md").exists())

    def _git(self, root: Path, *args: str) -> None:
        completed = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def _remote(self, root: Path, name: str, branch: str = "main") -> Path:
        source = root / (name + "-source")
        source.mkdir()
        self._git(source, "init", "-b", branch)
        self._git(source, "config", "user.email", "test@example.invalid")
        self._git(source, "config", "user.name", "Test")
        (source / "README.md").write_text("fixture\n", encoding="utf-8")
        self._git(source, "add", "README.md")
        self._git(source, "commit", "-m", "baseline")
        remote = root / (name + ".git")
        completed = subprocess.run(["git", "clone", "--bare", str(source), str(remote)], text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return remote

    def test_isolated_workspace_uses_fresh_local_forks_and_preserves_legacy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            legacy = self.legacy_library(root)
            dig_upstream, dig = self._remote(root, "dig-upstream"), self._remote(root, "dig-fork")
            wrapper_upstream, wrapper = self._remote(root, "wrapper-upstream"), self._remote(root, "wrapper-fork")
            old_constants = adoption_workspace.CANONICAL_DIG, adoption_workspace.CANONICAL_WRAPPER
            adoption_workspace.CANONICAL_DIG = str(dig_upstream)
            adoption_workspace.CANONICAL_WRAPPER = str(wrapper_upstream)
            try:
                workspace = create_workspace(
                    existing=legacy, workspace=root / "isolated", library_id="Adopted", display_name=None,
                    pattern="generic", github_user=None, dig_fork=str(dig), wrapper_fork=str(wrapper),
                )
            finally:
                adoption_workspace.CANONICAL_DIG, adoption_workspace.CANONICAL_WRAPPER = old_constants
            loaded_root, manifest = load_workspace(workspace)
            self.assertEqual(loaded_root, workspace.resolve())
            self.assertEqual(manifest["repositories"]["dig"]["base_branch"], "main")
            self.assertEqual(manifest["repositories"]["wrapper"]["base_branch"], "main")
            self.assertEqual(manifest["repositories"]["dig"]["work_branch"], "adopt/Adopted")
            self.assertEqual(manifest["repositories"]["dig"]["origin"], str(dig))
            self.assertEqual(manifest["repositories"]["dig"]["upstream"], str(dig_upstream))
            self.assertEqual(manifest["repositories"]["wrapper"]["origin"], str(wrapper))
            self.assertEqual(manifest["repositories"]["wrapper"]["upstream"], str(wrapper_upstream))
            self.assertFalse(manifest["workspace"]["upstream_origin_mode"])
            self.assertTrue((workspace / "adoption/legacy_reference.json").exists())
            self.assertTrue((workspace / "AI_ADOPTION_PROMPT.md").exists())
            self.assertIn("Baseline branch: `main`", (workspace / "AI_ADOPTION_PROMPT.md").read_text(encoding="utf-8"))
            self.assertEqual((legacy / "old.gmt").read_text(encoding="utf-8"), "set_a\tna\tA\tB\n")
            self.assertTrue((workspace / "geneset-extractor-dev/Adopted/submission.yaml").is_file())

    def test_default_branch_is_main_and_submit_never_pushes_upstream(self) -> None:
        self.assertEqual(DEFAULT_BASE_BRANCH, "main")
        source = inspect.getsource(adoption_workspace.submit_workspace)
        self.assertIn('["git", "push", "-u", "origin"', source)
        self.assertNotIn('["git", "push", "upstream"', source)

    def test_workspace_safety_and_legacy_change_detection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            legacy = self.legacy_library(root)
            with self.assertRaises(ValueError):
                validate_workspace_location(legacy / "nested", legacy)
            workspace = root / "workspace"; workspace.mkdir()
            (workspace / "unrelated").write_text("x", encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_workspace_location(workspace, legacy)

    def test_canonical_origins_require_recorded_maintainer_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            legacy = self.legacy_library(root)
            dig, wrapper = self._remote(root, "dig"), self._remote(root, "wrapper")
            old_constants = adoption_workspace.CANONICAL_DIG, adoption_workspace.CANONICAL_WRAPPER
            adoption_workspace.CANONICAL_DIG = str(dig); adoption_workspace.CANONICAL_WRAPPER = str(wrapper)
            try:
                with self.assertRaisesRegex(ValueError, "allow-upstream-origin"):
                    create_workspace(existing=legacy, workspace=root / "rejected", library_id="Adopted", display_name=None, pattern="generic", github_user=None, dig_fork=str(dig), wrapper_fork=str(wrapper))
                workspace = create_workspace(existing=legacy, workspace=root / "accepted", library_id="Adopted", display_name=None, pattern="generic", github_user=None, dig_fork=str(dig), wrapper_fork=str(wrapper), allow_upstream_origin=True)
            finally:
                adoption_workspace.CANONICAL_DIG, adoption_workspace.CANONICAL_WRAPPER = old_constants
            _root, manifest = load_workspace(workspace)
            self.assertTrue(manifest["workspace"]["upstream_origin_mode"])
            self.assertEqual(manifest["repositories"]["dig"]["work_branch"], "adopt/Adopted")
            verified, messages = verify_workspace(workspace)
            self.assertFalse(verified)  # incomplete scaffold, not remote safety
            self.assertFalse(any("without the recorded" in message for message in messages))
            manifest["workspace"]["upstream_origin_mode"] = False
            _write_json(workspace / ".adoption-workspace.yaml", manifest)
            verified, messages = verify_workspace(workspace)
            self.assertFalse(verified)
            self.assertTrue(any("without the recorded" in message for message in messages))
            manifest["workspace"]["upstream_origin_mode"] = True
            manifest["verification"] = {"last_result": "PASS", "last_receipt": None, "workspace_digest": _workspace_digest(workspace, manifest)}
            _write_json(workspace / ".adoption-workspace.yaml", manifest)
            submitted, submission_messages = submit_workspace(workspace, yes=True)
            self.assertFalse(submitted)
            self.assertTrue(any("origin is canonical upstream" in message for message in submission_messages))

    def test_verify_and_submit_fail_safely_on_incomplete_or_stale_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            legacy = self.legacy_library(root)
            dig, wrapper = self._remote(root, "dig"), self._remote(root, "wrapper")
            old_constants = adoption_workspace.CANONICAL_DIG, adoption_workspace.CANONICAL_WRAPPER
            adoption_workspace.CANONICAL_DIG = str(dig); adoption_workspace.CANONICAL_WRAPPER = str(wrapper)
            try:
                workspace = create_workspace(existing=legacy, workspace=root / "isolated", library_id="Adopted", display_name=None, pattern="generic", github_user=None, dig_fork=str(dig), wrapper_fork=str(wrapper), allow_upstream_origin=True)
                ok, messages = verify_workspace(workspace)
                self.assertFalse(ok)  # scaffold intentionally has no usable DIG identifier yet
                self.assertTrue(any("DIG" in message or "smoke" in message.lower() for message in messages))
                (legacy / "old.gmt").write_text("set_a\tna\tchanged\n", encoding="utf-8")
                ok, messages = verify_workspace(workspace)
                self.assertFalse(ok)
                self.assertTrue(any("Legacy source changed" in message for message in messages))
                submitted, submission_messages = submit_workspace(workspace, yes=True)
                self.assertFalse(submitted)
                self.assertTrue(any("stale" in message or "missing" in message for message in submission_messages))
            finally:
                adoption_workspace.CANONICAL_DIG, adoption_workspace.CANONICAL_WRAPPER = old_constants

    def test_base_branch_override_is_recorded_and_used_for_draft_prs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            legacy = self.legacy_library(root)
            dig, wrapper = self._remote(root, "dig", "release-branch"), self._remote(root, "wrapper", "release-branch")
            old_constants = adoption_workspace.CANONICAL_DIG, adoption_workspace.CANONICAL_WRAPPER
            adoption_workspace.CANONICAL_DIG = str(dig); adoption_workspace.CANONICAL_WRAPPER = str(wrapper)
            try:
                workspace = create_workspace(existing=legacy, workspace=root / "isolated", library_id="Adopted", display_name=None, pattern="generic", github_user=None, dig_fork=str(dig), wrapper_fork=str(wrapper), base_branch="release-branch", allow_upstream_origin=True)
            finally:
                adoption_workspace.CANONICAL_DIG, adoption_workspace.CANONICAL_WRAPPER = old_constants
            _root, manifest = load_workspace(workspace)
            self.assertEqual(manifest["repositories"]["dig"]["base_branch"], "release-branch")
        commands: list[list[str]] = []
        def fake_run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
            commands.append(args)
            return subprocess.CompletedProcess(args, 0, "https://github.com/broadinstitute/geneset-extractor-dev/pull/1\n", "")
        declared = {"origin": "https://github.com/example/geneset-extractor-dev.git", "upstream": "https://github.com/broadinstitute/geneset-extractor-dev.git", "base_branch": "main", "work_branch": "adopt/Adopted"}
        with patch.object(adoption_workspace.shutil, "which", return_value="gh"), patch.object(adoption_workspace, "_run", side_effect=fake_run):
            url, _message = _open_draft_pr(Path("."), declared, "title", "body")
        self.assertEqual(url, "https://github.com/broadinstitute/geneset-extractor-dev/pull/1")
        pr_command = commands[-1]
        self.assertEqual(pr_command[pr_command.index("--base") + 1], "main")
        same_repo = {"origin": "https://github.com/broadinstitute/geneset-extractor-dev.git", "upstream": "https://github.com/broadinstitute/geneset-extractor-dev.git", "base_branch": "main", "work_branch": "adopt/Adopted"}
        commands.clear()
        with patch.object(adoption_workspace.shutil, "which", return_value="gh"), patch.object(adoption_workspace, "_run", side_effect=fake_run):
            _open_draft_pr(Path("."), same_repo, "title", "body")
        same_repo_command = commands[-1]
        self.assertEqual(same_repo_command[same_repo_command.index("--head") + 1], "adopt/Adopted")

    def test_safe_staging_rejects_secrets_and_canonical_origins(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"; repo.mkdir()
            self._git(repo, "init")
            self._git(repo, "config", "user.email", "test@example.invalid")
            self._git(repo, "config", "user.name", "Test")
            (repo / "src").mkdir(); (repo / "src" / "ok.py").write_text("x = 1\n", encoding="utf-8")
            self.assertEqual(safe_stage(repo, ("src",)), ["src/ok.py"])
            self._git(repo, "reset")
            (repo / "src" / ".env").write_text("TOKEN=x\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                safe_stage(repo, ("src",))
            self.assertFalse(_is_fork_origin("https://github.com/flannick/dig-gene-set-extractors.git", "https://github.com/flannick/dig-gene-set-extractors.git"))
            self.assertTrue(_is_fork_origin("https://github.com/example/dig-gene-set-extractors.git", "https://github.com/flannick/dig-gene-set-extractors.git"))


if __name__ == "__main__":
    unittest.main()
