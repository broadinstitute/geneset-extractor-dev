#!/usr/bin/env python3
"""Write the geneset.model.json sidecar for a KidsFirst harmonizome-DE model.

This is the config-driven model runner for the KidsFirst library. It mirrors the
per-library runners used by GTEx/MoTrPAC (e.g. run_motrpac_*_model.py): given a
model_id and comparison_id it resolves the model parameters and comparison labels
from config/ and writes a branch-standard geneset.model.json into the model's
extractor/ directory.

Only --write_model_only is supported here: the differential-expression workflow
itself is run by the DIG rna_de_prepare workflow and the rna_deg_multi extractor
(see run/sbatch_*.sh). This runner produces the model sidecar consumed by the
shared refresh_model_metadata_and_provenance flow.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

SCHEMA_VERSION = "1.0.0"
WORKFLOW_NAME = "rna_de_prepare"
EXTRACTOR_NAME = "rna_deg_multi"

# HZ2 (curated disease-up): partition -> (source comparisons, concordance strategy).
# Only KF-TALL uses concordance across two controls; every other disease uses its single control.
HZ2_SOURCES = {
    "KF-TALL-vs-T21": (["KF-TALL-vs-T21", "KF-TALL-vs-GTEx"], "intersection"),
}


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def lookup(rows: list[dict[str, str]], key_field: str, key_value: str) -> dict[str, str]:
    for row in rows:
        if str(row.get(key_field, "")).strip() == key_value:
            return row
    raise SystemExit(f"No row with {key_field}={key_value!r} found")


def parse_numeric_or_none(value: str):
    text = str(value).strip()
    if text == "" or text.upper() == "NA":
        return None
    try:
        if "." in text or "e" in text.lower():
            return float(text)
        return int(text)
    except ValueError:
        return text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write geneset.model.json for a KidsFirst model.")
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--comparison_id", required=True)
    parser.add_argument(
        "--run_root",
        required=True,
        help="Models root: <run_root>/<model_id>/extractor/geneset.model.json is written.",
    )
    parser.add_argument(
        "--config_dir",
        default=str(Path(__file__).resolve().parent.parent / "config"),
        help="KidsFirst config/ directory (defaults to the library config).",
    )
    parser.add_argument("--write_model_only", action="store_true")
    # Accepted for parity with other library runners; unused for model-only writes.
    parser.add_argument("--python_bin")
    parser.add_argument("--dig_dir")
    return parser.parse_args()


def build_model_payload(
    *,
    model_id: str,
    comparison_id: str,
    config_dir: Path,
) -> dict[str, object]:
    model_list = read_tsv(config_dir / "model_list.tsv")
    manifest = read_tsv(config_dir / "model_manifest.tsv")
    comparisons = read_tsv(config_dir / "comparison_list.tsv")
    templates = read_tsv(config_dir / "model_description_templates.tsv")

    model_row = lookup(model_list, "model_id", model_id)
    manifest_row = lookup(manifest, "model_id", model_id)
    comparison_row = lookup(comparisons, "comparison_id", comparison_id)
    template_row = lookup(templates, "model_id", model_id)

    model_group = str(model_row.get("model_family", "")).strip()
    tumor_label = str(comparison_row.get("tumor_label", "")).strip()
    reference_label = str(comparison_row.get("reference_label", "")).strip()
    disease_label = str(comparison_row.get("disease_label", "")).strip()
    tumor_study = str(comparison_row.get("tumor_study", "")).strip()

    if model_id == "HZ2":
        sources, strategy = HZ2_SOURCES.get(comparison_id, ([comparison_id], "single"))
        return {
            "schema_version": SCHEMA_VERSION,
            "library": "KidsFirst",
            "model_id": model_id,
            "model_group": model_group,
            "model_label": f"KidsFirst curated disease-up — {disease_label}",
            "workflow_name": WORKFLOW_NAME,
            "extractor_name": "kidsfirst_curate",
            "inputs": {
                "comparison_label": comparison_id,
                "tumor_label": tumor_label,
                "reference_label": reference_label,
                "disease_label": disease_label,
                "tumor_study": tumor_study,
                "source_comparisons": sources,
            },
            "parameters": {
                "de_backend": str(manifest_row.get("de_backend", "")).strip(),
                "de_padj_max": parse_numeric_or_none(manifest_row.get("de_padj_max", "")),
                "de_min_abs_logfc": parse_numeric_or_none(manifest_row.get("de_min_abs_logfc", "")),
                "extractor_preset": None,
                "concordance_strategy": strategy,
                "score_threshold": parse_numeric_or_none(manifest_row.get("score_threshold", "")),
                "safety_cap": parse_numeric_or_none(manifest_row.get("safety_cap", "")),
            },
            "naming": {
                "gmt_up_name": f"KidsFirst_{comparison_id}_DiseaseUp",
                "description_template": model_id,
            },
        }

    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "library": "KidsFirst",
        "model_id": model_id,
        "model_group": model_group,
        "model_label": f"KidsFirst harmonizome DE — {comparison_id}",
        "workflow_name": WORKFLOW_NAME,
        "extractor_name": EXTRACTOR_NAME,
        "inputs": {
            "comparison_label": comparison_id,
            "tumor_label": tumor_label,
            "reference_label": reference_label,
            "disease_label": disease_label,
            "tumor_study": tumor_study,
        },
        "parameters": {
            "de_backend": str(manifest_row.get("de_backend", "")).strip(),
            "de_padj_max": parse_numeric_or_none(manifest_row.get("de_padj_max", "")),
            "de_min_abs_logfc": parse_numeric_or_none(manifest_row.get("de_min_abs_logfc", "")),
            "extractor_preset": str(manifest_row.get("extractor_preset", "")).strip(),
            "concordance_strategy": str(manifest_row.get("concordance_strategy", "")).strip(),
            "score_threshold": parse_numeric_or_none(manifest_row.get("score_threshold", "")),
            "safety_cap": parse_numeric_or_none(manifest_row.get("safety_cap", "")),
        },
        "naming": {
            "gmt_up_name": f"KidsFirst_{comparison_id}_up",
            "gmt_dn_name": f"KidsFirst_{comparison_id}_dn",
            "description_template": model_id,
        },
    }
    return payload


def main() -> int:
    args = parse_args()
    config_dir = Path(args.config_dir).resolve()
    payload = build_model_payload(
        model_id=args.model_id,
        comparison_id=args.comparison_id,
        config_dir=config_dir,
    )
    extractor_dir = Path(args.run_root).resolve() / args.model_id / "extractor"
    extractor_dir.mkdir(parents=True, exist_ok=True)
    out_path = extractor_dir / "geneset.model.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
