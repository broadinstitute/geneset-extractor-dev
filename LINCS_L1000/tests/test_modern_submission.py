from __future__ import annotations

import csv
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DIG = ROOT.parents[1] / "dig-gene-set-extractors"


class LincsModernSubmissionTests(unittest.TestCase):
    def test_declared_models_and_outputs_are_complete(self) -> None:
        def rows(path: Path):
            with path.open(encoding="utf-8", newline="") as handle:
                return list(csv.DictReader(handle, delimiter="\t"))
        self.assertEqual({row["model_id"] for row in rows(ROOT / "config/model_list.tsv") if row["enabled"] == "true"}, {"HZ1", "HZ2", "HZ3", "HZ4"})
        self.assertEqual({row["model_id"] for row in rows(ROOT / "config/task_manifest.tsv")}, {"HZ1", "HZ2", "HZ3", "HZ4"})
        self.assertEqual({row["model_id"] for row in rows(ROOT / "expected/output_manifest.tsv")}, {"HZ1", "HZ2", "HZ3", "HZ4"})

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
        self.assertIn('mkdir -p "${SUBMISSION_WORK_DIR}"', source)
        self.assertIn("submit_submission_models_cluster_apptainer.sh --full --submit", source)

    def test_reproduction_translates_full_mode_for_the_dispatcher(self) -> None:
        source = (ROOT / "reproduction/reproduce.sh").read_text(encoding="utf-8")
        self.assertIn('download_mode="full"', source)
        self.assertIn('dispatch_mode="--full"', source)

    def test_legacy_array_launcher_creates_the_output_bind_source(self) -> None:
        source = (ROOT.parent / "run/submit_lincs_l1000_models_cluster_apptainer.sh").read_text(encoding="utf-8")
        self.assertIn('"${LINCS_OUT_ROOT}"', source)
        self.assertIn('SUBMISSION_ARRAY_MEMORY:-16G', source)
        self.assertIn('SUBMISSION_ARRAY_WALLTIME:-24:00:00', source)

    def test_joint_cluster_launcher_splits_hz4(self) -> None:
        source = (ROOT.parent / "run/submit_lincs_l1000_models_cluster_apptainer.sh").read_text(encoding="utf-8")
        self.assertIn("hz4_is_selected", source)
        self.assertIn("plan_hz4_cell_line_time_apptainer.sh", source)
        self.assertIn("submit_hz4_cell_line_time_cluster_apptainer.sh", source)

    @unittest.skipUnless((DIG / "src/geneset_extractors").is_dir(), "requires sibling DIG checkout")
    def test_smoke_reproduction_runs_hz1(self) -> None:
        with TemporaryDirectory() as temp_dir:
            result = subprocess.run(["bash", str(ROOT / "reproduction/reproduce.sh"), "--smoke"], cwd=ROOT, env={**os.environ, "SUBMISSION_WORK_DIR": temp_dir, "DIG_REPO": str(DIG), "PYTHON_BIN": sys.executable}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            extractor = Path(temp_dir, "smoke/genesets/all_signatures/models/HZ1/extractor")
            self.assertTrue((extractor / "genesets.gmt").is_file())
            # DAPPER keeps the legacy machine identifier as an alternate ID
            # and emits the collection's readable name separately.
            self.assertIn("name: LINCS L1000 Chem Pert", (extractor / "geneset.provenance.dapper.yaml").read_text(encoding="utf-8"))

    @unittest.skipUnless((DIG / "src/geneset_extractors").is_dir(), "requires sibling DIG checkout")
    def test_hz4_wrapper_exports_legacy_style_gmt(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source = temp / "cp_coeff_mat.gctx"
            with h5py.File(source, "w") as handle:
                handle.create_dataset("0/DATA/0/matrix", data=np.arange(500, 0, -1).reshape(1, 500))
                handle.create_dataset("0/META/ROW/id", data=np.asarray([f"GENE{i:03d}".encode() for i in range(500)]))
                handle.create_dataset("0/META/COL/lincs_id", data=np.asarray([b"fixture"]))
            result = subprocess.run(
                [sys.executable, str(ROOT / "src/build_lincs_l1000_genesets.py"), "--models", "HZ4", "--cp_coeff_gctx", str(source), "--dig_dir", str(DIG), "--out_root", str(temp / "out"), "--overwrite"],
                cwd=ROOT,
                env={**os.environ, "PYTHONPATH": str(DIG / "src") + (":" + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            gmt = temp / "out/genesets/all_signatures/models/HZ4/extractor/genesets.gmt"
            lines = gmt.read_text(encoding="utf-8").splitlines()
            self.assertEqual([line.split("\t", 1)[0] for line in lines], ["fixture_dn", "fixture_up"])
            self.assertTrue(all(line.split("\t")[1] == "LINCS L1000 chemical perturbation Characteristic Direction signature" for line in lines))
            self.assertTrue(all(len(line.split("\t")) == 252 for line in lines))
            extractor = gmt.parent
            for filename in ["geneset.tsv", "geneset.full.tsv", "signature_summary.tsv", "geneset.meta.json", "geneset.provenance.legacy.json", "geneset.provenance.dapper.yaml", "geneset.provenance.json"]:
                self.assertTrue((extractor / filename).is_file(), filename)
            self.assertFalse((gmt.parent.parent / "workflow/lincs_l1000_cp_signed_term_gene.tsv").exists())

    @unittest.skipUnless((DIG / "src/geneset_extractors").is_dir(), "requires sibling DIG checkout")
    def test_hz3_wrapper_exports_consensus_median_gmt(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source = temp / "cp_coeff_mat.gctx"
            with h5py.File(source, "w") as handle:
                matrix = np.vstack([np.arange(500, dtype=float) + index for index in range(10)] + [np.arange(500, dtype=float) * -1 - index for index in range(10)])
                handle.create_dataset("0/DATA/0/matrix", data=matrix)
                handle.create_dataset("0/META/ROW/id", data=np.asarray([f"GENE{i:03d}".encode() for i in range(500)]))
                handle.create_dataset("0/META/COL/pert_name", data=np.asarray([b"drug_a"] * 10 + [b"drug_b"] * 10))
            result = subprocess.run(
                [sys.executable, str(ROOT / "src/build_lincs_l1000_genesets.py"), "--models", "HZ3", "--cp_coeff_gctx", str(source), "--dig_dir", str(DIG), "--out_root", str(temp / "out"), "--overwrite"],
                cwd=ROOT,
                env={**os.environ, "PYTHONPATH": str(DIG / "src") + (":" + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            extractor = temp / "out/genesets/all_signatures/models/HZ3/extractor"
            lines = (extractor / "genesets.gmt").read_text(encoding="utf-8").splitlines()
            self.assertEqual([line.split("\t", 1)[0] for line in lines], ["drug_a_up", "drug_a_dn", "drug_b_up", "drug_b_dn"])
            self.assertTrue(all(len(line.split("\t")) == 202 for line in lines))
            self.assertTrue((extractor / "geneset.meta.json").is_file())
