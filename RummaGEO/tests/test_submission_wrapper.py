from __future__ import annotations

import os
import subprocess
import sys
import json
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
DIG = ROOT.parents[1] / "dig-gene-set-extractors"
DIG_PYTHON = DIG / ".venv/bin/python"


def test_model_runner_is_the_single_model_execution_entrypoint() -> None:
    runner = (ROOT / "src/run_rummageo_model.py").read_text(encoding="utf-8")
    dispatcher = (ROOT / "src/dispatch_rummageo_submission.py").read_text(encoding="utf-8")
    assert "--model_id" in runner
    assert "rumma_geo_selection" in runner
    assert "rumma_geo" in runner
    assert "run_rummageo_model.py" in dispatcher


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
            source_manifest = Path(temp_dir) / "genesets/all_signatures/models" / model_id / "workflow/source_manifest.json"
            assert (extractor / "geneset.meta.json").is_file()
            assert (extractor / "reconstruction_diagnostics.json").is_file()
            assert (selection / "selection_manifest.tsv").is_file()
            assert (selection / "query_records.used.json").is_file()
            assert json.loads(source_manifest.read_text(encoding="utf-8"))["sources"]["human_rummageo_gmt"]["url"].startswith("file://")
            assert (extractor / "genesets.gmt").read_text(encoding="utf-8").split("\t", 1)[0] == expected_term
        refresh = subprocess.run(
            ["bash", str(ROOT / "run/refresh_submission_models_apptainer.sh"), "--models", "HZ1"],
            cwd=ROOT,
            env={**os.environ, "GENESET_EXTRACTORS_IN_APPTAINER": "1", "APPTAINER_PYTHON_BIN": str(DIG_PYTHON if DIG_PYTHON.is_file() else sys.executable), "DIG_REPO": str(DIG), "SUBMISSION_WORK_DIR": temp_dir},
            capture_output=True,
            text=True,
        )
        assert refresh.returncode == 0, refresh.stderr + refresh.stdout
        refreshed_extractor = Path(temp_dir) / "genesets/all_signatures/models/HZ1/extractor"
        assert (refreshed_extractor / "geneset.model.json").is_file()
        assert (refreshed_extractor / "geneset.meta.json.orig").is_file()


def test_cluster_adapter_is_safe_by_default_and_uses_standard_interface() -> None:
    source = (ROOT / "run/submit_submission_models_cluster_apptainer.sh").read_text(encoding="utf-8")
    assert "--submit" in source
    assert "QSUB_BIN" in source
    assert "SUBMISSION_WORK_DIR" in source
    assert "SUBMISSION_ARRAY_MEMORY" in source
    assert "--model-id" in source
    assert "--refresh-metadata-and-provenance" in source
    assert "LOCAL_INPUT_SOURCE_MAP_TSV" in source
    assert "refresh_submission_models_apptainer.sh" in source
    result = subprocess.run(
        ["bash", str(ROOT / "run/submit_submission_models_cluster_apptainer.sh"), "--full"],
        cwd=ROOT,
        env={**os.environ, "SUBMISSION_WORK_DIR": "/tmp/rummageo_wrapper_dry_run"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "Would submit RummaGEO array:" in result.stdout
    assert "-t 1-1" in result.stdout


def test_full_dispatch_generates_source_manifest_from_standard_source_map() -> None:
    fixture = ROOT / "tests/fixtures"
    input_names = {
        "RUMMAGEO_HUMAN_GMT": "human.gmt",
        "RUMMAGEO_MOUSE_GMT": "mouse.gmt",
        "RUMMAGEO_QUERY_RECORDS_JSON": "query_records.json",
        "RUMMAGEO_DRUG_TERMS_JSON": "drug_terms.json",
        "RUMMAGEO_HUMAN_GENE_INFO": "human_gene_info.tsv",
        "RUMMAGEO_MOUSE_GENE_INFO": "mouse_gene_info.tsv",
        "RUMMAGEO_GENE_ORTHOLOGS": "gene_orthologs.tsv",
    }
    with TemporaryDirectory() as temp_dir:
        work = Path(temp_dir)
        source_map = work / "local_input_source_map.tsv"
        source_map.write_text(
            "local_path\tsource_uri\n" + "".join(
                f"{fixture / name}\thttps://example.org/{name}\n" for name in input_names.values()
            ),
            encoding="utf-8",
        )
        result = subprocess.run(
            [str(DIG_PYTHON if DIG_PYTHON.is_file() else sys.executable), str(ROOT / "src/dispatch_rummageo_submission.py"), "--full", "--models", "HZ1", "--out-root", str(work / "out")],
            cwd=ROOT,
            env={**os.environ, "DIG_REPO": str(DIG), "LOCAL_INPUT_SOURCE_MAP_TSV": str(source_map), **{key: str(fixture / value) for key, value in input_names.items()}},
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr + result.stdout
        source_manifest = work / "out/genesets/all_signatures/models/HZ1/workflow/source_manifest.json"
        sources = json.loads(source_manifest.read_text(encoding="utf-8"))["sources"]
        assert sources["human_rummageo_gmt"]["url"] == "https://example.org/human.gmt"
        assert sources["human_rummageo_gmt"]["version"].startswith("sha256:")
        assert sources["sigcom_lincs_drug_terms"]["url"] == "https://example.org/drug_terms.json"
