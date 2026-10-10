from __future__ import annotations

import gzip
import tempfile
import unittest
from pathlib import Path

from submission_tools.legacy_current_summary import create_legacy_current_summary


class LegacyCurrentSummaryTests(unittest.TestCase):
    def write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_resolves_stale_manifest_paths_and_writes_aggregate_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write(root / "legacy_gmts/lib/old.gmt", "A\td\tG1\tG2\n")
            self.write(root / "current_gmts/new.gmt", "B\td\tG1\tG3\n")
            self.write(root / "reference_mappings/map.tsv", "legacy_set_name\tregenerated_set_name\nA\tB\n")
            self.write(root / "pairs.tsv", "library_id\tmodel_id\tlegacy_gmt\tcurrent_gmt\tname_mapping\nLIB\tM1\t/obsolete/old.gmt\t/obsolete/new.gmt\t/obsolete/map.tsv\n")
            result = create_legacy_current_summary(root / "pairs.tsv", root / "report")
            self.assertEqual(result["library_count"], 1)
            self.assertEqual(result["mapped_set_count"], 1)
            self.assertTrue((root / "report/report.md").is_file())
            with gzip.open(root / "report/model_summary.tsv.gz", "rt", encoding="utf-8") as handle:
                table = handle.read()
            self.assertIn("LIB\tM1", table)
            self.assertIn("available", table)

    def test_header_only_mapping_reports_no_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write(root / "legacy_gmts/old.gmt", "A\td\tG1\n")
            self.write(root / "current_gmts/new.gmt", "B\td\tG2\n")
            self.write(root / "reference_mappings/map.tsv", "legacy_set_name\tregenerated_set_name\n")
            self.write(root / "pairs.tsv", "library_id\tmodel_id\tlegacy_gmt\tcurrent_gmt\tname_mapping\nLIB\tM1\t/obsolete/old.gmt\t/obsolete/new.gmt\t/obsolete/map.tsv\n")
            result = create_legacy_current_summary(root / "pairs.tsv", root / "report")
            self.assertEqual(result["mapped_set_count"], 0)
            with gzip.open(root / "report/model_summary.tsv.gz", "rt", encoding="utf-8") as handle:
                table = handle.read()
            self.assertIn("no_overlap", table)
            self.assertIn("direct_set_name", table)
            self.assertIn("\t1\t1\t0\t0\t", table)


if __name__ == "__main__":
    unittest.main()
