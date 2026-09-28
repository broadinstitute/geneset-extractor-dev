from __future__ import annotations

import os
import csv
import subprocess
import sys
import tempfile
import unittest
import importlib.util
from pathlib import Path

from submission_tools.validator import validate_submission


class GTExModernSubmissionTest(unittest.TestCase):
    def test_draft_contract_is_structurally_valid(self) -> None:
        root = Path(__file__).resolve().parents[1]
        result = validate_submission(root)
        self.assertTrue(result.ok, [f"{issue.code}: {issue.message}" for issue in result.issues])

    @unittest.skipUnless(importlib.util.find_spec("yaml") is not None, "DIG's declared PyYAML dependency is not installed")
    def test_smoke_dispatch_produces_declared_gmt(self) -> None:
        root = Path(__file__).resolve().parents[1]
        dig = root.parents[1] / "dig-gene-set-extractors"
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            env = {
                **os.environ,
                "DIG_REPO": str(dig),
                "PYTHON_BIN": sys.executable,
                "SUBMISSION_WORK_DIR": str(work),
            }
            completed = subprocess.run(
                ["bash", "reproduction/reproduce.sh", "--smoke"],
                cwd=root,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertTrue((work / "genesets/adipose_subcutaneous/models/AB4/extractor/genesets.gmt").is_file())

    def test_apptainer_scheduler_wrapper_dry_run_never_submits(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            completed = subprocess.run(
                ["bash", "run/submit_submission_models_cluster_apptainer.sh", "--smoke"],
                cwd=root,
                env={**os.environ, "SUBMISSION_WORK_DIR": temp},
                text=True,
                capture_output=True,
            )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("Would run one smoke job", completed.stdout)

    def test_apptainer_scheduler_wrapper_forwards_full_task_filters(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            completed = subprocess.run(
                [
                    "bash", "run/submit_submission_models_cluster_apptainer.sh",
                    "--full", "--model-id", "AB1", "--tissue-id", "adipose_tissue",
                ],
                cwd=root,
                env={**os.environ, "SUBMISSION_WORK_DIR": temp},
                text=True,
                capture_output=True,
            )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("--model_id AB1", completed.stdout)
        self.assertIn("--tissue_id adipose_tissue", completed.stdout)

    def test_full_contract_covers_all_enabled_model_tissue_pairs(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with (root / "config/task_manifest.tsv").open(encoding="utf-8", newline="") as handle:
            tasks = list(csv.DictReader(handle, delimiter="\t"))
        with (root / "expected/output_manifest.tsv").open(encoding="utf-8", newline="") as handle:
            outputs = list(csv.DictReader(handle, delimiter="\t"))
        self.assertEqual(len(tasks), 991)
        self.assertEqual(len(outputs), 990)
        self.assertEqual({row["dig_identifier"] for row in tasks}, {
            "gtex_age_binned", "gtex_continuous_age", "gtex_aging_signatures",
        })
        self.assertTrue(any(row["model_id"] == "HZ1" for row in tasks))


if __name__ == "__main__":
    unittest.main()
