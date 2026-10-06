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
            self.write(root / "one/run/genesets.gmt", "A\td\tG1\n")
            self.write(root / "two/run/genesets.gmt", "B\td\tG2\n")
            self.write(root / "one/legacy.gmt", "A\td\tG1\n")
            self.write(root / "runs.tsv", "library_id\trun_root\tlegacy_gmt\none\tone/run\tone/legacy.gmt\ntwo\ttwo/run\t\n")
            result = create_collection_report(root / "runs.tsv", root / "collection", command="example")
            self.assertEqual(result["library_count"], 2)
            self.assertEqual(result["gene_set_count"], 2)
            self.assertEqual(result["legacy_comparison_count"], 1)
            self.assertTrue((root / "collection/report.md").is_file())
            self.assertTrue((root / "collection/libraries/one/report.md").is_file())
            with gzip.open(root / "collection/library_summary.tsv.gz", "rt", encoding="utf-8") as handle:
                self.assertIn("one", handle.read())

    def test_manifest_rejects_duplicate_library_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / "runs.tsv"
            self.write(manifest, "library_id\trun_root\nA\trun1\nA\trun2\n")
            with self.assertRaisesRegex(ValueError, "duplicate library_id"):
                read_collection_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
