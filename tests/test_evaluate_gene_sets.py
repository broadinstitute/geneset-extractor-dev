from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


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

    def test_intermediate_results_keep_the_gmt_tree_structure(self) -> None:
        evaluation = _evaluation_module()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "outputs"
            gmt = root / "tissue" / "model.gmt"
            gmt.parent.mkdir(parents=True)
            gmt.write_text("set\tdesc\tGENE1\n", encoding="utf-8")
            intermediate_root = Path(temporary_directory) / "hits"

            self.assertEqual(
                evaluation.intermediate_output_path(gmt, root, intermediate_root),
                intermediate_root / "tissue" / "model.evaluation.hits.tsv",
            )
