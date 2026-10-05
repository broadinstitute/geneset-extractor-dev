from __future__ import annotations
import os, subprocess, sys
from pathlib import Path
from tempfile import TemporaryDirectory
ROOT = Path(__file__).resolve().parents[1]
DIG = ROOT.parents[1] / "dig-gene-set-extractors"
DIG_PYTHON = DIG / ".venv/bin/python"
def test_smoke_submission_layout() -> None:
    with TemporaryDirectory() as temp:
        result = subprocess.run(["bash", str(ROOT / "reproduction/reproduce.sh"), "--smoke"], env={**os.environ, "SUBMISSION_WORK_DIR": temp, "DIG_REPO": str(DIG), "PYTHON_BIN": str(DIG_PYTHON if DIG_PYTHON.is_file() else sys.executable)}, text=True, capture_output=True)
        assert result.returncode == 0, result.stdout + result.stderr
        extractor = Path(temp) / "genesets/all_phenotypes/models/HZ1/extractor"
        for name in ("genesets.gmt", "geneset.meta.json", "geneset.model.json", "reconstruction_diagnostics.json"):
            assert (extractor / name).is_file()
        rows = (extractor / "genesets.gmt").read_text().splitlines()
        assert rows == ["Enlarged Lung (MP:0004882)\tIMPC Data Release 18 direct mouse knockout phenotype association gene set, reconstructed with historical Harmonizome HZ1-style symbol normalization.\tADK\tCLDN18\tKCNAB3\tLRRC8A\tTWIST2"]
