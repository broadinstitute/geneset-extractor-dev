from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from submission_tools.discovery import discover_submissions
from submission_tools.coordinated import coordinated_validate, inspect_dig_checkout
from submission_tools.receipt import validate_receipt, write_receipt
from submission_tools.scaffold import scaffold
from submission_tools.validator import validate_submission


class SubmissionToolsTest(unittest.TestCase):
    def scaffold(self, pattern: str = "generic") -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name) / "LibraryX"
        scaffold(root, "LibraryX", "Library X", pattern)
        return root

    def payload(self, root: Path) -> dict:
        return json.loads((root / "submission.yaml").read_text())

    def write_payload(self, root: Path, payload: dict) -> None:
        (root / "submission.yaml").write_text(json.dumps(payload, indent=2) + "\n")

    def synthetic_example(self) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        source = Path(__file__).resolve().parents[1] / "examples" / "synthetic_submission"
        destination = Path(temp.name) / "synthetic_submission"
        shutil.copytree(source, destination)
        for script in destination.rglob("*.sh"):
            script.chmod(script.stat().st_mode | 0o111)
        return destination

    def fake_dig_repo(self) -> tuple[Path, str]:
        """Create the smallest local DIG checkout needed by coordination tests."""
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        repo = Path(temp.name) / "dig-gene-set-extractors"
        package = repo / "src" / "geneset_extractors"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text('__version__ = "test"\n', encoding="utf-8")
        (package / "cli.py").write_text(
            "import sys\n"
            "if sys.argv[1:] == ['submission', 'validate', 'rna_deg']:\n"
            "    raise SystemExit(0)\n"
            "print('unknown workflow', file=sys.stderr)\n"
            "raise SystemExit(1)\n",
            encoding="utf-8",
        )
        (repo / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.org"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "fake DIG"], cwd=repo, check=True, capture_output=True)
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
        return repo, commit

    def test_valid_minimal_submission(self) -> None:
        self.assertTrue(validate_submission(self.scaffold()).ok)

    def test_all_patterns_scaffold_and_validate(self) -> None:
        for pattern in ("gtex", "motrpac", "hubmap", "lincs_l1000", "generic"):
            with self.subTest(pattern=pattern):
                root = self.scaffold(pattern)
                self.assertTrue((root / "reproduction/reproduce.sh").exists())
                self.assertTrue(validate_submission(root).ok)

    def test_missing_required_file(self) -> None:
        root = self.scaffold()
        (root / "config/model_list.tsv").unlink()
        self.assertFalse(validate_submission(root).ok)

    def test_malformed_yaml(self) -> None:
        root = self.scaffold()
        (root / "submission.yaml").write_text("library: [bad\n")
        self.assertFalse(validate_submission(root).ok)

    def test_bad_headers_and_duplicate_ids(self) -> None:
        root = self.scaffold()
        (root / "reproduction/input_manifest.tsv").write_text("input_id\nA\nA\n")
        self.assertFalse(validate_submission(root).ok)

    def test_absolute_path_is_rejected(self) -> None:
        root = self.scaffold()
        payload = self.payload(root)
        payload["configs"]["model_config"] = "/tmp/model.tsv"
        self.write_payload(root, payload)
        self.assertFalse(validate_submission(root).ok)

    def test_missing_script_is_rejected(self) -> None:
        root = self.scaffold()
        (root / "reproduction/download_inputs.sh").unlink()
        self.assertFalse(validate_submission(root).ok)

    def test_wrapper_analytical_import_is_rejected(self) -> None:
        root = self.scaffold()
        (root / "src/analysis.py").write_text("import pandas as pd\n")
        self.assertFalse(validate_submission(root).ok)

    def test_home_directory_provenance_mirror_warns_for_draft_and_fails_for_ready(self) -> None:
        root = self.scaffold()
        (root / "src/dispatch.py").write_text(
            'command = ["--provenance_mirror_local_prefix", str(Path.home())]\n'
        )
        draft = validate_submission(root)
        self.assertTrue(draft.ok)
        self.assertTrue(any(issue.code == "unsafe_provenance_mirror" and issue.level == "warning" for issue in draft.issues))
        payload = self.payload(root)
        payload["submission_status"] = "ready"
        payload["dig"]["commit"] = "a" * 40
        self.write_payload(root, payload)
        ready = validate_submission(root)
        self.assertFalse(ready.ok)
        self.assertTrue(any(issue.code == "unsafe_provenance_mirror" and issue.level == "error" for issue in ready.issues))

    def test_scaffold_creates_provenance_overlay_template(self) -> None:
        root = self.scaffold()
        overlay = json.loads((root / "config/provenance_overlay.json").read_text(encoding="utf-8"))
        self.assertIn("role:example_input", overlay["inputs"])

    def test_provenance_artifact_roles_must_be_non_empty_strings(self) -> None:
        root = self.scaffold()
        payload = self.payload(root)
        payload["provenance"]["contracts"][0]["artifact_roles"] = [""]
        self.write_payload(root, payload)
        result = validate_submission(root)
        self.assertFalse(result.ok)
        self.assertTrue(any(issue.code == "provenance_contract" for issue in result.issues))

    def test_allowlisted_deviation_warns_not_fails(self) -> None:
        root = self.scaffold()
        (root / "src/analysis.py").write_text("import pandas as pd\n")
        payload = self.payload(root)
        payload["deviations"]["allow_wrapper_findings"] = ["analytical_import"]
        self.write_payload(root, payload)
        result = validate_submission(root)
        self.assertTrue(result.ok)
        self.assertTrue(any(item.code == "allowlisted_analytical_import" for item in result.issues))

    def test_legacy_directory_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = validate_submission(Path(temp))
        self.assertTrue(result.ok)
        self.assertTrue(any(item.code == "legacy_ignored" for item in result.issues))

    def test_existing_gtex_legacy_library_is_ignored(self) -> None:
        legacy_gtex = Path(__file__).resolve().parents[1] / "GTEx"
        result = validate_submission(legacy_gtex)
        self.assertTrue(result.ok)
        self.assertTrue(any(item.code == "legacy_ignored" for item in result.issues))

    def test_discovery_uses_submission_yaml_and_changed_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            new_root = repo / "NewLibrary"
            scaffold(new_root, "NewLibrary", "New Library", "generic")
            legacy = repo / "GTEx"
            legacy.mkdir()
            self.assertEqual(discover_submissions(repo), [new_root])
            self.assertEqual(discover_submissions(repo, ["GTEx/src/legacy.py"]), [])
            self.assertEqual(discover_submissions(repo, ["NewLibrary/config/model_list.tsv"]), [new_root])

    def test_synthetic_example_validates_and_smoke_runs(self) -> None:
        root = self.synthetic_example()
        self.assertTrue(validate_submission(root).ok)
        completed = subprocess.run(["bash", "reproduction/reproduce.sh", "--smoke"], cwd=root, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("SIMULATED DIG ENTRYPOINT", completed.stdout)

    def test_synthetic_example_rejects_undeclared_input(self) -> None:
        root = self.synthetic_example()
        (root / "tests/fixtures/undeclared.tsv").write_text("x\n1\n")
        result = validate_submission(root)
        self.assertFalse(result.ok)
        self.assertTrue(any(item.code == "undeclared_input" for item in result.issues))

    def test_synthetic_example_rejects_wrapper_analysis(self) -> None:
        root = self.synthetic_example()
        (root / "src/simulate_dig_entrypoint.py").write_text("import numpy\n")
        result = validate_submission(root)
        self.assertFalse(result.ok)
        self.assertTrue(any(item.code == "analytical_import" for item in result.issues))

    def test_synthetic_example_rejects_missing_required_script(self) -> None:
        root = self.synthetic_example()
        (root / "reproduction/download_inputs.sh").unlink()
        result = validate_submission(root)
        self.assertFalse(result.ok)
        self.assertTrue(any(item.code == "missing_script" for item in result.issues))

    def test_ready_requires_full_commit(self) -> None:
        root = self.scaffold()
        payload = self.payload(root)
        payload["submission_status"] = "ready"
        self.write_payload(root, payload)
        self.assertFalse(validate_submission(root).ok)

    def test_cli_exit_codes(self) -> None:
        root = self.scaffold()
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
        ok = subprocess.run([sys.executable, "-m", "submission_tools", "validate", "--submission", str(root)], env=env, capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        (root / "config/model_list.tsv").unlink()
        bad = subprocess.run([sys.executable, "-m", "submission_tools", "validate", "--submission", str(root)], env=env, capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)

    def test_dig_checkout_match_mismatch_and_dirty(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.org"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
            (repo / "file.txt").write_text("x")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "test"], cwd=repo, check=True, capture_output=True)
            commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
            self.assertEqual(inspect_dig_checkout(repo, commit, False), [])
            self.assertTrue(inspect_dig_checkout(repo, "0" * 40, False))
            (repo / "file.txt").write_text("dirty")
            self.assertTrue(inspect_dig_checkout(repo, commit, False))

    def test_draft_placeholder_and_receipt(self) -> None:
        root = self.scaffold()
        dig_repo, _commit = self.fake_dig_repo()
        result = coordinated_validate(root, dig_repo, development_dig_checkout=True)
        self.assertTrue(result.ok)
        receipt = root / "run_receipt.json"
        write_receipt(root / "submission.yaml", dig_repo, {"ok": result.ok}, receipt, ["test"])
        self.assertTrue(validate_receipt(receipt))
        payload = json.loads(receipt.read_text())
        for key in ("library_id", "wrapper_commit", "dig_commit", "input_manifest_digest", "output_manifest_digest", "validation_result"):
            self.assertIn(key, payload)

    def test_coordinated_unknown_identifier_and_ready_smoke(self) -> None:
        root = self.scaffold()
        dig_repo, commit = self.fake_dig_repo()
        payload = self.payload(root)
        payload["submission_status"] = "ready"
        payload["dig"]["commit"] = commit
        payload["dig"]["identifiers"] = ["rna_deg"]
        self.write_payload(root, payload)
        successful = coordinated_validate(root, dig_repo, dig_python=sys.executable, smoke=True)
        self.assertTrue(successful.ok)
        payload["dig"]["identifiers"] = ["unknown_dig_identifier"]
        self.write_payload(root, payload)
        unknown = coordinated_validate(root, dig_repo, dig_python=sys.executable, smoke=False)
        self.assertFalse(unknown.ok)
        self.assertTrue(any(item.code == "dig_identifier" for item in unknown.issues), unknown.issues)

    def test_ci_coordination_is_fork_safe_by_design(self) -> None:
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/validate-submissions.yml").read_text()
        self.assertIn("pull_request:", workflow)
        self.assertNotIn("pull_request_target", workflow)
        self.assertIn("contents: read", workflow)
        self.assertNotIn("secrets.", workflow)
        self.assertNotIn("download_inputs.sh", workflow)


if __name__ == "__main__":
    unittest.main()
