from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
import importlib.util
from pathlib import Path

from submission_tools.validator import validate_submission


class GTExModernSubmissionTest(unittest.TestCase):
    def test_draft_contract_is_structurally_valid(self) -> None:
        root = Path(__file__).resolve().parents[1]
        result = validate_submission(root)
        self.assertTrue(result.ok, [f"{issue.code}: {issue.message}" for issue in result.issues])

    @unittest.skipUnless(importlib.util.find_spec("yaml") is not None, "DIG's declared PyYAML dependency is not installed")
    def test_smoke_dispatch_produces_declared_gmt(self) -> None:
        root = Path(__file__).resolve().parents[1]
        dig = root.parents[1] / "dig-gene-set-extractors"
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            env = {
                **os.environ,
                "DIG_REPO": str(dig),
                "PYTHON_BIN": sys.executable,
                "SUBMISSION_WORK_DIR": str(work),
            }
            completed = subprocess.run(
                ["bash", "reproduction/reproduce.sh", "--smoke"],
                cwd=root,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertTrue((work / "genesets/adipose_subcutaneous/models/AB4/extractor/genesets.gmt").is_file())


if __name__ == "__main__":
    unittest.main()
