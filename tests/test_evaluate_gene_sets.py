from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock


def _evaluation_module():
    path = Path(__file__).resolve().parents[1] / "src" / "evaluate_gene_sets.py"
    spec = importlib.util.spec_from_file_location("evaluate_gene_sets", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EvaluateGeneSetsTests(unittest.TestCase):
    def test_discovery_is_recursive_and_output_is_consolidated(self) -> None:
        evaluation = _evaluation_module()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "outputs"
            nested = root / "tissue" / "model"
            nested.mkdir(parents=True)
            top_level = root / "top.gmt"
            nested_gmt = nested / "sets.GMT"
            top_level.write_text("set\tdesc\tGENE1\n", encoding="utf-8")
            nested_gmt.write_text("set\tdesc\tGENE2\n", encoding="utf-8")

            self.assertEqual(evaluation.discover_gmt_files(root), [nested_gmt, top_level])
            self.assertEqual(
                evaluation.default_evaluation_output_path(root),
                root / "evaluation" / "evaluation_summary.tsv",
            )

    def test_evaluation_directory_does_not_add_to_gmt_discovery(self) -> None:
        evaluation = _evaluation_module()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "outputs"
            gmt = root / "tissue" / "model.gmt"
            gmt.parent.mkdir(parents=True)
            gmt.write_text("set\tdesc\tGENE1\n", encoding="utf-8")
            evaluation_directory = root / "evaluation"
            evaluation_directory.mkdir()
            (evaluation_directory / "evaluation_summary.tsv").write_text("source_gmt\n", encoding="utf-8")

            self.assertEqual(
                evaluation.discover_gmt_files(root),
                [gmt],
            )

    def test_main_writes_one_summary_with_a_source_gmt_column(self) -> None:
        evaluation = _evaluation_module()
        fake_scorer = types.ModuleType("gene_set_evaluation_score")
        fake_scorer.build_evaluation_context = lambda *args: object()
        fake_scorer.read_gmt = lambda path: {"set": ["GENE1"]}
        def fake_evaluate_gene_sets(gene_lists, *args, progress_callback=None):
            if progress_callback is not None:
                progress_callback(len(gene_lists), len(gene_lists))
            return [[{"gene_set": "reference", "gene_set_size": 1, "p_value": 0.01}] for _ in gene_lists]

        fake_scorer.evaluate_gene_sets = fake_evaluate_gene_sets
        fake_scorer.summarize_hits = lambda name, size, hits: {
            "gene_set_name": name,
            "gene_set_size": size,
            "top_enriched_gene_set": "reference",
            "enriched_gene_set_size": 1,
            "enriched_gene_set_p_value": 0.01,
            "negative_control_count": 0,
            "n_hits": len(hits),
            "evaluation_score": 1.0,
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "outputs"
            gmt = root / "tissue" / "model.gmt"
            reference = Path(temporary_directory) / "reference.gmt"
            gmt.parent.mkdir(parents=True)
            gmt.write_text("set\tdesc\tGENE1\n", encoding="utf-8")
            reference.write_text("reference\tdesc\tGENE1\n", encoding="utf-8")
            with mock.patch.dict(sys.modules, {"gene_set_evaluation_score": fake_scorer}), mock.patch.object(
                sys, "argv", [
                    "evaluate_gene_sets.py", "--local_output_root", str(root), "-r", str(reference),
                    "--progress-every", "1",
                ]
            ):
                evaluation.main()

            self.assertEqual(
                evaluation.default_evaluation_output_path(root).read_text(encoding="utf-8").splitlines(),
                [
                    "source_gmt\tgene_set_name\tnegative_control_count\tn_hits\tevaluation_score",
                    "tissue/model.gmt\tset\t0\t1\t1.0",
                ],
            )
