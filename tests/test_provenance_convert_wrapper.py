from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
DIG = ROOT.parent / "dig-gene-set-extractors"
DIG_PYTHON = DIG / ".venv" / "bin" / "python"


def _pair(directory: Path) -> Path:
    directory.mkdir(parents=True)
    (directory / "geneset.provenance.json").write_text(json.dumps({"nodes": [
        {"id": "file", "type": "File", "name": "input", "description": "input"},
        {"id": "run", "type": "AnalysisType", "name": "run", "description": "run"},
        {"id": "set", "type": "GeneSet", "name": "set", "description": "set"},
    ], "edges": [
        {"source": "file", "target": "run", "label": "data input"},
        {"source": "run", "target": "set", "label": "data output"},
    ]}), encoding="utf-8")
    (directory / "geneset.meta.json").write_text(json.dumps({"gene_set": {}, "converter": {}, "summary": {}, "input": {}, "output": {}}), encoding="utf-8")
    return directory / "geneset.provenance.json"


class ProvenanceConvertWrapperTest(unittest.TestCase):
    def test_forwards_arguments_to_compatible_dig(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            provenance = _pair(Path(temp) / "out")
            result = subprocess.run(
                [sys.executable, "-m", "submission_tools", "provenance", "convert", str(provenance), "--overwrite", "--dig-repo", str(DIG), "--dig-python", str(DIG_PYTHON if DIG_PYTHON.is_file() else sys.executable)],
                cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)}, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("summary converted=1 skipped=0 failed=0", result.stdout)
            self.assertTrue(provenance.with_name("geneset.provenance.dapper.yaml").is_file())

    def test_reports_incompatible_dig_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fake = Path(temp) / "dig" / "src" / "geneset_extractors"; fake.mkdir(parents=True)
            (fake / "__init__.py").write_text("", encoding="utf-8")
            (fake / "cli.py").write_text("raise SystemExit(9)\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-m", "submission_tools", "provenance", "convert", "x", "--dig-repo", str(fake.parents[1])],
                cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)}, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("does not support `provenance convert`", result.stderr)

    def test_preserves_dig_conversion_failure_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            provenance = Path(temp) / "geneset.provenance.json"
            provenance.write_text("{}", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-m", "submission_tools", "provenance", "convert", str(provenance), "--dig-repo", str(DIG), "--dig-python", str(DIG_PYTHON if DIG_PYTHON.is_file() else sys.executable)],
                cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)}, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("metadata file is missing", result.stderr)
