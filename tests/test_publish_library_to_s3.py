from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


def _publisher_module():
    path = Path(__file__).resolve().parents[1] / "src" / "publish_library_to_s3.py"
    spec = importlib.util.spec_from_file_location("publish_library_to_s3", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PublishLibraryToS3Tests(unittest.TestCase):
    def test_provenance_filter_excludes_unmentioned_output_files(self):
        publisher = _publisher_module()
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_root = Path(temporary_directory) / "outputs"
            model = output_root / "model_one"
            model.mkdir(parents=True)
            declared = model / "genesets.gmt"
            extra = model / "debug.tsv"
            declared.write_text("set\tdesc\tGENE1\n", encoding="utf-8")
            extra.write_text("debug\n", encoding="utf-8")
            provenance = model / "geneset.provenance.legacy.json"
            provenance.write_text(json.dumps({
                "graph": {"nodes": [{
                    "type": "File",
                    "c2m2_properties": {"local_id": "model_one/genesets.gmt"},
                }]},
            }), encoding="utf-8")

            candidates = publisher.iter_output_candidates(
                local_output_root=output_root,
                s3_output_root="s3://example-bucket/library",
            )
            filtered = publisher.filter_output_candidates_to_provenance_paths(
                local_output_root=output_root,
                output_candidates=candidates,
                provenance_paths=[provenance],
            )
            self.assertEqual(
                {candidate.local_path.resolve() for candidate in filtered},
                {declared.resolve(), provenance.resolve()},
            )

    def test_provenance_only_discovery_includes_dapper_companion_gmt(self):
        publisher = _publisher_module()
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_root = Path(temporary_directory) / "outputs"
            model = output_root / "model_one"
            model.mkdir(parents=True)
            original = model / "genesets.gmt"
            companion = model / "genesets.dapper-ids.gmt"
            unreferenced = model / "debug.tsv"
            original.write_text("legacy\tdesc\tGENE1\n", encoding="utf-8")
            companion.write_text("dapper:GeneSet.example\tdesc\tGENE1\n", encoding="utf-8")
            unreferenced.write_text("do not publish\n", encoding="utf-8")
            provenance = model / "geneset.provenance.dapper.yaml"
            provenance.write_text(
                "files:\n- id: dapper:File.companion\n  filename: genesets.dapper-ids.gmt\n",
                encoding="utf-8",
            )

            paths = publisher.extract_local_output_paths_from_provenance(provenance, output_root)
            self.assertEqual(paths, [companion.resolve()])
            self.assertNotIn(unreferenced.resolve(), paths)
