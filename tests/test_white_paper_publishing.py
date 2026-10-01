from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


def _publisher_module():
    path = Path(__file__).resolve().parents[1] / "src" / "publish_library_to_s3.py"
    spec = importlib.util.spec_from_file_location("publish_library_to_s3", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WhitePaperPublishingTests(unittest.TestCase):
    def test_provenance_only_publish_keeps_white_paper_sidecars(self) -> None:
        publisher = _publisher_module()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "outputs"
            model = root / "model_one"
            model.mkdir(parents=True)
            provenance = model / "geneset.provenance.legacy.json"
            provenance.write_text(json.dumps({
                "graph": {"nodes": [
                    {"type": "File", "c2m2_properties": {"local_id": "model_one/geneset.whitepaper.md"}},
                    {"type": "File", "c2m2_properties": {"local_id": "model_one/geneset.whitepaper.pdf"}},
                    {"type": "File", "c2m2_properties": {"local_id": "model_one/secondary.whitepaper.md"}},
                ]},
            }) + "\n", encoding="utf-8")
            markdown = model / "geneset.whitepaper.md"
            pdf = model / "geneset.whitepaper.pdf"
            second_markdown = model / "secondary.whitepaper.md"
            markdown.write_text("# White paper\n", encoding="utf-8")
            pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
            second_markdown.write_text("# Second white paper\n", encoding="utf-8")

            self.assertEqual(
                publisher.extract_local_output_paths_from_provenance(provenance, root),
                [markdown.resolve(), pdf.resolve(), second_markdown.resolve()],
            )
