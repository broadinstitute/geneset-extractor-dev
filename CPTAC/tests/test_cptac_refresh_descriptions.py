"""Exercise the SHARED refresh tool's CPTAC branch: rewrites an empty GMT description
column into a directional, model-specific sentence using the real `geneset.model.json`
schema (Task 3) + `CPTAC/config/model_description_templates.tsv`.

Uses the real offline CPTAC pipeline (already exercised by
test_run_cptac_ptm_model_offline.py) to produce one genuinely valid
`geneset.meta.json` / `geneset.model.json` pair for the ProteinAdjusted variant, then
repackages just that variant's `up` row into a tiny single-meta extractor dir (no
manifest.tsv) at the same `genesets/<cohort_id>/models/<model_id>` path shape the
shared refresh tool expects, and runs the refresh script against it end to end.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
import run_cptac_ptm_model as runner  # noqa: E402

HERE = Path(__file__).resolve()
WRAPPER_REPO_ROOT = HERE.parents[2]
REPO_ROOT = HERE.parents[3]
DIG_DIR = REPO_ROOT / "dig-gene-set-extractors"
FIX = HERE.parent / "fixtures"
CONFIG = HERE.parents[1] / "config"
REFRESH_SCRIPT = WRAPPER_REPO_ROOT / "src" / "refresh_model_metadata_and_provenance.py"

UP_SET_NAME = "CPTAC_ClearCellRCC_ProteinAdjusted_up"


def _api_cache(tmp_path: Path) -> Path:
    def md5(p: Path) -> str:
        return hashlib.md5(Path(p).read_bytes()).hexdigest()

    phospho = json.loads((FIX / "files_per_study.ccrcc_phospho.json").read_text())
    phospho["data"]["filesPerStudy"][0]["md5sum"] = md5(FIX / "reports" / "CCRCC_Phosphoproteome.phosphosite.tmt10.tsv")
    proteome = json.loads((FIX / "files_per_study.ccrcc_proteome.json").read_text())
    proteome["data"]["filesPerStudy"][0]["md5sum"] = md5(FIX / "reports" / "CCRCC_Proteome.tmt10.tsv")
    biospec = json.loads((FIX / "biospecimen_per_study.ccrcc.json").read_text())
    out = tmp_path / "api_cache.json"
    out.write_text(json.dumps({"phospho_files": phospho, "proteome_files": proteome, "biospecimen": biospec}))
    return out


def _build_fixture_model_dir(tmp_path: Path) -> Path:
    real_model_dir = runner.run_model(
        dig_dir=DIG_DIR,
        cohort_id="ccrcc",
        model_id="PT1",
        out_root=tmp_path / "real_run",
        config_dir=CONFIG,
        offline=True,
        source_dir=FIX / "reports",
        api_cache_json=_api_cache(tmp_path),
        python_bin=sys.executable,
    )
    variant_dirs = sorted((real_model_dir / "extractor").glob("*protein_adjustment=subtract*"))
    assert variant_dirs, "no ProteinAdjusted variant directory produced by the real offline pipeline"
    variant_dir = variant_dirs[0]

    # Tiny single-meta extractor dir (no manifest.tsv) at the path shape the shared
    # refresh tool's regenerate_cptac_model_sidecars derives cohort_id/model_id from.
    model_dir = tmp_path / "cptac_all_models" / "genesets" / "ccrcc" / "models" / "PT1"
    extractor_dir = model_dir / "extractor"
    extractor_dir.mkdir(parents=True)
    shutil.copy2(variant_dir / "geneset.meta.json", extractor_dir / "geneset.meta.json")
    shutil.copy2(variant_dir / "geneset.model.json", extractor_dir / "geneset.model.json")
    if (variant_dir / "geneset.tsv").exists():
        shutil.copy2(variant_dir / "geneset.tsv", extractor_dir / "geneset.tsv")

    up_rows = [
        line
        for line in (variant_dir / "genesets.gmt").read_text().splitlines()
        if line.split("\t", 1)[0] == UP_SET_NAME
    ]
    assert up_rows, f"expected a {UP_SET_NAME} row in the real pipeline's genesets.gmt"
    (extractor_dir / "genesets.gmt").write_text(up_rows[0] + "\n", encoding="utf-8")
    return model_dir


def _up_row(gmt_path: Path) -> list[str]:
    for line in gmt_path.read_text().splitlines():
        if not line.strip():
            continue
        row = line.split("\t")
        if row[0] == UP_SET_NAME:
            return row
    raise AssertionError(f"{UP_SET_NAME} row not found in {gmt_path}")


@pytest.mark.skipif(not DIG_DIR.exists(), reason="dig-gene-set-extractors checkout not found")
def test_refresh_rewrites_empty_description_with_directional_cptac_text(tmp_path):
    model_dir = _build_fixture_model_dir(tmp_path)
    gmt_path = model_dir / "extractor" / "genesets.gmt"

    # RED-state sanity: the raw extractor output ships an empty description column.
    assert _up_row(gmt_path)[1] == ""

    cmd = [
        sys.executable,
        str(REFRESH_SCRIPT),
        "--model_id", "PT1",
        "--model_dir", str(model_dir),
        "--description_template_tsv", str(CONFIG / "model_description_templates.tsv"),
        "--dig_dir", str(DIG_DIR),
        "--python_bin", sys.executable,
    ]
    completed = subprocess.run(cmd, cwd=str(WRAPPER_REPO_ROOT), capture_output=True, text=True)
    assert completed.returncode == 0, completed.stdout + completed.stderr

    description = _up_row(gmt_path)[1]
    assert description, "expected a non-empty rewritten description"
    assert "up-gene set" in description
    assert "Clear Cell RCC" in description
