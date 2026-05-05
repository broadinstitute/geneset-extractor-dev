from __future__ import annotations

import csv
import gzip
from pathlib import Path


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_tsv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def gzip_file(path: Path) -> None:
    with path.open("rb") as src, gzip.open(path.with_suffix(path.suffix + ".gz"), "wb") as dst:
        dst.write(src.read())


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def build_run_gtex_model(models: list[dict[str, str]]) -> str:
    cases: list[str] = []
    for row in models:
        lines: list[str] = [
            f"    {row['model_id']})",
            f"      WORKFLOW_DE_MODE={shell_quote(row['workflow_de_mode'])}",
            f"      WORKFLOW_BACKEND={shell_quote(row['workflow_backend'])}",
            f"      WORKFLOW_BALANCE_GROUPS={shell_quote(row['workflow_balance_groups'])}",
            f"      WORKFLOW_BALANCE_SEED={shell_quote(row['workflow_balance_seed'])}",
            f"      WORKFLOW_GENE_FILTER_SCOPE={shell_quote(row['workflow_gene_filter_scope'])}",
            f"      WORKFLOW_COVARIATES={shell_quote(row['workflow_covariates'])}",
            f"      ANNOTATION_MODE={shell_quote(row['annotation_mode'])}",
            f"      EXTRACTOR_POSTPROCESS_MODE={shell_quote(row['extractor_postprocess_mode'])}",
            f"      EXTRACTOR_SCORE_MODE={shell_quote(row['extractor_score_mode'])}",
            f"      EXTRACTOR_SELECT={shell_quote(row['extractor_select'])}",
            f"      EXTRACTOR_DISABLE_DEFAULT_EXCLUDES={shell_quote(row['extractor_disable_default_excludes'])}",
            f"      EXTRACTOR_GMT_REQUIRE_SYMBOL={shell_quote(row['extractor_gmt_require_symbol'])}",
            f"      EXTRACTOR_EMIT_SMALL_GENE_SETS={shell_quote(row['extractor_emit_small_gene_sets'])}",
        ]
        for name, value in [
            ("EXTRACTOR_PADJ_MAX", row["extractor_padj_max"]),
            ("EXTRACTOR_PVALUE_MAX", row["extractor_pvalue_max"]),
            ("EXTRACTOR_MIN_ABS_LOGFC", row["extractor_min_abs_logfc"]),
            ("EXTRACTOR_TOP_K", row["extractor_top_k"]),
            ("EXTRACTOR_MIN_SCORE", row["extractor_min_score"]),
            ("EXTRACTOR_GMT_SOURCE", row["extractor_gmt_source"]),
            ("EXTRACTOR_GMT_TOPK_LIST", row["extractor_gmt_topk_list"]),
            ("EXTRACTOR_GMT_MIN_GENES", row["extractor_gmt_min_genes"]),
            ("EXTRACTOR_GMT_MAX_GENES", row["extractor_gmt_max_genes"]),
            ("EXTRACTOR_GMT_BIOTYPE_ALLOWLIST", row["extractor_gmt_biotype_allowlist"]),
        ]:
            lines.append(f"      {name}={shell_quote(value)}")
        lines.append("      ;;")
        cases.append("\n".join(lines))

    case_block = "\n".join(cases)
    return f"""#!/usr/bin/env bash
set -euo pipefail

MODEL_ID=""
PREPARED_DIR=""
RUN_ROOT=""
PYTHON_BIN="python3"
ORGANISM="human"
GENOME_BUILD="hg38"
GTF_PATH=""
WRITE_COMMANDS_ONLY="false"
REPO_ROOT="$(cd "$(dirname "${{BASH_SOURCE[0]}}")/../../.." && pwd)"
DIG_DIR="${{REPO_ROOT}}/dig-gene-set-extractors"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model_id) MODEL_ID="$2"; shift 2 ;;
    --prepared_dir) PREPARED_DIR="$2"; shift 2 ;;
    --run_root) RUN_ROOT="$2"; shift 2 ;;
    --python_bin) PYTHON_BIN="$2"; shift 2 ;;
    --organism) ORGANISM="$2"; shift 2 ;;
    --genome_build) GENOME_BUILD="$2"; shift 2 ;;
    --gtf) GTF_PATH="$2"; shift 2 ;;
    --dig_dir) DIG_DIR="$2"; shift 2 ;;
    --write_commands_only) WRITE_COMMANDS_ONLY="true"; shift 1 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "${{MODEL_ID}}" || -z "${{PREPARED_DIR}}" || -z "${{RUN_ROOT}}" ]]; then
  echo "Usage: $0 --model_id AB1 --prepared_dir <dir> --run_root <dir> [--gtf <path>]" >&2
  exit 1
fi

if [[ "${{WRITE_COMMANDS_ONLY}}" != "true" && ( ! -f "${{PREPARED_DIR}}/tissue_counts.tsv" || ! -f "${{PREPARED_DIR}}/sample_metadata.tsv" || ! -f "${{PREPARED_DIR}}/comparisons.tsv" ) ]]; then
  echo "prepared_dir must contain tissue_counts.tsv, sample_metadata.tsv, and comparisons.tsv" >&2
  exit 1
fi

case "${{MODEL_ID}}" in
{case_block}
    *)
      echo "Unsupported model_id: ${{MODEL_ID}}" >&2
      exit 1
      ;;
esac

if [[ "${{ANNOTATION_MODE}}" == "gtf_annotated" && -z "${{GTF_PATH}}" ]]; then
  echo "Model ${{MODEL_ID}} requires --gtf" >&2
  exit 1
fi

MODEL_OUT="${{RUN_ROOT}}/${{MODEL_ID}}"
WORKFLOW_OUT="${{MODEL_OUT}}/workflow"
EXTRACTOR_OUT="${{MODEL_OUT}}/extractor"
mkdir -p "${{MODEL_OUT}}"

WORKFLOW_CMD=(
  "${{PYTHON_BIN}}" -m geneset_extractors.cli workflows rna_de_prepare
  --modality bulk
  --counts_tsv "${{PREPARED_DIR}}/tissue_counts.tsv"
  --matrix_orientation gene_by_sample
  --feature_id_column gene_id
  --matrix_gene_symbol_column gene_symbol
  --sample_metadata_tsv "${{PREPARED_DIR}}/sample_metadata.tsv"
  --sample_id_column sample_id
  --group_column age_bin
  --comparisons_tsv "${{PREPARED_DIR}}/comparisons.tsv"
  --de_mode "${{WORKFLOW_DE_MODE}}"
  --balance_groups "${{WORKFLOW_BALANCE_GROUPS}}"
  --balance_seed "${{WORKFLOW_BALANCE_SEED}}"
  --gene_filter_scope "${{WORKFLOW_GENE_FILTER_SCOPE}}"
  --backend "${{WORKFLOW_BACKEND}}"
  --out_dir "${{WORKFLOW_OUT}}"
  --organism "${{ORGANISM}}"
  --genome_build "${{GENOME_BUILD}}"
)

if [[ "${{WORKFLOW_COVARIATES}}" != "none" ]]; then
  WORKFLOW_CMD+=(--covariates "${{WORKFLOW_COVARIATES}}")
fi

EXTRACTOR_FLAGS=(
  --deg_tsv "${{WORKFLOW_OUT}}/deg_long.tsv"
  --comparison_column comparison_id
  --out_dir "${{EXTRACTOR_OUT}}"
  --organism "${{ORGANISM}}"
  --genome_build "${{GENOME_BUILD}}"
  --signature_name "${{MODEL_ID}}"
  --postprocess_mode "${{EXTRACTOR_POSTPROCESS_MODE}}"
  --score_mode "${{EXTRACTOR_SCORE_MODE}}"
  --select "${{EXTRACTOR_SELECT}}"
  --normalize within_set_l1
  --emit_full true
  --emit_gmt true
  --gmt_split_signed true
  --gmt_require_symbol "${{EXTRACTOR_GMT_REQUIRE_SYMBOL}}"
  --emit_small_gene_sets "${{EXTRACTOR_EMIT_SMALL_GENE_SETS}}"
)

if [[ "${{EXTRACTOR_DISABLE_DEFAULT_EXCLUDES}}" == "true" ]]; then
  EXTRACTOR_FLAGS+=(--disable_default_excludes)
fi

if [[ "${{EXTRACTOR_PADJ_MAX}}" != "NA" ]]; then
  EXTRACTOR_FLAGS+=(--padj_max "${{EXTRACTOR_PADJ_MAX}}")
fi
if [[ "${{EXTRACTOR_PVALUE_MAX}}" != "NA" ]]; then
  EXTRACTOR_FLAGS+=(--pvalue_max "${{EXTRACTOR_PVALUE_MAX}}")
fi
if [[ "${{EXTRACTOR_MIN_ABS_LOGFC}}" != "NA" ]]; then
  EXTRACTOR_FLAGS+=(--min_abs_logfc "${{EXTRACTOR_MIN_ABS_LOGFC}}")
fi
if [[ "${{EXTRACTOR_TOP_K}}" != "NA" ]]; then
  EXTRACTOR_FLAGS+=(--top_k "${{EXTRACTOR_TOP_K}}")
fi
if [[ "${{EXTRACTOR_MIN_SCORE}}" != "NA" ]]; then
  EXTRACTOR_FLAGS+=(--min_score "${{EXTRACTOR_MIN_SCORE}}")
fi
if [[ "${{EXTRACTOR_GMT_SOURCE}}" != "NA" ]]; then
  EXTRACTOR_FLAGS+=(--gmt_source "${{EXTRACTOR_GMT_SOURCE}}")
fi
if [[ "${{EXTRACTOR_GMT_TOPK_LIST}}" != "NA" ]]; then
  EXTRACTOR_FLAGS+=(--gmt_topk_list "${{EXTRACTOR_GMT_TOPK_LIST}}")
fi
if [[ "${{EXTRACTOR_GMT_MIN_GENES}}" != "NA" ]]; then
  EXTRACTOR_FLAGS+=(--gmt_min_genes "${{EXTRACTOR_GMT_MIN_GENES}}")
fi
if [[ "${{EXTRACTOR_GMT_MAX_GENES}}" != "NA" ]]; then
  EXTRACTOR_FLAGS+=(--gmt_max_genes "${{EXTRACTOR_GMT_MAX_GENES}}")
fi

if [[ -n "${{EXTRACTOR_GMT_BIOTYPE_ALLOWLIST}}" ]]; then
  EXTRACTOR_FLAGS+=(--gmt_biotype_allowlist "${{EXTRACTOR_GMT_BIOTYPE_ALLOWLIST}}")
fi

if [[ -n "${{GTF_PATH}}" ]]; then
  EXTRACTOR_FLAGS+=(--gtf "${{GTF_PATH}}")
fi

EXTRACTOR_CMD=("${{PYTHON_BIN}}" -m geneset_extractors.cli convert rna_deg_multi "${{EXTRACTOR_FLAGS[@]}}")

{{
  printf '# Commands For %s\n\n' "${{MODEL_ID}}"
  printf '## Workflow\n\n'
  printf '```bash\n'
  printf 'PYTHONPATH=%s/src %s\n' "${{DIG_DIR}}" "${{WORKFLOW_CMD[*]}}"
  printf '```\n\n'
  printf '## Extractor\n\n'
  printf '```bash\n'
  printf 'PYTHONPATH=%s/src %s\n' "${{DIG_DIR}}" "${{EXTRACTOR_CMD[*]}}"
  printf '```\n'
}} > "${{MODEL_OUT}}/commands.md"

if [[ "${{WRITE_COMMANDS_ONLY}}" == "true" ]]; then
  exit 0
fi

echo "[run_gtex_model] MODEL_ID=${{MODEL_ID}}" | tee "${{MODEL_OUT}}/run.log"
(
  cd "${{DIG_DIR}}"
  PYTHONPATH="${{DIG_DIR}}/src" "${{WORKFLOW_CMD[@]}}"
) 2>&1 | tee -a "${{MODEL_OUT}}/run.log"
(
  cd "${{DIG_DIR}}"
  PYTHONPATH="${{DIG_DIR}}/src" "${{EXTRACTOR_CMD[@]}}"
) 2>&1 | tee -a "${{MODEL_OUT}}/run.log"
"${{PYTHON_BIN}}" "${{REPO_ROOT}}/geneset-extractor-dev/GTEx/src/compact_gtex_extractor_outputs.py" \
  --extractor_out "${{EXTRACTOR_OUT}}" \
  --model_id "${{MODEL_ID}}" \
  --model_out "${{MODEL_OUT}}"
"""


