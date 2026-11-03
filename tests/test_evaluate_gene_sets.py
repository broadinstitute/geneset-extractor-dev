from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


HAS_SCIPY = importlib.util.find_spec("scipy") is not None


def _evaluation_module():
    path = Path(__file__).resolve().parents[1] / "src" / "evaluate_gene_sets.py"
    spec = importlib.util.spec_from_file_location("evaluate_gene_sets", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EvaluateGeneSetsTests(unittest.TestCase):
    def test_discovery_is_recursive_and_output_is_paired_with_gmt(self) -> None:
        evaluation = _evaluation_module()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "outputs"
            nested = root / "tissue" / "model"
            nested.mkdir(parents=True)
            top_level = root / "top.gmt"
            nested_gmt = nested / "sets.GMT"
            top_level.write_text("set\tdesc\tGENE1\n", encoding="utf-8")
            nested_gmt.write_text("set\tdesc\tGENE2\n", encoding="utf-8")
            (nested / "sets.evaluation.tsv").write_text("ignored\n", encoding="utf-8")

            self.assertEqual(evaluation.discover_gmt_files(root), [nested_gmt, top_level])
            self.assertEqual(evaluation.evaluation_output_path(top_level), root / "top.evaluation.tsv")
            self.assertEqual(evaluation.evaluation_output_path(nested_gmt), nested / "sets.evaluation.tsv")

    @unittest.skipUnless(HAS_SCIPY, "scipy is required for hypergeometric evaluation")
    def test_evaluation_writes_one_summary_tsv_per_gmt(self) -> None:
        evaluation = _evaluation_module()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "outputs"
            root.mkdir()
            first = root / "first.gmt"
            second = root / "second.gmt"
            first.write_text("first\tdesc\tGENE1\tGENE2\n", encoding="utf-8")
            second.write_text("second\tdesc\tGENE2\tGENE3\n", encoding="utf-8")
            gmt_files = evaluation.discover_gmt_files(root)
            gene_index, matrix, names = evaluation.build_context(gmt_files, seed=1)

            for gmt_path in gmt_files:
                evaluation.evaluate_gmt(
                    gmt_path,
                    evaluation.evaluation_output_path(gmt_path),
                    gene_index,
                    matrix,
                    names,
                    p_value_cutoff=1.0,
                    max_gene_sets=5,
                    overwrite=False,
                )

            for gmt_path in gmt_files:
                output = evaluation.evaluation_output_path(gmt_path)
                self.assertTrue(output.is_file())
                self.assertEqual(output.read_text(encoding="utf-8").splitlines()[0],
                                 "gene_set_name\tnegative_control_count\tn_hits\tevaluation_score")
