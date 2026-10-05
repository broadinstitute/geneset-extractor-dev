from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
DIG = ROOT.parents[1] / "dig-gene-set-extractors"
DIG_PYTHON = DIG / ".venv/bin/python"


def test_single_model_runner_owns_glygen_execution() -> None:
    runner = (ROOT / "src/run_glygen_model.py").read_text(encoding="utf-8")
    dispatcher = (ROOT / "src/dispatch_glygen_submission.py").read_text(encoding="utf-8")
    assert "--model_id" in runner
    assert "glygen_glycosylated_proteins" in runner
    assert "glygen_glycan_synthesizing_enzymes" in runner
    assert "refresh_model_metadata_and_provenance.sh" in runner
    assert "run_glygen_model.py" in dispatcher


def test_smoke_wrapper_has_standard_model_layout() -> None:
    with TemporaryDirectory() as temp_dir:
        result = subprocess.run(
            ["bash", str(ROOT / "reproduction/reproduce.sh"), "--smoke"], cwd=ROOT,
            env={**os.environ, "SUBMISSION_WORK_DIR": temp_dir, "DIG_REPO": str(DIG), "PYTHON_BIN": str(DIG_PYTHON if DIG_PYTHON.is_file() else sys.executable)}, capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr + result.stdout
        root = Path(temp_dir)
        assert not (root / "full").exists()
        for model_id in ("HZ1", "HZ2"):
            model = root / "genesets/all_glycans/models" / model_id
            extractor = model / "extractor"
            for filename in ("genesets.gmt", "geneset.meta.json", "geneset.model.json", "reconstruction_diagnostics.json", "geneset.meta.json.orig"):
                assert (extractor / filename).is_file()
            assert (model / "workflow/source_manifest.json").is_file()
        assert (root / "genesets/all_glycans/models/HZ2/workflow/glygen_api_cache_manifest.tsv").is_file()
        assert not (root / "genesets/all_glycans/models/HZ2/extractor/glygen_api_cache_manifest.tsv").exists()
