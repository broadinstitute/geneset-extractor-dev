"""Per-study CPTAC PTM gene-set runner: fetch -> prepare -> overlay -> extract (stdlib only)."""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cptac_selection_io as sio
import fetch_pdc_study as fetch


def engine_cmd(dig_dir: Path, python_bin: str, *args: str) -> tuple[list[str], dict]:
    cmd = [python_bin, "-m", "geneset_extractors.cli", *args]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(dig_dir) / "src")
    return cmd, env


def _run(cmd: list[str], env: dict, dig_dir: Path, log_lines: list[str]) -> None:
    log_lines.append("$ " + " ".join(shlex.quote(c) for c in cmd))
    completed = subprocess.run(
        cmd, cwd=str(dig_dir), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False
    )
    log_lines.append(completed.stdout)
    if completed.returncode != 0:
        raise subprocess.CalledProcessError(completed.returncode, cmd, output=completed.stdout)


_VARIANT_LABELS = {"none": "Unadjusted", "subtract": "ProteinAdjusted"}
_COHORT_TOKEN_SPLIT_RE = re.compile(r"[\s-]+")
_COMPARISON_STYLE = "signed_two_group"
_COMPARISON_LABEL = "tumor-versus-adjacent-normal"
_GENE_SET_PATTERN = "CPTAC_<Cohort>_<Variant>_{up,dn}"


def cohort_token(label: str) -> str:
    """Compact cohort token used in signature/gene-set names, e.g. ``"Clear Cell RCC"``
    -> ``"ClearCellRCC"``.

    Splits on whitespace/hyphen and upper-cases only the first character of each word
    (the remainder of each word is left as-is, so an already-uppercase acronym like
    "RCC" is not lower-cased). Words are then joined with no separator.

    Reused verbatim by the DIG converter's ``--signature_name`` wiring so it must stay
    a plain, dependency-free module-level function here.
    """
    words = [w for w in _COHORT_TOKEN_SPLIT_RE.split(str(label).strip()) if w]
    return "".join(w[:1].upper() + w[1:] for w in words)


def _variant_label(protein_adjustment: str) -> str:
    """Map a CDAP protein-adjustment token to the publish-style variant label.

    MUST match `_PUBLISH_VARIANT_LABELS` in the DIG `ptm_site_matrix` converter
    byte-for-byte so GMT signature names and this sidecar's `naming.variant_label`
    line up: `none` -> `Unadjusted`, `subtract` -> `ProteinAdjusted`.
    """
    token = str(protein_adjustment).strip()
    return _VARIANT_LABELS.get(token, token.capitalize() or token)


def _parse_variant_id(variant_id: str) -> dict[str, str]:
    """Parse a `key=value__key=value` variant_id (e.g. `protein_adjustment=none__gene_topk_sites=3`)."""
    parsed: dict[str, str] = {}
    for bit in str(variant_id).split("__"):
        if "=" not in bit:
            continue
        key, _, value = bit.partition("=")
        parsed[key.strip()] = value.strip()
    return parsed


def rebuild_grouped_provenance(
    *,
    dig_dir: Path,
    python_bin: str,
    extractor_dir: Path,
    workflow_graph_json: Path,
    overlay_json: Path,
    log_lines: list[str],
) -> None:
    """Merge the prepare-step workflow provenance graph into each variant's provenance.

    Mirrors MoTrPAC's rebuild_grouped_provenance: one `provenance build` per grouped
    variant so the final geneset.provenance.json carries both the ptm_prepare_public
    workflow step and the convert ptm_site_matrix step.
    """
    manifest = extractor_dir / "manifest.tsv"
    if not manifest.exists() or not workflow_graph_json.exists():
        return
    for row in sio.read_tsv(manifest):
        meta_rel = (row.get("meta_path") or "").strip()
        prov_rel = (row.get("provenance_path") or "").strip()
        if not meta_rel or not prov_rel:
            continue
        build_args = [
            "provenance", "build",
            str(extractor_dir / meta_rel),
            "--out", str(extractor_dir / prov_rel),
            "--upstream_provenance_graph_json", str(workflow_graph_json),
            "--provenance_overlay_json", str(overlay_json),
        ]
        cmd, env = engine_cmd(dig_dir, python_bin, *build_args)
        _run(cmd, env, dig_dir, log_lines)


