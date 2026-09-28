from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def load_refresh_module():
    path = Path(__file__).resolve().parents[1] / "src" / "refresh_model_metadata_and_provenance.py"
    spec = importlib.util.spec_from_file_location("refresh_model_metadata_and_provenance", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REFRESH = load_refresh_module()


class ProvenanceRefreshTest(unittest.TestCase):
    def test_current_paired_sidecars_are_preferred_and_snapshotted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            metadata = directory / "geneset.meta.json"
            metadata.write_text("{}\n", encoding="utf-8")
            legacy, dapper, transitional = REFRESH.provenance_sidecar_paths(metadata)
            legacy.write_text('{"path": "/local/input.tsv"}\n', encoding="utf-8")
            dapper.write_text("gene_sets: []\n", encoding="utf-8")
            transitional.write_text('{"old": true}\n', encoding="utf-8")

            REFRESH.snapshot_originals([metadata])

            self.assertEqual(REFRESH.active_provenance_path(metadata), legacy)
            self.assertEqual(REFRESH.provenance_snapshot_path(metadata), Path(f"{legacy}.orig"))
            self.assertTrue(Path(f"{legacy}.orig").exists())
            self.assertTrue(Path(f"{dapper}.orig").exists())
            self.assertTrue(Path(f"{transitional}.orig").exists())
            REFRESH.rewrite_metadata_and_provenance(
                metadata_paths=[metadata], rewrite_passes=[{"/local": "https://example.org"}]
            )
            self.assertIn("https://example.org", legacy.read_text(encoding="utf-8"))
            self.assertIn("/local/input.tsv", Path(f"{legacy}.orig").read_text(encoding="utf-8"))

    def test_dapper_regeneration_uses_final_legacy_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            metadata = directory / "geneset.meta.json"
            metadata.write_text('{"gene_set": {"name": "example"}}\n', encoding="utf-8")
            legacy, dapper, _transitional = REFRESH.provenance_sidecar_paths(metadata)
            legacy.write_text('{"graph": {"nodes": []}}\n', encoding="utf-8")
            dig_dir = directory / "dig"; converter_path = dig_dir / "src/geneset_extractors/core/dapper_provenance.py"
            converter_path.parent.mkdir(parents=True)
            converter_path.write_text("# fake converter\n", encoding="utf-8")
            observed: dict[str, object] = {}

            def write_dapper(output: Path, provenance: dict, meta: dict) -> None:
                observed["provenance"] = provenance
                observed["metadata"] = meta
                output.write_text("gene_sets: []\n", encoding="utf-8")

            converter = SimpleNamespace(__file__=str(converter_path), write_dapper_provenance=write_dapper)
            with patch.object(REFRESH.importlib, "import_module", return_value=converter):
                REFRESH.regenerate_dapper_sidecars(metadata_paths=[metadata], dig_dir=dig_dir)

            self.assertEqual(observed["provenance"], {"graph": {"nodes": []}})
            self.assertTrue(dapper.exists())

    def test_refresh_regenerates_white_paper_when_declared_dig_support_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            metadata = directory / "geneset.meta.json"
            metadata.write_text('{"gene_set": {"name": "example"}}\n', encoding="utf-8")
            legacy, dapper, _transitional = REFRESH.provenance_sidecar_paths(metadata)
            legacy.write_text('{"graph": {"nodes": []}}\n', encoding="utf-8")
            dig_dir = directory / "dig"
            core = dig_dir / "src/geneset_extractors/core"
            core.mkdir(parents=True)
            converter_path = core / "dapper_provenance.py"
            white_paper_path = core / "white_paper.py"
            converter_path.write_text("# fake converter\n", encoding="utf-8")
            white_paper_path.write_text("# fake white-paper module\n", encoding="utf-8")
            observed: dict[str, object] = {}

            def write_dapper(output: Path, provenance: dict, meta: dict) -> None:
                output.write_text("gene_sets: []\n", encoding="utf-8")

            def write_white_paper(path: Path) -> None:
                observed["white_paper_metadata"] = path

            converter = SimpleNamespace(__file__=str(converter_path), write_dapper_provenance=write_dapper)
            white_paper = SimpleNamespace(
                __file__=str(white_paper_path),
                write_white_paper_from_metadata=write_white_paper,
            )
            with patch.object(
                REFRESH.importlib,
                "import_module",
                side_effect=lambda name: converter if name.endswith("dapper_provenance") else white_paper,
            ):
                REFRESH.regenerate_dapper_sidecars(metadata_paths=[metadata], dig_dir=dig_dir)

            self.assertEqual(observed["white_paper_metadata"], metadata)
