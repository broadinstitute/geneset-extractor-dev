from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from pathlib import Path

from submission_tools.comprehensive_report import convert_legacy_current_tsv, discover_run_root_manifest, render, run, submit


class ComprehensiveReportTests(unittest.TestCase):
    def write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def manifest(self, root: Path) -> Path:
        self.write(root / "gtex.gmt", "A\td\tG1\tG2\n")
        self.write(root / "gtex-old.gmt", "A\td\tG1\tG2\n")
        self.write(root / "lincs.gmt", "B\td\tG3\n")
        payload = {"libraries": [
            {"library_id": "GTEx", "models": [{"model_id": "HZ1", "outputs": [{"output_id": "main", "gmt": "gtex.gmt", "legacy_references": [{"reference_id": "old", "gmt": "gtex-old.gmt"}]}]}]},
            {"library_id": "LINCS", "models": [{"model_id": "HZ1", "outputs": [{"output_id": "main", "gmt": "lincs.gmt"}]}]},
        ]}
        path = root / "reporting.json"; path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_selected_library_writes_standalone_and_aggregate_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); manifest = self.manifest(root); output = root / "run"
            results = run(manifest, output, {"GTEx"}, None, None)
            self.assertEqual(len(results), 1)
            summary = json.loads((output / "rendered/summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["library_count"], 1)
            self.assertEqual(summary["unique_gene_union_count"], 2)
            self.assertTrue((output / "rendered/libraries/GTEx/report.html").is_file())
            self.assertFalse((output / "rendered/libraries/LINCS/report.html").exists())
            with gzip.open(output / "metrics/GTEx.HZ1.main.old.per_term.tsv.gz", "rt", encoding="utf-8") as handle:
                self.assertIn("1.0", handle.read())

    def test_empty_mapping_uses_direct_name_comparison_and_render_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write(root / "new.gmt", "A\td\tG1\n")
            self.write(root / "old.gmt", "A\td\tG2\n")
            self.write(root / "map.tsv", "legacy_set_name\tregenerated_set_name\n")
            manifest = root / "reporting.json"
            manifest.write_text(json.dumps({"libraries": [{"library_id": "LIB", "models": [{"model_id": "M1", "outputs": [{"gmt": "new.gmt", "legacy_references": [{"gmt": "old.gmt", "name_mapping": "map.tsv"}]}]}]}]}), encoding="utf-8")
            output = root / "run"; run(manifest, output, {"LIB"}, None, None)
            metric = json.loads(next((output / "metrics").glob("*.json")).read_text(encoding="utf-8"))
            self.assertEqual(metric["comparison"]["comparison_method"], "direct_set_name")
            self.assertEqual(metric["comparison"]["set_name_recall"], 1.0)
            self.assertEqual(metric["comparison"]["membership_jaccard"], 0.0)
            rendered = render(output, {"LIB"}, None, False)
            self.assertEqual(rendered["library_count"], 1)

    def test_submit_dry_run_uses_executable_script_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); manifest = self.manifest(root); output = root / "run"
            class Args:
                dapper_validator = None; qsub_bin = "qsub"; memory = "2G"; walltime = "01:00:00"; queue = None; project = None
                apptainer_image = None; apptainer_bin = "apptainer"; python_bin = "python3"; bind: list[str] = []; dry_run = True
            payload = submit(manifest, output, {"GTEx"}, None, Args())
            self.assertTrue(Path(payload["script"]).is_absolute())
            self.assertTrue(Path(payload["script"]).stat().st_mode & 0o111)
            self.assertNotIn("bash", payload["qsub_command"])

    def test_converts_legacy_current_tsv_with_stale_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write(root / "legacy_gmts/LIB/old.gmt", "A\td\tG1\n")
            self.write(root / "current_gmts/LIB.M1.gmt", "A\td\tG1\n")
            self.write(root / "reference_mappings/LIB.M1.tsv", "legacy_set_name\tregenerated_set_name\nA\tA\n")
            tsv = root / "legacy_current_mapping.tsv"
            self.write(tsv, "library_id\tmodel_id\tlegacy_gmt\tcurrent_gmt\tname_mapping\nLIB\tM1\t/retired/old.gmt\t/retired/LIB.M1.gmt\t/retired/LIB.M1.tsv\n")
            result = convert_legacy_current_tsv(tsv, root / "reporting.json")
            self.assertEqual(result["library_count"], 1)
            payload = json.loads((root / "reporting.json").read_text(encoding="utf-8"))
            output = payload["libraries"][0]["models"][0]["outputs"][0]
            self.assertEqual(output["gmt"], "current_gmts/LIB.M1.gmt")
            self.assertEqual(output["legacy_references"][0]["gmt"], "legacy_gmts/LIB/old.gmt")

    def test_discovers_and_compiles_model_outputs_from_run_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_root = root / "completed-run"
            self.write(run_root / "genesets/partition/models/HZ1/workflow/selection/genesets.gmt", "selection\td\tWRONG\n")
            self.write(run_root / "genesets/partition/models/HZ1/extractor/genesets.gmt", "A\td\tG1\n")
            self.write(run_root / "genesets/partition/models/HZ1/extractor/geneset.provenance.dapper.yaml", "id: example\n")
            self.write(root / "legacy_gmts/old.gmt", "A\td\tG1\n")
            legacy_tsv = root / "legacy_current_mapping.tsv"
            self.write(legacy_tsv, "library_id\tmodel_id\tlegacy_gmt\tname_mapping\nLIB\tHZ1\t/retired/old.gmt\t\n")
            manifest = root / "discovered.json"
            discovered = discover_run_root_manifest(run_root, legacy_tsv, manifest, library_id="LIB")
            self.assertEqual(discovered["model_count"], 1)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            output = payload["libraries"][0]["models"][0]["outputs"][0]
            self.assertEqual(output["output_id"], "LIB.HZ1.compiled")
            self.assertIn("run_root", output)
            report_root = root / "report"; run(manifest, report_root, {"LIB"}, None, None)
            metric = json.loads(next((report_root / "metrics").glob("*.json")).read_text(encoding="utf-8"))
            self.assertTrue(metric["compile_source_manifest"])
            self.assertTrue(Path(metric["generated_gmt"]).is_file())
            self.assertNotIn("WRONG", Path(metric["generated_gmt"]).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
