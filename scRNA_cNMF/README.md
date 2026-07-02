# scRNA_cNMF — CFDE Gene-Set Library

Single-cell RNA-seq gene-program library using consensus NMF (cNMF), built as a branch-standard
`geneset-extractor-dev` wrapper against the `dig-gene-set-extractors` DIG pipeline.

---

## Library choice

**scRNA_cNMF** was selected as the resubmission scope because it:

- Was previously submitted in a non-standard format (flat directory, standalone script bypassing DIG)
- Has a clearly defined DIG pipeline (`scrna_cnmf_prepare` → `cnmf` CLI → `cnmf_select_k` →
  `rna_sc_programs`) that maps cleanly onto the two-repo architecture
- Covers three publicly available NIH/BRAIN Initiative (BICCN) datasets under anonymous public access

---

## Datasets (partition dimension)

| dataset_id | Organism | Tissue | Access |
|---|---|---|---|
| `allen_biccn_human_m1_10x` | human (hg38) | Primary motor cortex (10x Chromium) | anon-public |
| `allen_biccn_human_ctx_smartseq` | human (hg38) | Multiple cortical areas (SMART-seq) | anon-public |
| `allen_biccn_MOUSE_ctx_hpf_10x` | mouse (mm10) | Cortex + hippocampus (10x Chromium) | anon-public |

Source: Allen Brain Cell Atlas / BICCN. NIH BRAIN Initiative funded.
All datasets are anonymously public (no credential wall, no controlled-access).

---

## Model

| model_id | Family | K selection | Iterations | Top genes |
|---|---|---|---|---|
| `GP1` | `cnmf_programs` | auto (largest-stable) | 100 | 100 per program |

See `config/model_manifest.tsv` for full parameter set.

---

## Output tree

```
scrna_cnmf_all_models/
  genesets/
    <dataset_id>/
      models/
        GP1/
          workflow/          # DIG intermediate files (subsets/all/cnmf_out/…)
          extractor/         # final genesets.gmt, genesets.tsv, provenance.json, …
          geneset.model.json # model sidecar (required for refresh / GMT descriptions)
```

---

## Running on the cluster

```bash
# 1. Create local-paths map (pre-downloaded matrices)
cat > scrna_input_map.tsv << 'EOF'
dataset_id	matrix_tsv	meta_tsv
allen_biccn_human_m1_10x	/path/to/m1_matrix.tsv	/path/to/m1_meta.tsv
allen_biccn_human_ctx_smartseq	/path/to/smartseq_matrix.tsv	/path/to/smartseq_meta.tsv
allen_biccn_MOUSE_ctx_hpf_10x	/path/to/mouse_matrix.tsv	/path/to/mouse_meta.tsv
EOF

# 2. Submit array jobs
APPTAINER_IMAGE=/path/to/geneset-extractor.sif \
SCRNA_INPUT_MAP_TSV=scrna_input_map.tsv \
SCRNA_OUT_ROOT=/humgen/.../scrna_cnmf_all_models \
DIG_DIR=/humgen/.../dig-gene-set-extractors \
bash run/submit_scrna_cnmf_models_cluster_apptainer.sh --submit

# 3. After jobs complete, refresh descriptions + provenance
bash run/submit_scrna_cnmf_models_cluster_apptainer.sh --refresh_metadata_and_provenance
```

See `run/submit_scrna_cnmf_models_cluster_apptainer.sh` for full env var documentation.

---

## PRs

| Repo | PR | Description |
|---|---|---|
| `broadinstitute/geneset-extractor-dev` | [#12](https://github.com/broadinstitute/geneset-extractor-dev/pull/12) | Add `scRNA_cNMF` library wrapper (this branch: `gage-add-scrna-cnmf-20260702`) |
| `flannick/dig-gene-set-extractors` | [#6](https://github.com/flannick/dig-gene-set-extractors/pull/6) | Fix `run_scrna_programs.sh` to use DIG 4-stage pipeline |

Branch pushed to fork: `sdgagephd/geneset-extractor-dev` → `gage-add-scrna-cnmf-20260702`

---

## Deferred portfolio components

The following items from the broader CFDE gene-set portfolio were out of scope for this
resubmission (already submitted or held for separate review):

| Item | Status |
|---|---|
| GTEx eQTL/sQTL, ClinVar, ClinGen, GlyGen | Previously submitted (Batches 4, 9) |
| ENCODE ATAC/DNase/histone (region-level) | Previously submitted (Batches 7–8) |
| TF ChIP / eCLIP regulons (bg-corrected) | Previously submitted (Batch 10) |
| CATLAS scATAC cell-type accessibility | Previously submitted (Batches 12–15) |
| shRNA-KD regulons | Previously submitted (Batch 5) |
| iPTMnet, CRISPR KD, gnomAD, HPO | Held — license / funding-scope pending |

---

## Architecture notes

This library follows the two-repo split standard:
- **`dig-gene-set-extractors`** owns all cNMF workflow logic (`scrna_cnmf_prepare`,
  `cnmf_select_k`, `rna_sc_programs` extractor). The DIG pipeline generates bash scripts
  that are executed in sequence; all intermediate files live under `workflow/subsets/all/`.
- **`geneset-extractor-dev`** (this repo) owns config, orchestration, and the thin Python
  wrapper (`src/run_scrna_cnmf_model.py`) that calls each DIG stage, copies final outputs to
  `extractor/`, and writes `geneset.model.json` sidecars.
- The submit script (`run/submit_scrna_cnmf_models_cluster_apptainer.sh`) generates a
  worklist by joining `dataset_list.tsv × model_list.tsv` and dispatches array jobs via
  PBS/SGE inside an Apptainer container.
