from __future__ import annotations

import os
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
DIG = ROOT.parents[1] / "dig-gene-set-extractors"
DIG_PYTHON = DIG / ".venv/bin/python"


def test_smoke_and_refresh_dispatch_both_idg_models() -> None:
    python = str(DIG_PYTHON if DIG_PYTHON.is_file() else sys.executable)
    with TemporaryDirectory() as temp_dir:
        base_env = {**os.environ, "SUBMISSION_WORK_DIR": temp_dir, "DIG_REPO": str(DIG), "PYTHON_BIN": python}
        smoke = subprocess.run(["bash", str(ROOT / "reproduction/reproduce.sh"), "--smoke"], cwd=ROOT, env=base_env, text=True, capture_output=True)
        assert smoke.returncode == 0, smoke.stdout + smoke.stderr
        for model_id, expected_sets, expected_memberships in (("HZ1", 2, 3), ("HZ2", 1, 3)):
            extractor = Path(temp_dir) / "genesets/idg/models" / model_id / "extractor"
            assert (extractor / "geneset.meta.json").is_file()
            assert (extractor / "reconstruction_diagnostics.json").is_file()
            diagnostics = (extractor / "reconstruction_diagnostics.json").read_text(encoding="utf-8")
            assert f'"n_gene_sets": {expected_sets}' in diagnostics
            assert f'"n_memberships": {expected_memberships}' in diagnostics
        refresh = subprocess.run(["bash", str(ROOT / "run/refresh_submission_models_apptainer.sh"), "--models", "all"], cwd=ROOT, env={**base_env, "GENESET_EXTRACTORS_IN_APPTAINER": "1", "APPTAINER_PYTHON_BIN": python}, text=True, capture_output=True)
        assert refresh.returncode == 0, refresh.stdout + refresh.stderr
        assert (Path(temp_dir) / "genesets/idg/models/HZ1/extractor/geneset.model.json").is_file()


def test_cluster_submitter_is_a_safe_dry_run() -> None:
    with TemporaryDirectory() as temp_dir:
        result = subprocess.run(["bash", str(ROOT / "run/submit_submission_models_cluster_apptainer.sh"), "--smoke"], cwd=ROOT, env={**os.environ, "SUBMISSION_WORK_DIR": temp_dir}, text=True, capture_output=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Would submit IDG array:" in result.stdout
        assert "-t 1-2" in result.stdout


def test_full_wrapper_uses_user_downloaded_gmts_without_network() -> None:
    python = str(DIG_PYTHON if DIG_PYTHON.is_file() else sys.executable)
    fixture = ROOT / "tests/fixtures"
    with TemporaryDirectory() as temp_dir:
        result = subprocess.run(
            ["bash", str(ROOT / "reproduction/reproduce.sh"), "--full"],
            cwd=ROOT,
            env={
                **os.environ,
                "SUBMISSION_WORK_DIR": temp_dir,
                "DIG_REPO": str(DIG),
                "PYTHON_BIN": python,
                "IDG_DRUG_TARGETS_GMT": str(fixture / "IDG_Drug_Targets_2022.small.gmt"),
                "IDG_ARCHS4_COEXP_GMT": str(fixture / "ARCHS4_IDG_Coexp.small.gmt"),
            },
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        metadata = json.loads((Path(temp_dir) / "genesets/idg/models/HZ1/extractor/geneset.meta.json").read_text(encoding="utf-8"))
        assert metadata["input"]["files"][0]["canonical_uri"].startswith("https://maayanlab.cloud/Enrichr/")
