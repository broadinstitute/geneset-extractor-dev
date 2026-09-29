from __future__ import annotations

import csv
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
DIG = ROOT.parents[1] / "dig-gene-set-extractors"


class LincsModernSubmissionTests(unittest.TestCase):
    def test_declared_models_and_outputs_are_complete(self) -> None:
        def rows(path: Path):
            with path.open(encoding="utf-8", newline="") as handle:
                return list(csv.DictReader(handle, delimiter="\t"))
        self.assertEqual({row["model_id"] for row in rows(ROOT / "config/model_list.tsv") if row["enabled"] == "true"}, {"HZ1", "HZ2"})
        self.assertEqual({row["model_id"] for row in rows(ROOT / "config/task_manifest.tsv")}, {"HZ1", "HZ2"})
        self.assertEqual({row["model_id"] for row in rows(ROOT / "expected/output_manifest.tsv")}, {"HZ1", "HZ2"})

    def test_cluster_adapter_uses_standard_submission_interface(self) -> None:
        source = (ROOT / "run/submit_submission_models_cluster_apptainer.sh").read_text(encoding="utf-8")
        self.assertIn("DIG_REPO", source)
        self.assertIn("SUBMISSION_WORK_DIR", source)
        self.assertIn("SUBMISSION_ARRAY_MEMORY", source)
        self.assertIn("--model-id", source)
        self.assertIn("--smoke", source)
        self.assertIn("--full", source)

    def test_apptainer_adapter_uses_standard_modes_and_keeps_full_alias(self) -> None:
        source = (ROOT / "run/run_submission_models_apptainer.sh").read_text(encoding="utf-8")
        self.assertIn("--smoke|--full", source)
        self.assertIn("--full|full", source)

    @unittest.skipUnless((DIG / "src/geneset_extractors").is_dir(), "requires sibling DIG checkout")
    def test_smoke_reproduction_runs_hz1(self) -> None:
        with TemporaryDirectory() as temp_dir:
            result = subprocess.run(["bash", str(ROOT / "reproduction/reproduce.sh"), "--smoke"], cwd=ROOT, env={**os.environ, "SUBMISSION_WORK_DIR": temp_dir, "DIG_REPO": str(DIG), "PYTHON_BIN": sys.executable}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            extractor = Path(temp_dir, "smoke/genesets/all_signatures/models/HZ1/extractor")
            self.assertTrue((extractor / "genesets.gmt").is_file())
            self.assertIn("name: LINCS_L1000_Chem_Pert", (extractor / "geneset.provenance.dapper.yaml").read_text(encoding="utf-8"))
