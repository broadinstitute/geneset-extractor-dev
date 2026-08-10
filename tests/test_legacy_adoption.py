from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from submission_tools.adoption import adopt, adoption_status, inventory_legacy
from submission_tools.legacy_compare import compare_gmt
from submission_tools.validator import validate_submission


class LegacyAdoptionTest(unittest.TestCase):
    def legacy_library(self, root: Path) -> Path:
        legacy = root / "legacy"
        legacy.mkdir()
        (legacy / "prepare.py").write_text("# /home/example/input\nprint('manually inspect data')\n", encoding="utf-8")
        (legacy / "run.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        (legacy / "counts.tsv").write_text("gene\tcount\nA\t1\n", encoding="utf-8")
        (legacy / "environment.yml").write_text("name: legacy\n", encoding="utf-8")
        (legacy / "old.gmt").write_text("set_a\tna\tA\tB\n", encoding="utf-8")
        return legacy

    def test_inventory_detects_common_legacy_materials(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            inventory = inventory_legacy(self.legacy_library(Path(temp)))
        self.assertEqual(len(inventory["code_files"]), 2)
        self.assertEqual(len(inventory["data_files"]), 1)
        self.assertEqual(inventory["gene_set_outputs"][0]["n_gene_sets"], 1)
        self.assertTrue(inventory["environment_files"])
        self.assertTrue(inventory["nonportable_findings"])
        self.assertTrue(inventory["manual_step_findings"])

    def test_adopt_does_not_modify_legacy_and_creates_valid_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            legacy = self.legacy_library(root)
            before = (legacy / "old.gmt").read_bytes()
            adopted = adopt(legacy, root / "Adopted", "Adopted")
            self.assertEqual((legacy / "old.gmt").read_bytes(), before)
            self.assertTrue(validate_submission(adopted).ok)
            payload = json.loads((adopted / "submission.yaml").read_text(encoding="utf-8"))
            self.assertEqual(payload["submission_origin"]["type"], "adopted")
            for name in ("inventory.json", "dependency_map.json", "adoption_report.md", "AI_ADOPTION_PROMPT.md"):
                self.assertTrue((adopted / "adoption" / name).is_file())

    def test_compare_modes_and_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old, new = root / "old.gmt", root / "new.gmt"
            old.write_text("set\tna\tA\tB\n", encoding="utf-8")
            new.write_text("set\tna\tB\tA\n", encoding="utf-8")
            self.assertFalse(compare_gmt(old, new, "exact")[0])
            self.assertTrue(compare_gmt(old, new, "set_equivalent")[0])
            adopted = adopt(self.legacy_library(root), root / "Adopted", "Adopted")
            completed = subprocess.run([sys.executable, "-m", "submission_tools", "compare-legacy", "--legacy", str(old), "--new", str(new), "--mode", "report_only"], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            states = dict((name, ok) for name, ok, _ in adoption_status(adopted))
            self.assertTrue(states["INVENTORIED"])
            self.assertTrue(states["NEW_FORMAT_VALID"])
            self.assertFalse(states["READY"])

    def test_library_comparison_writes_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            adopted = adopt(self.legacy_library(root), root / "Adopted", "Adopted")
            generated = adopted / "outputs/old.gmt"
            generated.parent.mkdir()
            generated.write_text("set_a\tna\tB\tA\n", encoding="utf-8")
            completed = subprocess.run([sys.executable, "-m", "submission_tools", "compare-legacy", "--library", str(adopted)], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((adopted / "adoption/comparison_report.tsv").exists())
            self.assertTrue((adopted / "adoption/comparison_summary.md").exists())


if __name__ == "__main__":
    unittest.main()
