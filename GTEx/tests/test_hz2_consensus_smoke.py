from __future__ import annotations

import os
import json
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
            "GTEx_Tissues_V8_Consensus_Brain_Cortex_Female_40-49_up",
            "GTEx_Tissues_V8_Consensus_Whole_Blood_Male_50-59_up",
        ]
        for name in (
            "gene_support.tsv", "geneset.full.tsv", "geneset.meta.json",
            "geneset.model.json", "geneset.provenance.dapper.yaml",
            "geneset.provenance.legacy.json", "geneset.tsv", "run_summary.json",
            "run_summary.txt",
        ):
            assert (gmt.parent / name).is_file()
        summary = json.loads((gmt.parent / "run_summary.json").read_text(encoding="utf-8"))
        assert summary["support_fraction"] == 0.25
        assert {"median", "min", "max"} == set(summary["sample_up_genes"])
        assert summary["n_unique_genes_ever_up"] > 0
