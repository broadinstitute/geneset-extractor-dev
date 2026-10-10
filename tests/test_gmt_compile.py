from __future__ import annotations

import gzip
import tempfile
import unittest
from pathlib import Path

from submission_tools.gmt_compile import compile_gmts, discover_model_gmts, _write_manifest


class GmtCompileTests(unittest.TestCase):
    def write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_compiles_split_outputs_and_excludes_aggregate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            self.write(root / "genesets/tissue/models/M1/extractor/genesets.gmt", "aggregate\td\tX\n")
            self.write(root / "genesets/tissue/models/M1/extractor/a/genesets.gmt", "A\td\tG1\n")
            self.write(root / "genesets/tissue/models/M1/extractor/b/genesets.gmt", "B\td\tG2\n")
            output = Path(temporary) / "compiled.gmt"
            manifest, count = compile_gmts(root, "M1", output)
            self.assertEqual(count, 2)
            self.assertEqual(len(manifest), 2)
            self.assertEqual(output.read_text(encoding="utf-8"), "A\td\tG1\nB\td\tG2\n")
            _write_manifest(Path(temporary) / "compiled.manifest.tsv.gz", manifest)
            with gzip.open(Path(temporary) / "compiled.manifest.tsv.gz", "rt", encoding="utf-8") as handle:
                self.assertIn("source_gmt", handle.read())

    def test_duplicate_names_fail_unless_prefixed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            self.write(root / "genesets/a/models/M1/extractor/one/genesets.gmt", "same\td\tG1\n")
            self.write(root / "genesets/a/models/M1/extractor/two/genesets.gmt", "same\td\tG2\n")
            with self.assertRaisesRegex(ValueError, "duplicate gene-set name"):
                compile_gmts(root, "M1", Path(temporary) / "fail.gmt")
            self.assertFalse((Path(temporary) / "fail.gmt").exists())
            manifest, _ = compile_gmts(root, "M1", Path(temporary) / "prefixed.gmt", duplicate_policy="prefix_source")
            self.assertIn("__same", (Path(temporary) / "prefixed.gmt").read_text(encoding="utf-8"))
            self.assertEqual(sum(int(row["duplicate_term_count"]) for row in manifest), 1)
            self.assertEqual(sum(int(row["renamed_term_count"]) for row in manifest), 1)

    def test_excludes_workflow_selection_gmts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            self.write(root / "genesets/a/models/M1/workflow/selection/genesets.gmt", "selection\td\tWRONG\n")
            self.write(root / "genesets/a/models/M1/extractor/genesets.gmt", "final\td\tRIGHT\n")
            output = Path(temporary) / "compiled.gmt"
            manifest, count = compile_gmts(root, "M1", output)
            self.assertEqual(count, 1)
            self.assertEqual(len(manifest), 1)
            self.assertEqual(output.read_text(encoding="utf-8"), "final\td\tRIGHT\n")


if __name__ == "__main__":
    unittest.main()
