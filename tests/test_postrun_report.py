from __future__ import annotations

import gzip
import tempfile
import unittest
from pathlib import Path

from submission_tools.postrun_report import create_report, read_gmt


class PostrunReportTests(unittest.TestCase):
    def write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_report_writes_inventory_comparison_and_qc(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            generated = root / "run/genesets/blood/models/M1/extractor/group/genesets.gmt"
            legacy = root / "legacy.gmt"
            output = root / "report"
            self.write(generated, "A\tdesc\tG1\tG2\nB\tdesc\t\n")
            self.write(legacy, "A\tdesc\tG2\tG3\nC\tdesc\tG4\n")
            result = create_report(root / "run", output, legacy_gmts=[legacy], min_gene_set_size=1, command="example")
            self.assertEqual(result["generated_gmt_count"], 1)
            self.assertTrue((output / "report.md").is_file())
            self.assertTrue((output / "legacy_comparison_summary.tsv.gz").is_file())
            with gzip.open(output / "qc_flags.tsv.gz", "rt", encoding="utf-8") as handle:
                self.assertIn("empty;below_min_size_1", handle.read())
            self.assertIn("0.3333", (output / "report.md").read_text(encoding="utf-8"))

    def test_duplicate_gmt_names_are_reported_not_merged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "sets.gmt"
            self.write(path, "A\td\tG1\nA\td\tG2\n")
            sets, warnings = read_gmt(path)
            self.assertEqual(sets, {"A": {"G1"}})
            self.assertEqual(len(warnings), 1)

    def test_legacy_pairing_must_be_unambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write(root / "run/first.gmt", "A\td\tG1\n")
            self.write(root / "run/second.gmt", "A\td\tG1\n")
            self.write(root / "old.gmt", "A\td\tG1\n")
            with self.assertRaisesRegex(ValueError, "exactly one"):
                create_report(root / "run", root / "report", legacy_gmts=[root / "old.gmt"])

    def test_explicit_name_mapping_is_applied(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write(root / "run/generated.gmt", "new_a\td\tG1\n")
            self.write(root / "old.gmt", "old_a\td\tG1\n")
            self.write(root / "mapping.tsv", "legacy_set_name\tgenerated_set_name\nold_a\tnew_a\n")
            create_report(root / "run", root / "report", legacy_gmts=[root / "old.gmt"], mapping_path=root / "mapping.tsv")
            with gzip.open(root / "report/legacy_per_set_comparison.tsv.gz", "rt", encoding="utf-8") as handle:
                self.assertIn("old_a\tnew_a\tmatched", handle.read())


if __name__ == "__main__":
    unittest.main()
