#!/usr/bin/env bash
# refresh_provenance_batch.sh
#
# Repairs geneset.meta.json and geneset.provenance.json for a batch of scRNA cNMF
# datasets so they are publishable:
#   - Removes local python-binary paths from geneset.meta.json
#   - Injects the scrna_cnmf_prepare provenance node with the DIG CLI command
#   - Replaces wrapper references with python -m geneset_extractors.cli calls
#
# Usage: edit the CONFIG section below, then run on the cluster.
#
# Prerequisites (one-time repo setup — already done for the CFDE scRNA_cNMF batch):
#   dig-gene-set-extractors branch cfde-geneset-deliverables >= commit 7483e29
#   geneset-extractor-dev   branch gage-add-scrna-cnmf-20260702 >= commit 10b1c8f

set -euo pipefail

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG — edit for each new batch
# ──────────────────────────────────────────────────────────────────────────────

PYBIN=/home/unix/gage/.conda/envs/gsx310/bin/python
DIG=/humgen/diabetes2/users/gage/software/dig-gene-set-extractors
REFRESH=/humgen/diabetes2/users/gage/software/geneset-extractor-dev/src/refresh_model_metadata_and_provenance.py
TEMPLATE=/humgen/diabetes2/users/gage/software/geneset-extractor-dev/scRNA_cNMF/config/model_description_templates.tsv

# Root under which each dataset lives as OUTROOT/<dataset>/models/<model_id>/
OUTROOT=/humgen/diabetes2/users/ryank/CFDE/geneset_extractors/submissions/gage/v4/scRNA_cNMF/scrna_cnmf_all_models/genesets

# Model ID used for all datasets in this batch
MODEL_ID=GP1

# Dataset table: name | matrix_url | meta_url | dataset_label
# Add one entry per dataset. Use actual S3 URLs — no abbreviations.
declare -A MATRIX_URL META_URL DATASET_LABEL

MATRIX_URL[allen_biccn_MOUSE_ctx_hpf_10x]="https://idk-etl-prod-download-bucket.s3.amazonaws.com/aibs_mouse_ctx-hpf_10x/matrix.csv"
META_URL[allen_biccn_MOUSE_ctx_hpf_10x]="https://idk-etl-prod-download-bucket.s3.amazonaws.com/aibs_mouse_ctx-hpf_10x/metadata.csv"
DATASET_LABEL[allen_biccn_MOUSE_ctx_hpf_10x]="AllenBICCN_MouseCtxHPF_10x"

MATRIX_URL[allen_biccn_human_m1_10x]="https://idk-etl-prod-download-bucket.s3.amazonaws.com/aibs_human_m1_10x/matrix.csv"
META_URL[allen_biccn_human_m1_10x]="https://idk-etl-prod-download-bucket.s3.amazonaws.com/aibs_human_m1_10x/metadata.csv"
DATASET_LABEL[allen_biccn_human_m1_10x]="AllenBICCN_HumanM1_10x"

MATRIX_URL[allen_biccn_human_ctx_smartseq]="https://idk-etl-prod-download-bucket.s3.amazonaws.com/aibs_human_ctx_smart-seq/matrix.csv"
META_URL[allen_biccn_human_ctx_smartseq]="https://idk-etl-prod-download-bucket.s3.amazonaws.com/aibs_human_ctx_smart-seq/metadata.csv"
DATASET_LABEL[allen_biccn_human_ctx_smartseq]="AllenBICCN_HumanCtx_SmartSeq"

# ──────────────────────────────────────────────────────────────────────────────
# STEP 1: Patch geneset.model.json with S3 URLs and dataset_label
# ──────────────────────────────────────────────────────────────────────────────

echo "=== Step 1: Patching geneset.model.json ==="
for DATASET in "${!MATRIX_URL[@]}"; do
    MODEL_JSON="$OUTROOT/$DATASET/models/$MODEL_ID/geneset.model.json"
    echo "  Patching $MODEL_JSON"
    $PYBIN - "$MODEL_JSON" <<EOF
import json, sys
path = sys.argv[1]
with open(path) as f:
    m = json.load(f)
