from __future__ import annotations

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from build_tissue_inputs import expanded_age_comparison_label
from run_age_binned_model import build_extractor_cmd as build_age_binned_extractor_cmd
from run_continuous_age_model import build_extractor_cmd as build_continuous_extractor_cmd
from run_continuous_age_model import gtex_tissue_signature_name


def test_expanded_age_comparison_label_uses_full_age_bins():
    assert expanded_age_comparison_label("30-39", "20-29") == "30_39_20_29"


def test_age_binned_extractor_cmd_uses_gtex_gmt_naming():
    cmd = build_age_binned_extractor_cmd(
        python_bin="python3",
        workflow_out=Path("/tmp/workflow"),
        extractor_out=Path("/tmp/extractor"),
        organism="human",
        genome_build="hg38",
        tissue_id="adipose_subcutaneous",
        settings={
            "extractor_postprocess_mode": "harmonizome",
            "extractor_score_mode": "signed_neglog10padj",
            "extractor_select": "top_k",
            "extractor_gmt_require_symbol": "true",
            "extractor_emit_small_gene_sets": "false",
            "extractor_disable_default_excludes": "false",
            "extractor_padj_max": "0.05",
            "extractor_pvalue_max": "NA",
            "extractor_min_abs_logfc": "1.0",
            "extractor_top_k": "200",
            "extractor_min_score": "NA",
            "extractor_gmt_source": "full",
            "extractor_gmt_topk_list": "200",
            "extractor_gmt_min_genes": "100",
            "extractor_gmt_max_genes": "500",
            "extractor_gmt_biotype_allowlist": "",
        },
        gtf_path=None,
        provenance_mirror_local_prefix=None,
        provenance_mirror_remote_prefix=None,
    )

    assert "--comparison_name_column" in cmd and "gmt_comparison_label" in cmd
    assert "--signature_name" in cmd and "GTEx_aging_adipose_subcutaneous" in cmd
    assert "--gmt_name_separator" in cmd and "_" in cmd
    assert "--gmt_signed_labels" in cmd and "up_dn" in cmd


def test_continuous_age_extractor_cmd_uses_gtex_tissue_names():
    cmd = build_continuous_extractor_cmd(
        python_bin="python3",
        deg_tsv=Path("/tmp/tissue_deg.tsv"),
        extractor_out=Path("/tmp/extractor"),
        organism="human",
        genome_build="hg38",
        settings={
            "EXTRACTOR_POSTPROCESS_MODE": "harmonizome",
            "EXTRACTOR_SCORE_MODE": "signed_neglog10padj",
            "EXTRACTOR_SELECT": "top_k",
            "EXTRACTOR_GMT_REQUIRE_SYMBOL": "true",
            "EXTRACTOR_EMIT_SMALL_GENE_SETS": "false",
            "EXTRACTOR_DISABLE_DEFAULT_EXCLUDES": "false",
            "EXTRACTOR_PADJ_MAX": "0.05",
            "EXTRACTOR_PVALUE_MAX": "NA",
            "EXTRACTOR_MIN_ABS_LOGFC": "1.0",
            "EXTRACTOR_TOP_K": "200",
            "EXTRACTOR_MIN_SCORE": "NA",
            "EXTRACTOR_GMT_SOURCE": "full",
            "EXTRACTOR_GMT_TOPK_LIST": "200",
            "EXTRACTOR_GMT_MIN_GENES": "100",
            "EXTRACTOR_GMT_MAX_GENES": "500",
            "EXTRACTOR_GMT_BIOTYPE_ALLOWLIST": "",
            "ANNOTATION_MODE": "none",
        },
        signature_name=gtex_tissue_signature_name("adipose_subcutaneous"),
        gtf_path=None,
        provenance_mirror_local_prefix=None,
        provenance_mirror_remote_prefix=None,
    )

    assert "--signature_name" in cmd and "GTEx_tissue_adipose_subcutaneous" in cmd
    assert "--gmt_name_separator" in cmd and "_" in cmd
    assert "--gmt_signed_labels" in cmd and "up_dn" in cmd
