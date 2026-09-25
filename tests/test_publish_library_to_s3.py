from __future__ import annotations

import importlib.util
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
    def test_provenance_only_discovery_includes_dapper_companion_gmt(self):
        publisher = _publisher_module()
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_root = Path(temporary_directory) / "outputs"
            model = output_root / "model_one"
            model.mkdir(parents=True)
            original = model / "genesets.gmt"
            companion = model / "genesets.dapper-ids.gmt"
            original.write_text("legacy\tdesc\tGENE1\n", encoding="utf-8")
            companion.write_text("dapper:GeneSet.example\tdesc\tGENE1\n", encoding="utf-8")
            provenance = model / "geneset.provenance.dapper.yaml"
            provenance.write_text(
                "files:\n- id: dapper:File.companion\n  filename: genesets.dapper-ids.gmt\n",
                encoding="utf-8",
            )

            self.assertEqual(
                publisher.extract_local_output_paths_from_provenance(provenance, output_root),
                [companion.resolve()],
            )