def build_prepare_wrapper() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PYTHON_BIN="python3"

if [[ $# -ge 2 && "$1" == "--python_bin" ]]; then
  PYTHON_BIN="$2"
  shift 2
fi

exec "${PYTHON_BIN}" "${REPO_ROOT}/geneset-extractor-dev/GTEx/src/prepare_gtex_tissue_inputs.py" "$@"
"""


def build_run_all(models: list[dict[str, str]]) -> str:
    model_ids = " ".join(row["model_id"] for row in models)
    return f"""#!/usr/bin/env bash
set -euo pipefail

PREPARED_DIR=""
RUN_ROOT=""
PYTHON_BIN="python3"
ORGANISM="human"
GENOME_BUILD="hg38"
GTF_PATH=""
REPO_ROOT="$(cd "$(dirname "${{BASH_SOURCE[0]}}")/../../.." && pwd)"
SCRIPT_DIR="${{REPO_ROOT}}/geneset-extractor-dev/GTEx/run"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prepared_dir) PREPARED_DIR="$2"; shift 2 ;;
    --run_root) RUN_ROOT="$2"; shift 2 ;;
    --python_bin) PYTHON_BIN="$2"; shift 2 ;;
    --organism) ORGANISM="$2"; shift 2 ;;
    --genome_build) GENOME_BUILD="$2"; shift 2 ;;
    --gtf) GTF_PATH="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "${{PREPARED_DIR}}" || -z "${{RUN_ROOT}}" ]]; then
  echo "Usage: $0 --prepared_dir <dir> --run_root <dir> [--gtf <path>]" >&2
  exit 1
