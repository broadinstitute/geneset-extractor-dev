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


class MoTrPACModernSubmissionTests(unittest.TestCase):
    def test_declares_all_existing_models(self) -> None:
        with (ROOT / "config/model_list.tsv").open(encoding="utf-8", newline="") as handle:
            models = {row["model_id"] for row in csv.DictReader(handle, delimiter="\t") if row["enabled"] == "true"}
        with (ROOT / "config/task_manifest.tsv").open(encoding="utf-8", newline="") as handle:
            tasks = {row["model_id"] for row in csv.DictReader(handle, delimiter="\t")}
        self.assertEqual(models, tasks)
        with (ROOT / "expected/output_manifest.tsv").open(encoding="utf-8", newline="") as handle:
            outputs = list(csv.DictReader(handle, delimiter="\t"))
        self.assertEqual(len(outputs), 19 * 4 + 3)

    def test_standard_cluster_adapter_interface(self) -> None:
        source = (ROOT / "run/submit_submission_models_cluster_apptainer.sh").read_text(encoding="utf-8")
        for value in ("DIG_REPO", "SUBMISSION_WORK_DIR", "SUBMISSION_ARRAY_MEMORY", "--model-id", "--smoke", "--full"):
            self.assertIn(value, source)

    @unittest.skipUnless((DIG / "src/geneset_extractors").is_dir(), "requires sibling DIG checkout")
    def test_smoke_reproduction_runs_hz1(self) -> None:
        with TemporaryDirectory() as temp_dir:
            result = subprocess.run(["bash", str(ROOT / "reproduction/reproduce.sh"), "--smoke"], cwd=ROOT, env={**os.environ, "SUBMISSION_WORK_DIR": temp_dir, "DIG_REPO": str(DIG), "PYTHON_BIN": sys.executable}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            output = Path(temp_dir, "smoke/genesets/all_tissues/models/HZ1/extractor/genesets.gmt")
            self.assertTrue(output.is_file())
            self.assertTrue(output.with_name("geneset.provenance.legacy.json").is_file())
            self.assertTrue(output.with_name("geneset.provenance.dapper.yaml").is_file())
            self.assertFalse(output.with_name("geneset.provenance.json").exists())
            dapper_gmt = output.with_name("genesets.dapper-ids.gmt")
            self.assertTrue(dapper_gmt.is_file())
            self.assertTrue(
                all(line.startswith("dapper:GeneSet.") for line in dapper_gmt.read_text(encoding="utf-8").splitlines())
            )
            dapper = output.with_name("geneset.provenance.dapper.yaml").read_text(encoding="utf-8")
            self.assertIn("name: MoTrPAC Rat Endurance Training HZ1", dapper)


if __name__ == "__main__":
    unittest.main()
