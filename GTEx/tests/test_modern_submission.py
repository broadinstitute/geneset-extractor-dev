from __future__ import annotations

import os
import csv
import shlex
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
                env={
                    **os.environ,
                    "SUBMISSION_WORK_DIR": temp,
                    "SUBMISSION_ARRAY_MEMORY": "24G",
                    "SUBMISSION_ARRAY_WALLTIME": "48:00:00",
                    "SUBMISSION_JOB_NAME": "gtex_filtered_test",
                },
                text=True,
                capture_output=True,
            )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("--model_id AB1", completed.stdout)
        self.assertIn("--tissue_id adipose_tissue", completed.stdout)
        self.assertIn("GTEX_ARRAY_MEMORY=24G", completed.stdout)
        self.assertIn("GTEX_ARRAY_WALLTIME=48:00:00", completed.stdout)
        self.assertIn("GTEX_JOB_NAME=gtex_filtered_test", completed.stdout)

    def test_apptainer_scheduler_wrapper_combines_hz2_with_standard_models(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            completed = subprocess.run(
                [
                    "bash", "run/submit_submission_models_cluster_apptainer.sh",
                    "--full", "--model-id", "HZ1,HZ2",
                ],
                cwd=root,
                env={**os.environ, "SUBMISSION_WORK_DIR": temp},
                text=True,
                capture_output=True,
            )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("Would also submit one HZ2 consensus task", completed.stdout)
        self.assertIn("--model_id HZ1", completed.stdout)
        self.assertNotIn("--model_id HZ1,HZ2", completed.stdout)

    def test_legacy_cluster_launchers_accept_hz2_for_refresh(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for name in (
            "submit_gtex_models_cluster.sh",
            "submit_gtex_models_cluster_apptainer.sh",
        ):
            source = (root.parent / "run" / name).read_text(encoding="utf-8")
            self.assertIn('else if ($family_col == "hz_consensus") print "HZ2"', source)
            self.assertIn('else if ($2 == "hz_consensus") group = "HZ2"', source)
            self.assertIn("HZ2 consensus uses GTEx/run/submit_submission_models_cluster_apptainer.sh", source)

    def test_legacy_cluster_refresh_worklist_uses_hz2_single_partition(self) -> None:
        root = Path(__file__).resolve().parents[1]
        launcher = root.parent / "run/submit_gtex_models_cluster_apptainer.sh"
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            # Exercise the worklist function without invoking main/qsub.
            harness = directory / "worklist_harness.sh"
            source = launcher.read_text(encoding="utf-8").replace('main "$@"', ': # main disabled for test')
            worklist = directory / "worklist.tsv"
            harness.write_text(
                source
                + "\n"
                + f"GTEX_MODEL_LIST={shlex.quote(str(root / 'config/model_list.tsv'))}\n"
                + f"GTEX_BROAD_TISSUE_LIST={shlex.quote(str(root / 'config/broad_tissue_list.tsv'))}\n"
                + f"GTEX_WORKLIST={shlex.quote(str(worklist))}\n"
                + "FILTER_MODEL_IDS=HZ1,HZ2\n"
                + "REFRESH_METADATA_AND_PROVENANCE=1\n"
                + "write_worklist\n"
                + "cat \"${GTEX_WORKLIST}\"\n",
                encoding="utf-8",
            )
            completed = subprocess.run(["bash", str(harness)], text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            hz2_rows = [line for line in completed.stdout.splitlines() if "\tHZ2\tHZ2\t" in line]
            self.assertEqual(len(hz2_rows), 1)
            self.assertIn("\tall_detailed_tissues\tHZ2\tHZ2\t", hz2_rows[0])

    def test_legacy_cluster_refresh_handles_hz2_before_broad_tissue_lookup(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for name in (
            "submit_gtex_models_cluster.sh",
            "submit_gtex_models_cluster_apptainer.sh",
        ):
            source = (root.parent / "run" / name).read_text(encoding="utf-8")
            refresh_index = source.index("if [[ ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]]; then")
            label_lookup_index = source.index('tissue_label="$(resolve_tissue_label "${tissue_id}")"')
            self.assertLess(
                refresh_index,
                label_lookup_index,
                f"{name} must refresh HZ2 before looking up its non-broad all_detailed_tissues partition",
            )

    def test_full_contract_covers_all_enabled_model_tissue_pairs(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with (root / "config/task_manifest.tsv").open(encoding="utf-8", newline="") as handle:
            tasks = list(csv.DictReader(handle, delimiter="\t"))
        with (root / "expected/output_manifest.tsv").open(encoding="utf-8", newline="") as handle:
            outputs = list(csv.DictReader(handle, delimiter="\t"))
        self.assertEqual(len(tasks), 993)
        self.assertEqual(len(outputs), 991)
        self.assertEqual({row["dig_identifier"] for row in tasks}, {
            "gtex_age_binned", "gtex_continuous_age", "gtex_aging_signatures", "gtex_hz_consensus",
        })
        self.assertTrue(any(row["model_id"] == "HZ1" for row in tasks))
        self.assertTrue(any(row["model_id"] == "HZ2" for row in tasks))


if __name__ == "__main__":
    unittest.main()