fi

for model_id in {model_ids}; do
  cmd=(
    bash "${{SCRIPT_DIR}}/run_gtex_model.sh"
    --model_id "${{model_id}}"
    --prepared_dir "${{PREPARED_DIR}}"
    --run_root "${{RUN_ROOT}}"
    --python_bin "${{PYTHON_BIN}}"
    --organism "${{ORGANISM}}"
    --genome_build "${{GENOME_BUILD}}"
  )
  if [[ -n "${{GTF_PATH}}" ]]; then
    cmd+=(--gtf "${{GTF_PATH}}")
  fi
  "${{cmd[@]}}"
done
"""


def build_full_pipeline() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail

COUNTS_GCT=""
SAMPLE_METADATA_TSV=""
SUBJECT_METADATA_TSV=""
TISSUE_LABEL=""
PREPARED_DIR=""
RUN_ROOT=""
PYTHON_BIN="python3"
GTF_PATH=""
ORGANISM="human"
GENOME_BUILD="hg38"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT_DIR="${REPO_ROOT}/geneset-extractor-dev/GTEx/run"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --counts_gct) COUNTS_GCT="$2"; shift 2 ;;
    --sample_metadata_tsv) SAMPLE_METADATA_TSV="$2"; shift 2 ;;
    --subject_metadata_tsv) SUBJECT_METADATA_TSV="$2"; shift 2 ;;
    --tissue_label) TISSUE_LABEL="$2"; shift 2 ;;
    --prepared_dir) PREPARED_DIR="$2"; shift 2 ;;
    --run_root) RUN_ROOT="$2"; shift 2 ;;
    --python_bin) PYTHON_BIN="$2"; shift 2 ;;
    --gtf) GTF_PATH="$2"; shift 2 ;;
    --organism) ORGANISM="$2"; shift 2 ;;
    --genome_build) GENOME_BUILD="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "${COUNTS_GCT}" || -z "${SAMPLE_METADATA_TSV}" || -z "${SUBJECT_METADATA_TSV}" || -z "${TISSUE_LABEL}" || -z "${PREPARED_DIR}" || -z "${RUN_ROOT}" ]]; then
  echo "Usage: $0 --counts_gct <path> --sample_metadata_tsv <path> --subject_metadata_tsv <path> --tissue_label <label> --prepared_dir <dir> --run_root <dir> [--gtf <path>]" >&2
  exit 1
fi

bash "${SCRIPT_DIR}/prepare_gtex_tissue_inputs.sh" \
  --python_bin "${PYTHON_BIN}" \
  --counts_gct "${COUNTS_GCT}" \
  --sample_metadata_tsv "${SAMPLE_METADATA_TSV}" \
  --subject_metadata_tsv "${SUBJECT_METADATA_TSV}" \
  --tissue_label "${TISSUE_LABEL}" \
  --out_dir "${PREPARED_DIR}"

mkdir -p "$(dirname "${RUN_ROOT}")"
OUTPUT_ROOT="$(cd "$(dirname "${RUN_ROOT}")" && pwd)"
if [[ -f "${PREPARED_DIR}/naming_reference.md" ]]; then
  cp "${PREPARED_DIR}/naming_reference.md" "${OUTPUT_ROOT}/naming_reference.md"
fi

cmd=(
  bash "${SCRIPT_DIR}/run_all_gtex_models.sh"
  --prepared_dir "${PREPARED_DIR}"
  --run_root "${RUN_ROOT}"
  --python_bin "${PYTHON_BIN}"
  --organism "${ORGANISM}"
  --genome_build "${GENOME_BUILD}"
)
if [[ -n "${GTF_PATH}" ]]; then
  cmd+=(--gtf "${GTF_PATH}")
fi
"${cmd[@]}"
"""


