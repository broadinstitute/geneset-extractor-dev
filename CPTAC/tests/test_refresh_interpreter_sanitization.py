"""Unit tests for the SHARED refresh tool's command-interpreter sanitization.

Regression coverage for maintainer finding #7: a local Python interpreter path
(e.g. `/home/user/.pyenv/versions/3.12.4/bin/python`, recorded from
`sys.executable` by the DIG CLI) must not leak into published
`geneset.meta.json` / `geneset.provenance.json`. This is a SHARED,
library-agnostic behavior of `src/refresh_model_metadata_and_provenance.py`
(not CPTAC-specific), but it lives here because that is where the refresh
tool's other tests currently live (see test_cptac_refresh_descriptions.py).
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve()
WRAPPER_REPO_ROOT = HERE.parents[2]
sys.path.insert(0, str(WRAPPER_REPO_ROOT / "src"))

import refresh_model_metadata_and_provenance as refresh  # noqa: E402

INTERPRETER = "/home/dhite/.pyenv/versions/3.12.4/bin/python"


def test_sanitize_interpreter_path_replaces_absolute_path_in_command_argv():
    command_argv = [
        INTERPRETER,
        "-m",
        "geneset_extractors.cli",
        "convert",
        "ptm_site_matrix",
        "--top_k",
        "200",
    ]
    sanitized = refresh.sanitize_interpreter_path(command_argv)
    assert sanitized[0] == "python"
    assert sanitized[1:] == command_argv[1:]


def test_sanitize_interpreter_path_replaces_leading_token_in_command_string():
    command = f"{INTERPRETER} -m geneset_extractors.cli convert ptm_site_matrix --top_k 200"
    sanitized = refresh.sanitize_interpreter_path(command)
    assert sanitized.startswith("python -m geneset_extractors.cli")
    assert "/home/dhite" not in sanitized


def test_sanitize_interpreter_path_does_not_touch_data_paths_containing_python():
    command_argv = [
        INTERPRETER,
        "-m",
        "geneset_extractors.cli",
        "convert",
        "--out_dir",
        "/home/dhite/some/python_project/out",
    ]
    sanitized = refresh.sanitize_interpreter_path(command_argv)
    assert sanitized[0] == "python"
    assert sanitized[-1] == "/home/dhite/some/python_project/out"


def test_sanitize_interpreter_path_leaves_bare_python_unchanged():
    command_argv = ["python", "-m", "geneset_extractors.cli", "convert"]
    assert refresh.sanitize_interpreter_path(command_argv) == command_argv
    assert refresh.sanitize_interpreter_path("python -m geneset_extractors.cli convert") == (
        "python -m geneset_extractors.cli convert"
    )


def test_sanitize_interpreter_path_is_idempotent():
    command_argv = [f"{INTERPRETER}3.12", "-m", "geneset_extractors.cli"]
    once = refresh.sanitize_interpreter_path(command_argv)
    twice = refresh.sanitize_interpreter_path(once)
    assert once == twice
    assert once[0] == "python"


def test_sanitize_directory_args_in_json_genericizes_command_and_command_argv():
    payload = {
        "converter": {
            "execution": {
                "command": [
                    INTERPRETER,
                    "-m",
                    "geneset_extractors.cli",
                    "convert",
                ]
            }
        },
        "lineage": {
            "processes": [
                {
                    "command": f"{INTERPRETER} -m geneset_extractors.cli convert",
                    "command_argv": [
                        INTERPRETER,
                        "-m",
                        "geneset_extractors.cli",
                        "convert",
                    ],
                }
            ]
        },
    }

    sanitized = refresh.sanitize_directory_args_in_json(payload)

    assert sanitized["converter"]["execution"]["command"][0] == "python"
    process = sanitized["lineage"]["processes"][0]
    assert process["command"].startswith("python -m geneset_extractors.cli")
    assert process["command_argv"][0] == "python"
    assert "/home/dhite" not in str(sanitized)
