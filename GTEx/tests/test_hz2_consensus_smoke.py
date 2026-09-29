from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def test_hz2_smoke_uses_dig_and_writes_deterministic_consensus() -> None:
    root = Path(__file__).resolve().parents[1]
    dig = root.parents[1] / "dig-gene-set-extractors"
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)
        completed = subprocess.run(
            ["bash", "run/build_gtex_genesets.sh", "--smoke", "--task-id", "gtex_smoke_hz2_all_detailed_tissues", "--out-root", str(work)],
            cwd=root,
            env={**os.environ, "DIG_REPO": str(dig), "PYTHON_BIN": sys.executable},
            text=True,
            capture_output=True,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        gmt = work / "genesets/all_detailed_tissues/models/HZ2/extractor/genesets.gmt"
        assert gmt.is_file()
        assert [line.split("\t")[0] for line in gmt.read_text(encoding="utf-8").splitlines()] == [
            "Brain - Cortex Female 40-49 Up", "Whole Blood Male 50-59 Up"
        ]
        assert (gmt.parent / "geneset.provenance.legacy.json").is_file()