m.setdefault("inputs", {})
m["inputs"]["matrix_url"]    = "${MATRIX_URL[$DATASET]}"
m["inputs"]["meta_url"]      = "${META_URL[$DATASET]}"
m["inputs"]["dataset_label"] = "${DATASET_LABEL[$DATASET]}"
m.setdefault("naming", {})
m["naming"]["dataset_label"] = "${DATASET_LABEL[$DATASET]}"
with open(path, "w") as f:
    json.dump(m, f, indent=2)
print("  patched:", path)
EOF
done

# ──────────────────────────────────────────────────────────────────────────────
# STEP 2: Run refresh (patches meta + injects DIG CLI provenance for all programs)
# ──────────────────────────────────────────────────────────────────────────────

echo ""
echo "=== Step 2: Refreshing metadata and provenance ==="
for DATASET in "${!MATRIX_URL[@]}"; do
    echo "  --- $DATASET ---"
    $PYBIN "$REFRESH" \
        --model_id "$MODEL_ID" \
        --model_dir "$OUTROOT/$DATASET/models/$MODEL_ID" \
        --dig_dir "$DIG" \
        --python_bin "$PYBIN" \
        --description_template_tsv "$TEMPLATE"
done

# ──────────────────────────────────────────────────────────────────────────────
# STEP 3: Remove .orig backups created by the refresh script
# ──────────────────────────────────────────────────────────────────────────────

echo ""
echo "=== Step 3: Removing .orig backups ==="
find "$OUTROOT" -name "*.orig" -delete
echo "  Done."

# ──────────────────────────────────────────────────────────────────────────────
# STEP 4: Verify extractor/ outputs are clean
# ──────────────────────────────────────────────────────────────────────────────

echo ""
echo "=== Step 4: Verifying extractor/ outputs ==="
DIRTY=0
for DATASET in "${!MATRIX_URL[@]}"; do
    EXTRACTOR="$OUTROOT/$DATASET/models/$MODEL_ID/extractor"
    LOCAL_HITS=$(grep -rl "/home/unix/" "$EXTRACTOR" 2>/dev/null | wc -l)
    if [[ "$LOCAL_HITS" -gt 0 ]]; then
        echo "  FAIL $DATASET: $LOCAL_HITS files still contain /home/unix/"
        grep -rl "/home/unix/" "$EXTRACTOR" | head -3
        DIRTY=1
    else
        echo "  OK   $DATASET: 0 local-path hits"
    fi

    # Spot-check: both DIG CLI commands present in program=1
    PROG1="$EXTRACTOR/program=1/geneset.provenance.json"
    if [[ -f "$PROG1" ]]; then
        CMD_COUNT=$($PYBIN -c "
import json
with open('$PROG1') as f:
    g = json.load(f)
top = list(g.keys())[0]
nodes = g[top]['nodes']
cmds = [n['analysis']['command'] for n in nodes if 'analysis' in n and 'command' in n['analysis']]
print(len(cmds))
")
        if [[ "$CMD_COUNT" -lt 2 ]]; then
            echo "  WARN $DATASET program=1: only $CMD_COUNT command node(s) in provenance (expected 2)"
            DIRTY=1
        else
            echo "  OK   $DATASET program=1: $CMD_COUNT command nodes in provenance"
        fi
    fi
done

if [[ "$DIRTY" -eq 0 ]]; then
    echo ""
    echo "All datasets clean. Ready to zip."
else
    echo ""
    echo "Some datasets still have issues — do not zip yet."
    exit 1
fi

# ──────────────────────────────────────────────────────────────────────────────
# STEP 5: Re-zip the submission (run from the parent of scrna_cnmf_all_models/)
# ──────────────────────────────────────────────────────────────────────────────

ZIP_DIR="$(dirname "$OUTROOT")"   # .../v4/scRNA_cNMF/scrna_cnmf_all_models
SUBMISSION_DIR="$(dirname "$ZIP_DIR")"  # .../v4/scRNA_cNMF

echo ""
echo "=== Step 5: Re-zipping ==="
# workflow/ is included by design (Ryan confirmed). It contains cluster-local paths
# in .sh scripts and cnmf_out intermediates — that is expected for run artifacts.
# Ryan's validator checks extractor/ outputs only.
cd "$SUBMISSION_DIR"
rm -f scrna_cnmf_all_models.zip
zip -r scrna_cnmf_all_models.zip scrna_cnmf_all_models/
echo "Done: $(du -sh scrna_cnmf_all_models.zip)"
