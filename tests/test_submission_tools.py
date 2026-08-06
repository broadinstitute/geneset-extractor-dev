from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

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
        ok = subprocess.run(["python3", "-m", "submission_tools", "validate", "--submission", str(root)], env=env, capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        (root / "config/model_list.tsv").unlink()
        bad = subprocess.run(["python3", "-m", "submission_tools", "validate", "--submission", str(root)], env=env, capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)


if __name__ == "__main__":
    unittest.main()
