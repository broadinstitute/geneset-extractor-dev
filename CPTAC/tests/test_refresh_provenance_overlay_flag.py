"""Unit tests for the SHARED refresh tool's metadata-patch command builder.

Regression coverage: CPTAC's provenance carries CRDC-native ids (DRS
`drs://dg.4DFC/<uuid>` as `local_id`, `pdc.cancer.gov/pdc/study/...` as
`dcc_url`, CRDC `datacommons.cancer.gov...` as `drc_url`) that come from the
model's `provenance_overlay.json`, applied at extract time. The shared
refresh's `metadata patch` step regenerates the provenance from the metadata
and, unless `--provenance_overlay_json` is also passed through, drops those
CRDC ids entirely (replaced by generic s3/github dcc_urls).

This is SHARED, library-agnostic behavior of
`src/refresh_model_metadata_and_provenance.py` (not CPTAC-specific), but it
lives here alongside `test_refresh_interpreter_sanitization.py`, where the
refresh tool's other unit tests currently live.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve()
WRAPPER_REPO_ROOT = HERE.parents[2]
sys.path.insert(0, str(WRAPPER_REPO_ROOT / "src"))

import refresh_model_metadata_and_provenance as refresh  # noqa: E402


def test_metadata_patch_command_includes_overlay_flag_when_overlay_exists(tmp_path):
    model_dir = tmp_path / "models" / "PT1"
    model_dir.mkdir(parents=True)
    overlay_path = model_dir / "provenance_overlay.json"
    overlay_path.write_text("{}", encoding="utf-8")
    metadata_path = model_dir / "extractor" / "geneset.meta.json"

    cmd = refresh.build_metadata_patch_command(
        python_bin=Path("python3"),
        metadata_path=metadata_path,
        model_dir=model_dir,
        show_template_vars=False,
        template="some template",
    )

    assert "--provenance_overlay_json" in cmd
    idx = cmd.index("--provenance_overlay_json")
    assert cmd[idx + 1] == str(overlay_path)


def test_metadata_patch_command_omits_overlay_flag_when_overlay_missing(tmp_path):
    model_dir = tmp_path / "models" / "PT1"
    model_dir.mkdir(parents=True)
    metadata_path = model_dir / "extractor" / "geneset.meta.json"

    cmd = refresh.build_metadata_patch_command(
        python_bin=Path("python3"),
        metadata_path=metadata_path,
        model_dir=model_dir,
        show_template_vars=False,
        template="some template",
    )

    assert "--provenance_overlay_json" not in cmd


def test_metadata_patch_command_omits_overlay_flag_with_show_template_vars(tmp_path):
    model_dir = tmp_path / "models" / "PT1"
    model_dir.mkdir(parents=True)
    (model_dir / "provenance_overlay.json").write_text("{}", encoding="utf-8")
    metadata_path = model_dir / "extractor" / "geneset.meta.json"

    cmd = refresh.build_metadata_patch_command(
        python_bin=Path("python3"),
        metadata_path=metadata_path,
        model_dir=model_dir,
        show_template_vars=True,
        template="",
    )

    assert "--show_template_vars" in cmd
    # Overlay flag is additive regardless of show_template_vars mode, since
    # metadata patch --show_template_vars still accepts it (no-op display path).
    assert "--provenance_overlay_json" in cmd
