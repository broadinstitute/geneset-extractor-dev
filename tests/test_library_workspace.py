from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from submission_tools import library_workspace
from submission_tools import adoption_workspace as shared


class NewLibraryWorkspaceTest(unittest.TestCase):
    def git(self, root: Path, *args: str) -> str:
        completed = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return completed.stdout.strip()

    def identity(self, repo: Path) -> None:
        self.git(repo, "config", "user.name", "Gene Set Extractor Tests")
        self.git(repo, "config", "user.email", "geneset-extractor-tests@example.invalid")

    def remote(self, root: Path, name: str, *, tools: bool = False, dig: bool = False) -> Path:
        source = root / f"{name}-source"
        source.mkdir()
        self.git(source, "init", "-b", "main")
        self.identity(source)
        (source / "README.md").write_text("fixture\n", encoding="utf-8")
        (source / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        if tools:
            shutil.copytree(Path(__file__).resolve().parents[1] / "submission_tools", source / "submission_tools", ignore=shutil.ignore_patterns("__pycache__"))
        if dig:
            package = source / "src" / "geneset_extractors"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text('__version__ = "test"\n', encoding="utf-8")
            (package / "cli.py").write_text("import sys\nraise SystemExit(0 if sys.argv[1:] == ['submission', 'validate', 'TODO'] else 1)\n", encoding="utf-8")
        self.git(source, "add", ".")
        self.git(source, "commit", "-m", "baseline")
        remote = root / f"{name}.git"
        completed = subprocess.run(["git", "clone", "--bare", str(source), str(remote)], text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return remote

    def workspace(self, root: Path, *, pattern: str = "generic") -> tuple[Path, Path, Path, Path]:
        inputs = root / "inputs"
        inputs.mkdir()
        (inputs / "counts.tsv").write_text("gene\tvalue\nA\t1\n", encoding="utf-8")
        dig_upstream = self.remote(root, "dig-upstream", dig=True)
        dig_fork = self.remote(root, "dig-fork", dig=True)
        wrapper_upstream = self.remote(root, "wrapper-upstream", tools=True)
        wrapper_fork = self.remote(root, "wrapper-fork", tools=True)
        old_dig, old_wrapper = shared.CANONICAL_DIG, shared.CANONICAL_WRAPPER
        shared.CANONICAL_DIG, shared.CANONICAL_WRAPPER = str(dig_upstream), str(wrapper_upstream)
        try:
            workspace = library_workspace.create_library_workspace(
                inputs=inputs, workspace=root / "workspace", library_id="NewLibrary", display_name="New Library",
                pattern=pattern, github_user=None, dig_fork=str(dig_fork), wrapper_fork=str(wrapper_fork),
            )
        finally:
            shared.CANONICAL_DIG, shared.CANONICAL_WRAPPER = old_dig, old_wrapper
        self.identity(workspace / "dig-gene-set-extractors")
        self.identity(workspace / "geneset-extractor-dev")
        return workspace, inputs, dig_fork, wrapper_fork

    def test_create_library_records_read_only_inputs_and_generates_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace, inputs, _dig_fork, _wrapper_fork = self.workspace(Path(temp), pattern="lincs_l1000")
            root, manifest = library_workspace.load_library_workspace(workspace)
            inventory = json.loads((workspace / "inputs/input_inventory.json").read_text())
            prompt = (workspace / "AI_NEW_LIBRARY_PROMPT.md").read_text(encoding="utf-8")
            self.assertEqual(root, workspace.resolve())
            self.assertEqual(manifest["workflow_type"], "new_library")
            self.assertEqual(manifest["repositories"]["dig"]["work_branch"], "submit/NewLibrary")
            self.assertTrue(manifest["source_inputs"]["read_only"])
            self.assertEqual(inventory["files"][0]["path"], str(inputs / "counts.tsv"))
            self.assertTrue((workspace / "verify-library").exists())
            self.assertTrue((workspace / "submit-library").exists())
            self.assertIn("AI_NEW_LIBRARY_PLAN.md", prompt)
            self.assertIn("Source inputs listed", prompt)

    def test_verify_library_succeeds_for_draft_scaffold_and_detects_changed_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace, inputs, _dig_fork, _wrapper_fork = self.workspace(Path(temp))
            expected = workspace / "geneset-extractor-dev/submission_tools"
            with patch.object(library_workspace, "_tooling", return_value=(True, expected, expected, "test")):
                ok, messages = library_workspace.verify_library_workspace(workspace)
                self.assertTrue(ok, messages)
                receipt = json.loads((workspace / "geneset-extractor-dev/NewLibrary/run_receipt.json").read_text())
                self.assertEqual(receipt["workspace"]["workflow_type"], "new_library")
                self.assertEqual(receipt["workspace"]["tooling_commit"], "test")
                (inputs / "counts.tsv").write_text("gene\tvalue\nA\t2\n", encoding="utf-8")
                ok, messages = library_workspace.verify_library_workspace(workspace)
        self.assertFalse(ok)
        self.assertTrue(any("source input changed" in message for message in messages))

    def test_submit_requires_fresh_verification_and_never_pushes_upstream(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace, _inputs, _dig_fork, wrapper_fork = self.workspace(Path(temp))
            expected = workspace / "geneset-extractor-dev/submission_tools"
            with patch.object(library_workspace, "_tooling", return_value=(True, expected, expected, "test")):
                ok, messages = library_workspace.submit_library_workspace(workspace, yes=True)
                self.assertFalse(ok)
                self.assertIn("verification is missing or stale", messages[0])
                ok, messages = library_workspace.verify_library_workspace(workspace)
                self.assertTrue(ok, messages)
                library = workspace / "geneset-extractor-dev/NewLibrary"
                (library / "README.md").write_text("# New Library\n", encoding="utf-8")
                ok, messages = library_workspace.submit_library_workspace(workspace, yes=False)
                self.assertFalse(ok)
                self.assertIn("stale", messages[0])
                ok, _messages = library_workspace.verify_library_workspace(workspace)
                self.assertTrue(ok)
                with patch.object(shared, "_open_draft_pr", return_value=(None, "draft PR skipped")):
                    ok, messages = library_workspace.submit_library_workspace(workspace, yes=True)
            self.assertTrue(ok, messages)
            pushed = subprocess.run(["git", "--git-dir", str(wrapper_fork), "rev-parse", "refs/heads/submit/NewLibrary"], capture_output=True, text=True)
            self.assertEqual(pushed.returncode, 0, pushed.stderr)

    def test_remote_branch_collision_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace, _inputs, dig_fork, _wrapper_fork = self.workspace(root)
            self.assertTrue(workspace.exists())
            self.git(workspace / "dig-gene-set-extractors", "push", "origin", "submit/NewLibrary")
            inputs = root / "new-inputs"; inputs.mkdir()
            (inputs / "x.tsv").write_text("x\n", encoding="utf-8")
            old_dig, old_wrapper = shared.CANONICAL_DIG, shared.CANONICAL_WRAPPER
            shared.CANONICAL_DIG = str(dig_fork); shared.CANONICAL_WRAPPER = str(dig_fork)
            try:
                with self.assertRaisesRegex(ValueError, "remote branch submit/NewLibrary already exists"):
                    library_workspace.create_library_workspace(
                        inputs=inputs, workspace=root / "second", library_id="NewLibrary", display_name=None,
                        pattern="generic", github_user=None, dig_fork=str(dig_fork), wrapper_fork=str(dig_fork), allow_upstream_origin=True,
                    )
            finally:
                shared.CANONICAL_DIG, shared.CANONICAL_WRAPPER = old_dig, old_wrapper


if __name__ == "__main__":
    unittest.main()
