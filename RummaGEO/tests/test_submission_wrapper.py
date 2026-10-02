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
        for model_id, expected_term in [("HZ1", "GSE2_drug_0_v_1_mouse_up"), ("HZ2", "GSE1_knockdown_0_v_1_human_up")]:
            extractor = Path(temp_dir) / "genesets/all_signatures/models" / model_id / "extractor"
            selection = Path(temp_dir) / "genesets/all_signatures/models" / model_id / "workflow/selection"
            assert (extractor / "geneset.meta.json").is_file()
            assert (extractor / "reconstruction_diagnostics.json").is_file()
            assert (selection / "selection_manifest.tsv").is_file()
            assert (selection / "query_records.used.json").is_file()
            assert (extractor / "genesets.gmt").read_text(encoding="utf-8").split("\t", 1)[0] == expected_term


def test_cluster_adapter_is_safe_by_default_and_uses_standard_interface() -> None:
    source = (ROOT / "run/submit_submission_models_cluster_apptainer.sh").read_text(encoding="utf-8")
    assert "--submit" in source
    assert "QSUB_BIN" in source
    assert "SUBMISSION_WORK_DIR" in source
    assert "SUBMISSION_ARRAY_MEMORY" in source
    assert "--model-id" in source
    result = subprocess.run(
        ["bash", str(ROOT / "run/submit_submission_models_cluster_apptainer.sh"), "--full"],
        cwd=ROOT,
        env={**os.environ, "SUBMISSION_WORK_DIR": "/tmp/rummageo_wrapper_dry_run"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "Would submit RummaGEO job:" in result.stdout
