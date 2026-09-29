from __future__ import annotations

import csv
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
DIG = REPO / "dig-gene-set-extractors"


class HuBMAPModernSubmissionTests(unittest.TestCase):
    def test_declared_models_and_outputs_are_complete(self) -> None:
        with (ROOT / "config/model_list.tsv").open(encoding="utf-8", newline="") as handle:
            models = list(csv.DictReader(handle, delimiter="\t"))
        with (ROOT / "config/task_manifest.tsv").open(encoding="utf-8", newline="") as handle:
            tasks = list(csv.DictReader(handle, delimiter="\t"))
        with (ROOT / "expected/output_manifest.tsv").open(encoding="utf-8", newline="") as handle:
            outputs = list(csv.DictReader(handle, delimiter="\t"))
        self.assertEqual({row["model_id"] for row in models if row["enabled"] == "true"}, {"HZ1", "HZ2"})
        self.assertEqual({row["model_id"] for row in tasks}, {"HZ1", "HZ2"})
        self.assertEqual({row["model_id"] for row in outputs}, {"HZ1", "HZ2"})

    @unittest.skipUnless((DIG / "src/geneset_extractors").is_dir(), "requires sibling DIG checkout")
    def test_smoke_reproduction_runs_hz1_without_network(self) -> None:
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as temp_dir:
            result = subprocess.run(["bash", str(ROOT / "reproduction/reproduce.sh"), "--smoke"], cwd=ROOT, env={**os.environ, "SUBMISSION_WORK_DIR": temp_dir, "DIG_REPO": str(DIG), "PYTHON_BIN": sys.executable}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue(Path(temp_dir, "smoke/genesets/all_signatures/models/HZ1/extractor/genesets.gmt").is_file())


if __name__ == "__main__":
    unittest.main()
