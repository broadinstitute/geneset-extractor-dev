from __future__ import annotations

import csv
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
DIG = REPO / "dig-gene-set-extractors"


class HuBMAPModernSubmissionTests(unittest.TestCase):
    def test_cluster_launcher_accepts_explicit_full_and_hyphenated_model_id(self) -> None:
        with TemporaryDirectory() as temp_dir:
            result = subprocess.run(
                [
                    "bash", str(ROOT / "run/submit_submission_models_cluster_apptainer.sh"),
                    "--full", "--model-id", "HZ1",
                ],
                cwd=ROOT,
                env={**os.environ, "SUBMISSION_WORK_DIR": temp_dir},
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("--model_id HZ1", result.stdout)

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

    def test_wrapper_declares_stable_hubmap_collection_names(self) -> None:
        source = (ROOT / "src/run_hubmap_hz_model.py").read_text(encoding="utf-8")
        self.assertIn('"HuBMAP ASCT+B gene-set library (HZ1)"', source)
        self.assertIn('"--signature_name"', source)

    @unittest.skipUnless((DIG / "src/geneset_extractors").is_dir(), "requires sibling DIG checkout")
    def test_smoke_reproduction_runs_hz1_without_network(self) -> None:
        with TemporaryDirectory() as temp_dir:
            result = subprocess.run(["bash", str(ROOT / "reproduction/reproduce.sh"), "--smoke"], cwd=ROOT, env={**os.environ, "SUBMISSION_WORK_DIR": temp_dir, "DIG_REPO": str(DIG), "PYTHON_BIN": sys.executable}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            extractor = Path(temp_dir, "smoke/genesets/all_signatures/models/HZ1/extractor")
            self.assertTrue((extractor / "genesets.gmt").is_file())
            dapper = yaml.safe_load((extractor / "geneset.provenance.dapper.yaml").read_text(encoding="utf-8"))
            collection = dapper["gene_set_collections"][0]
            self.assertEqual(collection["name"], "HuBMAP ASCT+B gene-set library (HZ1)")
            self.assertTrue((extractor / "genesets.dapper-ids.gmt").is_file())
            self.assertEqual(collection["members"], [row["id"] for row in dapper["gene_sets"]])
            self.assertEqual(collection["n_genes"], len({gene for row in dapper["gene_sets"] for gene in row["members"]}))
            companion = next(node for node in dapper["files"] if node["filename"] == "genesets.dapper-ids.gmt")
            self.assertEqual(collection["has_gmt_file"], companion["id"])
            for row, line in zip(dapper["gene_sets"], (extractor / "genesets.dapper-ids.gmt").read_text(encoding="utf-8").splitlines(), strict=True):
                self.assertEqual(row["gmt_entry"], row["id"])
                self.assertEqual(line.split("\t", 1)[0], row["id"])
                self.assertEqual(row["in_gmt_file"], companion["id"])


if __name__ == "__main__":
    unittest.main()