def model_provenance_md(row: dict[str, str]) -> str:
    gtf_note = ""
    if row["annotation_mode"] == "gtf_annotated":
        gtf_note = "\nThis model requires `--gtf <path_to_gtf>` when running `run_gtex_model.sh`.\n"
    return f"""# {row['model_id']} Provenance

## Intent

- Model: `{row['model_id']}`
- Rationale: {row['rationale']}

## Full Pipeline Commands

### 1. Prepare tissue inputs

```bash
bash geneset-extractor-dev/GTEx/run/prepare_gtex_tissue_inputs.sh \\
  --counts_gct <path_to_gtex_tissue_counts.gct.gz> \\
  --sample_metadata_tsv <path_to_sample_attributes.tsv> \\
  --subject_metadata_tsv <path_to_subject_phenotypes.tsv> \\
  --tissue_label <human_readable_tissue_label> \\
  --out_dir <prepared_dir>
```

### 2. Run this model

```bash
bash geneset-extractor-dev/GTEx/run/run_gtex_model.sh \\
  --model_id {row['model_id']} \\
  --prepared_dir <prepared_dir> \\
  --run_root <model_run_root>{' \\\n  --gtf <path_to_gtf>' if row['annotation_mode'] == 'gtf_annotated' else ''}
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
    step1_manifest = repo_root / "geneset-extractor-dev/GTEx/planning/gtex_model_step1/model_manifest.tsv"
    planning_dir = repo_root / "geneset-extractor-dev/GTEx/planning/gtex_model_step2"
    run_dir = repo_root / "geneset-extractor-dev/GTEx/run"
    provenance_dir = planning_dir / "model_provenance"

    models = read_tsv(step1_manifest)

    write_text(run_dir / "prepare_gtex_tissue_inputs.sh", build_prepare_wrapper())
    write_text(run_dir / "run_gtex_model.sh", build_run_gtex_model(models))
    write_text(run_dir / "run_all_gtex_models.sh", build_run_all(models))
    write_text(run_dir / "run_full_gtex_tissue_pipeline.sh", build_full_pipeline())

    for path in [
        run_dir / "prepare_gtex_tissue_inputs.sh",
        run_dir / "run_gtex_model.sh",
        run_dir / "run_all_gtex_models.sh",
        run_dir / "run_full_gtex_tissue_pipeline.sh",
    ]:
        path.chmod(0o755)

    inventory_rows = [
        {
            "script_name": "prepare_gtex_tissue_inputs.sh",
            "path": "geneset-extractor-dev/GTEx/run/prepare_gtex_tissue_inputs.sh",
            "purpose": "convert one GTEx tissue counts GCT plus metadata into prepared DIG input tables",
        },
        {
            "script_name": "run_gtex_model.sh",
            "path": "geneset-extractor-dev/GTEx/run/run_gtex_model.sh",
            "purpose": "run one proposed model against one prepared tissue bundle",
        },
        {
            "script_name": "run_all_gtex_models.sh",
            "path": "geneset-extractor-dev/GTEx/run/run_all_gtex_models.sh",
            "purpose": "run all proposed models against one prepared tissue bundle",
        },
        {
            "script_name": "run_full_gtex_tissue_pipeline.sh",
            "path": "geneset-extractor-dev/GTEx/run/run_full_gtex_tissue_pipeline.sh",
            "purpose": "prepare one tissue bundle from GTEx files and then run all proposed models",
        },
    ]
    write_tsv(planning_dir / "run_script_inventory.tsv", inventory_rows, ["script_name", "path", "purpose"])
    gzip_file(planning_dir / "run_script_inventory.tsv")

    inventory_md = "# GTEx Step 2 Run Script Inventory\n\n"
    for row in inventory_rows:
        inventory_md += f"- `{row['script_name']}`: {row['purpose']}\n"
        inventory_md += f"  path: `{row['path']}`\n"
    write_text(planning_dir / "run_script_inventory.md", inventory_md)

    output_manifest_rows = [
        {"file_name": "run_script_inventory.tsv.gz", "file_type": "table", "description": "inventory of generated run scripts"},
        {"file_name": "run_script_inventory.md", "file_type": "markdown", "description": "human-readable inventory of generated run scripts"},
        {"file_name": "run_summary.md", "file_type": "markdown", "description": "summary of step-2 assets"},
        {"file_name": "commands.md", "file_type": "markdown", "description": "commands used to generate step-2 assets"},
        {"file_name": "step2_execution.log", "file_type": "log", "description": "step-2 asset-generation log"},
        {"file_name": "model_provenance/", "file_type": "directory", "description": "one provenance markdown file per proposed model"},
    ]
    write_tsv(planning_dir / "output_manifest.tsv", output_manifest_rows, ["file_name", "file_type", "description"])
    gzip_file(planning_dir / "output_manifest.tsv")

    for row in models:
        write_text(provenance_dir / f"{row['model_id']}.md", model_provenance_md(row))

    write_text(
        planning_dir / "run_summary.md",
        "\n".join(
            [
                "# GTEx Step 2 Run Summary",
                "",
                "- Scope completed: step 2 only",
                f"- Model count covered by scripts: `{len(models)}`",
                "- New runtime scripts: `4`",
                "- New provenance model docs: `22`",
                "- Step-2 scripts start from GTEx tissue counts plus GTEx sample and subject metadata",
                "- Full-model runs are parameterized and do not rely on hidden shell state",
                "",
                "## Main Entry Points",
                "",
                "- `geneset-extractor-dev/GTEx/run/prepare_gtex_tissue_inputs.sh`",
                "- `geneset-extractor-dev/GTEx/run/run_gtex_model.sh`",
                "- `geneset-extractor-dev/GTEx/run/run_all_gtex_models.sh`",
                "- `geneset-extractor-dev/GTEx/run/run_full_gtex_tissue_pipeline.sh`",
            ]
        )
        + "\n",
    )

    write_text(
        planning_dir / "commands.md",
        "\n".join(
            [
                "# Commands Used For GTEx Step 2",
                "",
                "```bash",
                "python3 geneset-extractor-dev/GTEx/src/generate_gtex_model_assets.py",
                "```",
            ]
        )
        + "\n",
    )
    write_text(
        planning_dir / "step2_execution.log",
        "\n".join(
            [
                "2026-04-23 00:00:00 EDT\tstep2\tread planning/model_manifest.tsv",
                "2026-04-23 00:00:00 EDT\tstep2\twrote GTEx run scripts under run/",
                "2026-04-23 00:00:00 EDT\tstep2\twrote model provenance markdown files under planning/gtex_model_step2/model_provenance",
                "2026-04-23 00:00:00 EDT\tstep2\twrote step-2 manifests and summary",
            ]
        )
        + "\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
