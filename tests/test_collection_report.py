from __future__ import annotations

import gzip
import tempfile
import unittest
from pathlib import Path

from submission_tools.collection_report import create_collection_report, read_collection_manifest


class CollectionReportTests(unittest.TestCase):
    def write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_collection_creates_individual_and_overall_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write(root / "one/current.gmt", "A\td\tG1\n")
            self.write(root / "two/current.gmt", "B\td\tG2\n")
            self.write(root / "one/legacy.gmt", "A\td\tG1\n")
            self.write(root / "two/legacy.gmt", "B\td\tG2\n")
            self.write(root / "runs.tsv", "library_id\tmodel_id\tlegacy_gmt\tcurrent_gmt\none\tM1\tone/legacy.gmt\tone/current.gmt\ntwo\tHZ1\ttwo/legacy.gmt\ttwo/current.gmt\n")
            result = create_collection_report(root / "runs.tsv", root / "collection", command="example")
            self.assertEqual(result["library_count"], 2)
            self.assertEqual(result["gene_set_count"], 2)
            self.assertEqual(result["legacy_comparison_count"], 2)
            self.assertTrue((root / "collection/report.md").is_file())
            self.assertTrue((root / "collection/pairs/one/M1/report.md").is_file())
            with gzip.open(root / "collection/library_summary.tsv.gz", "rt", encoding="utf-8") as handle:
                self.assertIn("one", handle.read())

    def test_manifest_rejects_duplicate_library_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / "runs.tsv"
            self.write(manifest, "library_id\tmodel_id\tlegacy_gmt\tcurrent_gmt\nA\tM1\ta.gmt\tb.gmt\nA\tM1\tc.gmt\td.gmt\n")
            with self.assertRaisesRegex(ValueError, "duplicate library/model pair"):
                read_collection_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
