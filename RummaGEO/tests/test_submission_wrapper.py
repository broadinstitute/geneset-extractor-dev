from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
DIG = ROOT.parents[1] / "dig-gene-set-extractors"
DIG_PYTHON = DIG / ".venv/bin/python"


def test_smoke_wrapper_dispatches_both_declared_models() -> None:
    with TemporaryDirectory() as temp_dir:
        result = subprocess.run(
            ["bash", str(ROOT / "reproduction/reproduce.sh"), "--smoke"],
            cwd=ROOT,
            env={**os.environ, "SUBMISSION_WORK_DIR": temp_dir, "DIG_REPO": str(DIG), "PYTHON_BIN": str(DIG_PYTHON if DIG_PYTHON.is_file() else sys.executable)},
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr + result.stdout
        for model_id, expected_term in [("gene_perturbations", "GSE1_KO_human_dn"), ("drug_perturbations", "GSE2_drug_mouse_up")]:
            extractor = Path(temp_dir) / "genesets/all_signatures/models" / model_id / "extractor"
            assert (extractor / "geneset.meta.json").is_file()
            assert (extractor / "reconstruction_diagnostics.json").is_file()
            assert (extractor / "genesets.gmt").read_text(encoding="utf-8").split("\t", 1)[0] == expected_term
