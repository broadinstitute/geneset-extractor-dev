from __future__ import annotations
import os, subprocess, sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
DIG = ROOT.parents[1] / "dig-gene-set-extractors"

def test_smoke_submission_layout() -> None:
    with TemporaryDirectory() as temp:
        result = subprocess.run(["bash", str(ROOT / "reproduction/reproduce.sh"), "--smoke"], env={**os.environ, "SUBMISSION_WORK_DIR": temp, "DIG_REPO": str(DIG), "PYTHON_BIN": sys.executable}, text=True, capture_output=True)
        assert result.returncode == 0, result.stdout + result.stderr
        extractor = Path(temp) / "genesets/all_metabolites/models/HZ1/extractor"
        for name in ("genesets.gmt", "geneset.meta.json", "geneset.model.json", "reconstruction_diagnostics.json"):
            assert (extractor / name).is_file()
        assert (extractor / "genesets.gmt").read_text() == "Metabolite A\tGene sets representing human genes associated with metabolites in Metabolomics Workbench, reconstructed from the Harmonizome processed edge list using the documented Ma'ayan Lab procedure.\tG1\tG2\tG3\tG4\tG5\n"
