from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from submission_tools.provenance_validation import validate_provenance_complete
from submission_tools.scaffold import scaffold


def graph(artifact: str, *, source_label: str = "source_counts", broken: bool = False) -> dict:
    edges = [
        {"source": "file:input", "target": "operation:workflow"},
        {"source": "operation:workflow", "target": "geneset:result"},
        {"source": "geneset:result", "target": "file:output"},
    ]
    if broken:
        edges[-1]["target"] = "file:missing"
    return {
        "focus_node_id": "geneset:result",
        "nodes": [
            {"id": "file:input", "kind": "file", "role": "source_input", "label": source_label, "access": {"canonical_uri": "urn:test:input"}},
            {"id": "operation:workflow", "kind": "operation", "label": "DIG workflow"},
            {"id": "geneset:result", "kind": "geneset", "label": "result"},
            {"id": "file:output", "kind": "file", "role": "gmt", "label": artifact},
        ],
        "edges": edges,
    }


def dig_graph_map(artifact: str) -> dict:
    """Representative existing DIG graph-map sidecar, with no focus node."""
    value = graph(artifact)
    value.pop("focus_node_id")
    for node in value["nodes"]:
        node["type"] = {"file": "File", "operation": "AnalysisType", "geneset": "GeneSet"}[node.pop("kind")]
    return {"urn:uuid:test-provenance-graph": value}


class ProvenanceValidationTest(unittest.TestCase):
    def library(self, *, ready: bool = False) -> tuple[Path, dict]:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name) / "Library"
        scaffold(root, "Library", "Library", "generic")
        payload = json.loads((root / "submission.yaml").read_text())
        payload["submission_status"] = "ready" if ready else "draft"
        payload["provenance"] = {"contracts": [{"scope": "full", "output_manifest": "expected/provenance_output_manifest.tsv", "provenance_filename": "geneset.provenance.json", "required_input_ids": ["source_counts"]}]}
        (root / "expected/provenance_output_manifest.tsv").write_text("output_id\trelative_path\trole\trequired\tmodel_id\tpartition_id\nmain\twork/model/genesets.gmt\tgmt\ttrue\tM1\texample\n", encoding="utf-8")
        (root / "submission.yaml").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return root, payload

    def test_valid_graph_passes(self) -> None:
        root, payload = self.library()
        artifact = root / "work/model/genesets.gmt"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("set\tna\tA\n", encoding="utf-8")
        (artifact.parent / "geneset.provenance.json").write_text(json.dumps(graph(artifact.name)), encoding="utf-8")
        self.assertTrue(validate_provenance_complete(root, payload, scope="full").ok)

    def test_existing_dig_graph_map_sidecar_passes(self) -> None:
        root, payload = self.library(ready=True)
        artifact = root / "work/model/genesets.gmt"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("set\tna\tA\n", encoding="utf-8")
        (artifact.parent / "geneset.provenance.json").write_text(
            json.dumps(dig_graph_map(artifact.name)), encoding="utf-8"
        )
        self.assertTrue(validate_provenance_complete(root, payload, scope="full").ok)

    def test_empty_graph_map_is_an_error(self) -> None:
        root, payload = self.library()
        artifact = root / "work/model/genesets.gmt"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("set\tna\tA\n", encoding="utf-8")
        (artifact.parent / "geneset.provenance.json").write_text("{}", encoding="utf-8")
        result = validate_provenance_complete(root, payload, scope="full")
        self.assertFalse(result.ok)
        self.assertTrue(any(issue.code == "provenance_json" for issue in result.issues))

    def test_missing_sidecar_is_warning_for_draft_and_error_for_ready(self) -> None:
        root, payload = self.library()
        draft = validate_provenance_complete(root, payload, scope="full")
        self.assertTrue(draft.ok)
        self.assertTrue(any(issue.code == "provenance_missing" for issue in draft.issues))
        payload["submission_status"] = "ready"
        ready = validate_provenance_complete(root, payload, scope="full")
        self.assertFalse(ready.ok)

    def test_malformed_and_broken_graphs_are_errors(self) -> None:
        root, payload = self.library()
        artifact = root / "work/model/genesets.gmt"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("set\tna\tA\n", encoding="utf-8")
        sidecar = artifact.parent / "geneset.provenance.json"
        sidecar.write_text("{bad", encoding="utf-8")
        self.assertFalse(validate_provenance_complete(root, payload, scope="full").ok)
        sidecar.write_text(json.dumps(graph(artifact.name, broken=True)), encoding="utf-8")
        self.assertFalse(validate_provenance_complete(root, payload, scope="full").ok)

    def test_input_linkage_and_local_paths_are_ready_errors(self) -> None:
        root, payload = self.library(ready=True)
        artifact = root / "work/model/genesets.gmt"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("set\tna\tA\n", encoding="utf-8")
        value = graph(artifact.name, source_label="wrong_input")
        value["nodes"][0]["access"] = {"local_path": "/home/contributor/private.tsv"}
        (artifact.parent / "geneset.provenance.json").write_text(json.dumps(value), encoding="utf-8")
        result = validate_provenance_complete(root, payload, scope="full")
        self.assertFalse(result.ok)
        self.assertTrue(any(issue.code == "provenance_input_link" for issue in result.issues))
        self.assertTrue(any(issue.code == "provenance_local_path" for issue in result.issues))

    def test_workspace_derived_remote_url_is_a_ready_error(self) -> None:
        root, payload = self.library(ready=True)
        artifact = root / "work/model/genesets.gmt"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("set\tna\tA\n", encoding="utf-8")
        value = graph(artifact.name)
        value["nodes"][0]["access"] = {
            "canonical_uri": "https://api.data.igvf.org/software/geneset_extractors/adoptions/adoption_candidate/geneset-extractor-dev/IGVF/inputs/input.tsv"
        }
        (artifact.parent / "geneset.provenance.json").write_text(json.dumps(value), encoding="utf-8")
        result = validate_provenance_complete(root, payload, scope="full")
        self.assertFalse(result.ok)
        self.assertTrue(any(issue.code == "provenance_workspace_url" for issue in result.issues))


if __name__ == "__main__":
    unittest.main()
