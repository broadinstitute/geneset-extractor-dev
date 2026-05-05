from __future__ import annotations

import csv
import gzip
from pathlib import Path


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_tsv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def gzip_file(path: Path) -> None:
    with path.open("rb") as src, gzip.open(path.with_suffix(path.suffix + ".gz"), "wb") as dst:
        dst.write(src.read())


def model_provenance_md(row: dict[str, str]) -> str:
    gtf_note = ""
    if row["annotation_mode"] == "gtf_annotated":
        gtf_note = "\nThis model requires `--gtf <path_to_gtf>` when running `build_genesets.sh`.\n"
    return f"""# {row['model_id']} Provenance

## Intent

- Model: `{row['model_id']}`
- Rationale: {row['rationale']}

## Current Public Command

Run this model through the unified geneset-build entrypoint:

```bash
bash geneset-extractor-dev/GTEx/run/build_genesets.sh \\
  --tissues <tissue_id> \\
  --models {row['model_id']}{' \\\n+  --gtf <path_to_gtf>' if row['annotation_mode'] == 'gtf_annotated' else ''}
```
{gtf_note}
## Underlying Workflow Settings

- `de_mode={row['workflow_de_mode']}`
- `backend={row['workflow_backend']}`
- `balance_groups={row['workflow_balance_groups']}`
- `balance_seed={row['workflow_balance_seed']}`
- `gene_filter_scope={row['workflow_gene_filter_scope']}`
- `covariates={row['workflow_covariates']}`

## Underlying Extractor Settings

- `postprocess_mode={row['extractor_postprocess_mode']}`
- `score_mode={row['extractor_score_mode']}`
- `padj_max={row['extractor_padj_max']}`
- `pvalue_max={row['extractor_pvalue_max']}`
- `min_abs_logfc={row['extractor_min_abs_logfc']}`
- `disable_default_excludes={row['extractor_disable_default_excludes']}`
- `select={row['extractor_select']}`
- `top_k={row['extractor_top_k']}`
- `min_score={row['extractor_min_score']}`
- `gmt_source={row['extractor_gmt_source']}`
- `gmt_topk_list={row['extractor_gmt_topk_list']}`
- `gmt_min_genes={row['extractor_gmt_min_genes']}`
- `gmt_max_genes={row['extractor_gmt_max_genes']}`
- `gmt_biotype_allowlist={row['extractor_gmt_biotype_allowlist']}`
- `gmt_require_symbol={row['extractor_gmt_require_symbol']}`
- `emit_small_gene_sets={row['extractor_emit_small_gene_sets']}`
"""


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    planning_dir = repo_root / "geneset-extractor-dev/GTEx/planning/geneset_build/age_binned_models"
    provenance_dir = planning_dir / "model_provenance"
    manifest_path = planning_dir / "model_manifest.tsv"

    models = read_tsv(manifest_path)

    inventory_rows = [
        {
            "script_name": "build_genesets.sh",
            "path": "geneset-extractor-dev/GTEx/run/build_genesets.sh",
            "purpose": "build prepared GTEx inputs and selected model GMT outputs for chosen tissues and models",
        },
        {
            "script_name": "run_pigean.sh",
            "path": "geneset-extractor-dev/GTEx/run/run_pigean.sh",
            "purpose": "run PIGEAN on selected tissue/model GMT outputs",
        },
        {
            "script_name": "run_eaggl.sh",
            "path": "geneset-extractor-dev/GTEx/run/run_eaggl.sh",
            "purpose": "run EAGGL on selected tissue/model GMT outputs",
        },
        {
            "script_name": "summarize_model_enrichment.sh",
            "path": "geneset-extractor-dev/GTEx/run/summarize_model_enrichment.sh",
            "purpose": "write detailed enrichment summaries for selected tissues and models",
        },
        {
            "script_name": "summarize_top_models.sh",
            "path": "geneset-extractor-dev/GTEx/run/summarize_top_models.sh",
            "purpose": "write top-model summaries for selected tissues and models",
        },
    ]
    write_tsv(planning_dir / "run_script_inventory.tsv", inventory_rows, ["script_name", "path", "purpose"])
    gzip_file(planning_dir / "run_script_inventory.tsv")

    inventory_md_lines = ["# Age-Binned Runtime Script Inventory", ""]
    for row in inventory_rows:
        inventory_md_lines.append(f"- `{row['script_name']}`: {row['purpose']}")
        inventory_md_lines.append(f"  path: `{row['path']}`")
    write_text(planning_dir / "run_script_inventory.md", "\n".join(inventory_md_lines))

    output_manifest_rows = [
        {"file_name": "run_script_inventory.tsv.gz", "file_type": "table", "description": "inventory of current public GTEx run scripts"},
        {"file_name": "run_script_inventory.md", "file_type": "markdown", "description": "human-readable inventory of current public GTEx run scripts"},
        {"file_name": "run_summary.md", "file_type": "markdown", "description": "summary of age-binned planning and public run interfaces"},
        {"file_name": "commands.md", "file_type": "markdown", "description": "command used to regenerate this planning support bundle"},
        {"file_name": "asset_generation.log", "file_type": "log", "description": "age-binned planning asset-generation log"},
        {"file_name": "model_provenance/", "file_type": "directory", "description": "one provenance markdown file per age-binned model"},
    ]
    write_tsv(planning_dir / "output_manifest.tsv", output_manifest_rows, ["file_name", "file_type", "description"])
    gzip_file(planning_dir / "output_manifest.tsv")

    for row in models:
        write_text(provenance_dir / f"{row['model_id']}.md", model_provenance_md(row))

    write_text(
        planning_dir / "run_summary.md",
        "\n".join(
            [
                "# Age-Binned Runtime Interface Summary",
                "",
                "- Scope completed: age-binned planning support for the current unified GTEx CLI surface",
                f"- Model count covered by planning docs: `{len(models)}`",
                "- Public entrypoints described here are shared across age-binned and continuous-age workflows",
                "",
                "## Main Entry Points",
                "",
                "- `geneset-extractor-dev/GTEx/run/build_genesets.sh`",
                "- `geneset-extractor-dev/GTEx/run/run_pigean.sh`",
                "- `geneset-extractor-dev/GTEx/run/run_eaggl.sh`",
                "- `geneset-extractor-dev/GTEx/run/summarize_model_enrichment.sh`",
                "- `geneset-extractor-dev/GTEx/run/summarize_top_models.sh`",
            ]
        )
        + "\n"
    )

    write_text(
        planning_dir / "commands.md",
        "\n".join(
            [
                "# Commands Used For Age-Binned Planning Support Generation",
                "",
                "```bash",
                "python3 geneset-extractor-dev/GTEx/src/generate_age_binned_model_assets.py",
                "```",
            ]
        )
        + "\n"
    )
    write_text(
        planning_dir / "asset_generation.log",
        "\n".join(
            [
                "2026-05-05 00:00:00 EDT\tasset_generation\tread age_binned_models/model_manifest.tsv",
                "2026-05-05 00:00:00 EDT\tasset_generation\twrote run interface inventory for current public GTEx entrypoints",
                "2026-05-05 00:00:00 EDT\tasset_generation\twrote model provenance markdown files under age_binned_models/model_provenance",
                "2026-05-05 00:00:00 EDT\tasset_generation\twrote age-binned planning support manifests and summary",
            ]
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