def write_model_sidecars(
    *,
    extractor_dir: Path,
    model_id: str,
    cohort_id: str,
    cohort_label: str,
    phospho_pdc_study_id: str,
    proteome_pdc_study_id: str,
    model: dict[str, str],
) -> None:
    """Emit one full-schema geneset.model.json per variant.

    The shared refresh tool (`refresh_model_metadata_and_provenance.py`) renders model
    descriptions from `config/model_description_templates.tsv`, resolving `{model.<var>}`
    placeholders (and flattened `inputs{}`/`naming{}` keys) against this sidecar. Writing
    the full branch-standard schema here keeps CPTAC on the shared metadata tooling
    instead of a bespoke description pathway.
    """
    manifest = extractor_dir / "manifest.tsv"
    if not manifest.exists():
        return
    pflags = sio.prepare_flags(model)
    eflags = sio.extractor_flags(model)
    ptm_type = pflags.get("ptm_type", "phospho")
    for row in sio.read_tsv(manifest):
        meta_rel = (row.get("meta_path") or "").strip()
        if not meta_rel:
            continue
        variant_bits = _parse_variant_id((row.get("variant_id") or "").strip())
        protein_adjustment = variant_bits.get("protein_adjustment", "none")
        gene_topk_sites = int(variant_bits.get("gene_topk_sites", eflags.get("gene_topk_sites", "3")))
        variant_label = _variant_label(protein_adjustment)
        signature_name = f"CPTAC_{cohort_token(cohort_label)}_{variant_label}"

        payload = {
            "schema_version": "1",
            "library": "CPTAC",
            "model_id": model_id,
            "model_group": "PT",
            "model_label": f"tumor_vs_adjacent_normal_{ptm_type}",
            "workflow_name": "ptm_prepare_public",
            "extractor_name": "ptm_site_matrix",
            "parameters": {
                "ptm_type": ptm_type,
                "study_contrast": eflags.get("study_contrast", "condition_a_vs_b"),
                "condition_a": eflags.get("condition_a", "case"),
                "condition_b": eflags.get("condition_b", "control"),
                "protein_adjustment": protein_adjustment,
                "gene_topk_sites": gene_topk_sites,
                "gene_aggregation": eflags.get("gene_aggregation", "signed_topk_mean"),
                "site_select": eflags.get("select", "top_k"),
                "site_top_k": int(eflags.get("top_k", "200")),
                "score_mode": eflags.get("score_mode", "auto"),
            },
            "inputs": {
                "cohort_id": cohort_id,
                "cohort_label": cohort_label,
                "phospho_pdc_study_id": phospho_pdc_study_id,
                "proteome_pdc_study_id": proteome_pdc_study_id,
                "organism": "human",
                "genome_build": "hg38",
            },
            "naming": {
                "signature_name": signature_name,
                "variant_label": variant_label,
                "comparison_style": _COMPARISON_STYLE,
                "comparison_label": _COMPARISON_LABEL,
                "gene_set_pattern": _GENE_SET_PATTERN,
            },
        }
        sidecar = (extractor_dir / meta_rel).parent / "geneset.model.json"
        sidecar.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def run_model(
    *,
    dig_dir: str | Path,
    cohort_id: str,
    model_id: str,
    out_root: str | Path,
    config_dir: str | Path | None = None,
    offline: bool = False,
    source_dir: str | Path | None = None,
    api_cache_json: str | Path | None = None,
    python_bin: str = "python",
    write_model_only: bool = False,
) -> Path:
    dig_dir = Path(dig_dir)
    config_dir = Path(config_dir) if config_dir else sio.default_config_dir()
    studies = sio.load_study_manifest(config_dir / "study_manifest.tsv")
    models = sio.load_models(config_dir / "model_list.tsv", config_dir / "model_manifest.tsv")
    study = studies[cohort_id]
    model = models[model_id]

    cohort_out = Path(out_root) / "genesets" / cohort_id
    model_out = cohort_out / "models" / model_id
    fetch_dir = cohort_out / "fetch"
    workflow_dir = model_out / "workflow"
    extractor_dir = model_out / "extractor"

    if write_model_only:
        # Sidecar-only mode: skip fetch/prepare/overlay/extract entirely and (re)write
        # geneset.model.json against whatever variants already exist under extractor/.
        # write_model_sidecars() no-ops cleanly (returns without writing anything) when
        # extractor/manifest.tsv is absent, so this is safe to call even before a real
        # run has ever populated extractor/.
        write_model_sidecars(
            extractor_dir=extractor_dir,
            model_id=model_id,
            cohort_id=cohort_id,
            cohort_label=study["cohort_label"],
            phospho_pdc_study_id=study["phospho_pdc_study_id"],
            proteome_pdc_study_id=study["proteome_pdc_study_id"],
            model=model,
        )
        return model_out

    model_out.mkdir(parents=True, exist_ok=True)
    log_lines: list[str] = []

    # 1. fetch (cohort-level)
    fetched = fetch.run_fetch(
        cohort_id=cohort_id,
        cohort_label=study["cohort_label"],
        proteome_pdc_study_id=study["proteome_pdc_study_id"],
        phospho_pdc_study_id=study["phospho_pdc_study_id"],
        out_dir=fetch_dir,
        offline=offline,
        source_dir=source_dir,
        api_cache_json=api_cache_json,
    )

    try:
        # 2. prepare
        pflags = sio.prepare_flags(model)
        prepare_args = [
            "workflows", "ptm_prepare_public",
            "--input_mode", "cdap_files",
            "--ptm_report_tsv", str(fetched["phospho_report"]),
            "--protein_report_tsv", str(fetched["proteome_report"]),
            "--sample_annotations_tsv", str(fetched["sample_annotations"]),
            "--out_dir", str(workflow_dir),
            "--organism", "human",
            "--ptm_type", pflags.get("ptm_type", "phospho"),
            "--study_id", cohort_id,
            "--study_label", study["cohort_label"],
            "--assay_type_policy", pflags.get("assay_type_policy", "warn"),
        ]
        cmd, env = engine_cmd(dig_dir, python_bin, *prepare_args)
        _run(cmd, env, dig_dir, log_lines)

        # 3. overlay (DIG builds it from the manifest the fetch step wrote)
        overlay_args = [
            "provenance", "overlay",
            "--pdc_file_manifest_tsv", str(fetched["file_manifest"]),
            "--prepared_dir", str(workflow_dir),
            "--out_dir", str(model_out),
            "--operation_script_url",
            "https://github.com/broadinstitute/geneset-extractor-dev/blob/main/CPTAC/src/run_cptac_ptm_model.py",
        ]
        cmd, env = engine_cmd(dig_dir, python_bin, *overlay_args)
        _run(cmd, env, dig_dir, log_lines)
        overlay_json = model_out / "provenance_overlay.json"

        # 4. extract
        eflags = sio.extractor_flags(model)
        extract_args = [
            "convert", "ptm_site_matrix",
            "--ptm_matrix_tsv", str(workflow_dir / "ptm_matrix.tsv"),
            "--sample_metadata_tsv", str(workflow_dir / "sample_metadata.tsv"),
            "--protein_matrix_tsv", str(workflow_dir / "protein_matrix.tsv"),
            "--study_contrast", eflags.get("study_contrast", "condition_a_vs_b"),
            "--condition_a", eflags.get("condition_a", "case"),
            "--condition_b", eflags.get("condition_b", "control"),
            "--protein_adjustment_run_mode", eflags.get("protein_adjustment_run_mode", "compare_if_protein"),
            # CPTAC CDAP proteome reports are gene-level (no per-row protein accession), so the
            # phospho-site -> proteome subtraction must join on gene symbol. Without this the
            # converter falls back to protein_accession, which is populated (RefSeq) on the phospho
            # side but empty on the gene-level proteome side -> 0 matched sites -> subtract == none.
            "--protein_accession_column", eflags.get("protein_accession_column", "gene_symbol"),
            "--select", eflags.get("select", "top_k"),
            "--top_k", eflags.get("top_k", "200"),
            "--gene_aggregation", eflags.get("gene_aggregation", "signed_topk_mean"),
            "--out_dir", str(extractor_dir),
            "--organism", "human",
            "--genome_build", "hg38",
            "--ptm_type", pflags.get("ptm_type", "phospho"),
            "--use_reference_bundle", "false",
            "--emit_small_gene_sets", "true",
            "--provenance_overlay_json", str(overlay_json),
            "--signature_name", f"CPTAC_{cohort_token(study['cohort_label'])}",
            "--gmt_name_style", "publish",
            "--gmt_signed_labels", "up,dn",
        ]
        cmd, env = engine_cmd(dig_dir, python_bin, *extract_args)
        _run(cmd, env, dig_dir, log_lines)

        # 4b. merge the prepare-step workflow provenance graph into each variant's provenance
        rebuild_grouped_provenance(
            dig_dir=dig_dir,
            python_bin=python_bin,
            extractor_dir=extractor_dir,
            workflow_graph_json=workflow_dir / "ptm_matrix.provenance_graph.json",
            overlay_json=overlay_json,
            log_lines=log_lines,
        )

        # 5. model sidecars (description-template vars for the shared refresh tooling)
        write_model_sidecars(
            extractor_dir=extractor_dir,
            model_id=model_id,
            cohort_id=cohort_id,
            cohort_label=study["cohort_label"],
            phospho_pdc_study_id=study["phospho_pdc_study_id"],
            proteome_pdc_study_id=study["proteome_pdc_study_id"],
            model=model,
        )

        return model_out
    finally:
        (model_out / "run.log").write_text("\n".join(log_lines), encoding="utf-8")
        (model_out / "commands.md").write_text(
            "# Commands\n\n```\n" + "\n".join(l for l in log_lines if l.startswith("$ ")) + "\n```\n",
            encoding="utf-8",
        )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run one CPTAC PTM gene-set model for one cohort.")
    p.add_argument("--dig_dir", required=True)
    p.add_argument("--cohort_id", required=True)
    p.add_argument("--model_id", default="PT1")
    p.add_argument("--out_root", required=True)
    p.add_argument("--config_dir")
    p.add_argument("--offline", action="store_true")
    p.add_argument("--source_dir")
    p.add_argument("--api_cache_json")
    p.add_argument("--python_bin", default="python")
    p.add_argument(
        "--write_model_only",
        action="store_true",
        help="Skip fetch/prepare/overlay/extract; only (re)write geneset.model.json "
        "sidecars against an existing extractor/ output.",
    )
    args = p.parse_args(argv)
    model_out = run_model(
        dig_dir=args.dig_dir,
        cohort_id=args.cohort_id,
        model_id=args.model_id,
        out_root=args.out_root,
        config_dir=args.config_dir,
        offline=args.offline,
        source_dir=args.source_dir,
        api_cache_json=args.api_cache_json,
        python_bin=args.python_bin,
        write_model_only=args.write_model_only,
    )
    print(f"model_out={model_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
