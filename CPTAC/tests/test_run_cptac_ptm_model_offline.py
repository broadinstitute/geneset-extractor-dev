import csv
import json
import shutil
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
import run_cptac_ptm_model as runner  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
DIG_DIR = REPO_ROOT / "dig-gene-set-extractors"
FIX = Path(__file__).resolve().parent / "fixtures"
CONFIG = Path(__file__).resolve().parents[1] / "config"


def _api_cache(tmp_path):
    import hashlib

    def md5(p):
        return hashlib.md5(Path(p).read_bytes()).hexdigest()

    phospho = json.loads((FIX / "files_per_study.ccrcc_phospho.json").read_text())
    phospho["data"]["filesPerStudy"][0]["md5sum"] = md5(FIX / "reports" / "CCRCC_Phosphoproteome.phosphosite.tmt10.tsv")
    proteome = json.loads((FIX / "files_per_study.ccrcc_proteome.json").read_text())
    proteome["data"]["filesPerStudy"][0]["md5sum"] = md5(FIX / "reports" / "CCRCC_Proteome.tmt10.tsv")
    biospec = json.loads((FIX / "biospecimen_per_study.ccrcc.json").read_text())
    out = tmp_path / "api_cache.json"
    out.write_text(json.dumps({"phospho_files": phospho, "proteome_files": proteome, "biospecimen": biospec}))
    return out


@pytest.mark.skipif(not DIG_DIR.exists(), reason="dig-gene-set-extractors checkout not found")
def test_run_model_offline_end_to_end(tmp_path):
    out_root = tmp_path / "cptac_outputs"
    model_dir = runner.run_model(
        dig_dir=DIG_DIR,
        cohort_id="ccrcc",
        model_id="PT1",
        out_root=out_root,
        config_dir=CONFIG,
        offline=True,
        source_dir=FIX / "reports",
        api_cache_json=_api_cache(tmp_path),
        python_bin=sys.executable,
    )
    # Model output standardizes on a workflow/ dir (formerly "prepared").
    assert (Path(model_dir) / "workflow").exists()
    assert (Path(model_dir) / "workflow" / "ptm_matrix.tsv").exists()
    assert not (Path(model_dir) / "prepared").exists()

    # At least one variant dir with the 3-file contract.
    provs = list(Path(model_dir).rglob("geneset.provenance.json"))
    assert provs, "no geneset.provenance.json produced"
    for prov in provs:
        assert (prov.parent / "geneset.tsv").exists()
        assert (prov.parent / "geneset.meta.json").exists()

    # Full-schema geneset.model.json sidecar alongside each variant.
    model_jsons = list(Path(model_dir).rglob("geneset.model.json"))
    assert model_jsons, "no geneset.model.json produced"
    variant_labels = set()
    for path in model_jsons:
        payload = json.loads(path.read_text())
        assert payload["library"] == "CPTAC"
        assert payload["model_group"] == "PT"
        assert payload["workflow_name"] == "ptm_prepare_public"
        assert payload["extractor_name"] == "ptm_site_matrix"
        assert isinstance(payload["parameters"], dict)
        assert isinstance(payload["inputs"], dict)
        assert isinstance(payload["naming"], dict)
        assert payload["inputs"]["cohort_id"] == "ccrcc"
        assert payload["naming"]["variant_label"] in {"ProteinAdjusted", "Unadjusted"}
        variant_labels.add(payload["naming"]["variant_label"])
    # compare_if_protein + a matched protein matrix should emit both variants.
    assert variant_labels == {"ProteinAdjusted", "Unadjusted"}
    # The ptm_matrix.tsv File node carries the PDC phosphosite DRS id + PDC dcc_url.
    graph = json.loads(provs[0].read_text())
    graph = list(graph.values())[0] if "nodes" not in graph else graph
    file_nodes = [n for n in graph["nodes"] if n["type"] == "File" and n["name"] == "ptm_matrix.tsv"]
    assert file_nodes, "ptm_matrix.tsv File node missing"
    c = file_nodes[0]["c2m2_properties"]
    assert c["persistent_id"] == "11111111-1111-1111-1111-111111111111"
    assert c["local_id"] == "drs://dg.4DFC/11111111-1111-1111-1111-111111111111"
    assert file_nodes[0]["dcc_url"] == "https://pdc.cancer.gov/pdc/study/PDC000128"


def test_cohort_token():
    assert runner.cohort_token("Clear Cell RCC") == "ClearCellRCC"
    assert runner.cohort_token("Lung SCC") == "LungSCC"
    assert runner.cohort_token("Breast (Prospective)") == "Breast(Prospective)"


def _write_manifest(extractor_dir: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = ["variant_id", "meta_path"]
    with (extractor_dir / "manifest.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, delimiter="\t", fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_write_model_sidecars_full_schema(tmp_path):
    extractor_dir = tmp_path / "extractor"
    variant_dirs = {"none": extractor_dir / "none", "subtract": extractor_dir / "subtract"}
    for d in variant_dirs.values():
        d.mkdir(parents=True)
    _write_manifest(
        extractor_dir,
        [
            {
                "variant_id": f"protein_adjustment={adjustment}__gene_topk_sites=3",
                "meta_path": f"{d.name}/geneset.meta.json",
            }
            for adjustment, d in variant_dirs.items()
        ],
    )
    model = {
        "prepare_ptm_type": "phospho",
        "extractor_study_contrast": "condition_a_vs_b",
        "extractor_condition_a": "case",
        "extractor_condition_b": "control",
        "extractor_gene_aggregation": "signed_topk_mean",
        "extractor_select": "top_k",
        "extractor_top_k": "200",
    }

    runner.write_model_sidecars(
        extractor_dir=extractor_dir,
        model_id="PT1",
        cohort_id="ccrcc",
        cohort_label="Clear Cell RCC",
        phospho_pdc_study_id="PDC000128",
        proteome_pdc_study_id="PDC000127",
        model=model,
    )

    payloads = {}
    for adjustment, d in variant_dirs.items():
        sidecar = d / "geneset.model.json"
        assert sidecar.exists()
        payload = json.loads(sidecar.read_text())
        payloads[adjustment] = payload
        assert payload["schema_version"] == "1"
        assert payload["library"] == "CPTAC"
        assert payload["model_id"] == "PT1"
        assert payload["model_group"] == "PT"
        assert payload["workflow_name"] == "ptm_prepare_public"
        assert payload["extractor_name"] == "ptm_site_matrix"
        assert isinstance(payload["parameters"], dict)
        assert isinstance(payload["inputs"], dict)
        assert isinstance(payload["naming"], dict)
        assert payload["parameters"]["gene_topk_sites"] == 3
        assert payload["parameters"]["protein_adjustment"] == adjustment
        assert payload["inputs"]["cohort_id"] == "ccrcc"
        assert payload["inputs"]["phospho_pdc_study_id"] == "PDC000128"
        assert payload["inputs"]["proteome_pdc_study_id"] == "PDC000127"
        assert payload["naming"]["variant_label"] in {"ProteinAdjusted", "Unadjusted"}

    assert payloads["none"]["naming"]["variant_label"] == "Unadjusted"
    assert payloads["subtract"]["naming"]["variant_label"] == "ProteinAdjusted"
    assert payloads["none"]["naming"]["signature_name"] == "CPTAC_ClearCellRCC_Unadjusted"
    assert payloads["subtract"]["naming"]["signature_name"] == "CPTAC_ClearCellRCC_ProteinAdjusted"
