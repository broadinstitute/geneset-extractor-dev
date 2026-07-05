# KidsFirst Pediatric Cancer Gene Sets

Author: KidsFirst submission team

Differential expression analysis and gene set extraction for pediatric cancers using
KidsFirst PBTA, CBTN, and GTEx data. Packaged as a branch-standard library: harmonizome-style
differential-expression gene sets (model `HZ1`) and curated disease-up gene sets (model `HZ2`)
under the shared `<library>_all_models` layout.

**Repository split (two-repo standard):** the reusable workflow/extractor logic lives in
`dig-gene-set-extractors` — `workflows kidsfirst_prepare` (tumor/normal matrix prep), `workflows
rna_de_prepare` (limma-voom DE), `workflows kidsfirst_curate` (HZ2 disease-up curation), and the
`rna_deg_multi` converter. This `KidsFirst/` directory is the config + orchestration wrapper
(models, comparisons, submit scripts, model-sidecar/refresh).

---

## Data Sources

### Tumor cohorts

| Cohort | Disease | N |
|--------|---------|---|
| KF-TALL | T-cell Acute Lymphoblastic Leukemia | 1,026 |
| KF-NBL | Neuroblastoma | 207 |
| KF-ESGR | Ewing Sarcoma | 77 |
| KF-MMC | Acute Myeloid Leukemia | 58 |
| CBTN | Pediatric brain tumors (7 diagnoses) | 60–408 per diagnosis |

Source: KidsFirst Data Resource Center (Gabriella Miller Kids First Pediatric Research Program)
and Children's Brain Tumor Network (CBTN). RNA-seq quantified with RSEM, hg38/GENCODE.

### Normal reference cohorts

Pediatric normal RNA-seq is not available for most of these tumor types. GTEx v10 adult tissue
is used as the normal reference. KF-CHDALL (Down syndrome pediatric blood, N=400) is used as an
additional internal control for T-ALL to allow a pipeline-matched and age-matched comparison.

| GTEx tissue | Used for |
|-------------|----------|
| Whole Blood | T-ALL, AML |
| Adrenal Gland | Neuroblastoma |
| Muscle - Skeletal | Ewing Sarcoma |
| Brain - Cortex | CBTN brain tumors |

GTEx donors are adults (ages 20–79). GTEx is quantified with RNASeQC; count-level integration
with RSEM is performed at the raw count level on shared hg38 gene coordinates.

---

## Comparisons (partitions)

Each comparison is one partition under `genesets/<comparison>/`.

### KidsFirst (6 comparisons)

| Comparison ID | Tumor | Normal |
|---|---|---|
| KF-TALL-vs-T21 | T-ALL | KF-CHDALL (Down syndrome blood, pediatric) |
| KF-TALL-vs-GTEx | T-ALL | GTEx Whole Blood |
| KF-NBL-vs-adrenal | Neuroblastoma | GTEx Adrenal Gland |
| KF-ESGR-vs-muscle | Ewing Sarcoma | GTEx Skeletal Muscle |
| KF-MMC-vs-blood | AML | GTEx Whole Blood |
| KF-BLOOD-vs-normal | Pan-blood cancer (T-ALL + AML) | GTEx Whole Blood |

Tumor-vs-tumor contrasts explored during analysis (KF-TALL-vs-MMC lineage contrast, KF-BLOOD-vs-SOLID blood/solid discriminator) are not part of this delivery.

### CBTN (7 comparisons, each vs GTEx Brain - Cortex)

| Comparison ID | Tumor | N |
|---|---|---|
| CBTN-low_grade_glioma-vs-brain_cortex | Low-grade glioma | 408 |
| CBTN-malignant_glioma-vs-brain_cortex | Malignant glioma | 278 |
| CBTN-medulloblastoma-vs-brain_cortex | Medulloblastoma | 213 |
| CBTN-ependymoma-vs-brain_cortex | Ependymoma | 176 |
| CBTN-ganglioglioma-vs-brain_cortex | Ganglioglioma | 75 |
| CBTN-craniopharyngioma-vs-brain_cortex | Craniopharyngioma | 74 |
| CBTN-atypical_teratoid_rhabdoid_tumor-vs-brain_cortex | ATRT | 60 |

DE method: limma-voom, two-group (tumor vs normal).

---

## Models

Two published models, both under the shared `<partition>/models/<model_id>/` layout. A partition
(comparison) may carry both models: HZ1 for all 13 comparisons, HZ2 for the 11 disease partitions.

### HZ1 — harmonizome differential expression

Generated with the DIG `rna_de_prepare` workflow (limma-voom DE) followed by the `rna_deg_multi`
extractor using the harmonizome preset. Available for all 13 comparisons.

- Criteria: padj < 0.05, |logFC| ≥ 1
- Emits an upregulated (`_up`) and a downregulated (`_dn`) gene set per comparison
- Harmonizome-style ranked selection

### HZ2 — curated disease-up

Curated pediatric-cancer disease-up gene sets generated with the DIG `kidsfirst_curate` workflow:
for each disease, concordant tumor-up genes across the configured control(s), filtered by mean
signed_neglog10padj (threshold 2.0 ≈ padj < 0.01) and capped at 200 genes. Available for 11
diseases (KF-TALL takes the concordance across both the T21 pediatric and GTEx controls; the others
use their single control).

- Criteria: padj < 0.05, |logFC| ≥ 1, control-concordance, mean signed_neglog10padj ≥ 2.0, cap 200
- Emits one disease-up gene set per disease; lives under the disease's primary comparison partition
  (e.g. `KF-ESGR-vs-muscle/models/HZ2/`, KF-TALL under `KF-TALL-vs-T21/models/HZ2/`)

Both models carry the full sidecar set (`geneset.model.json`, `geneset.meta.json`,
`geneset.provenance.json`) with populated GMT descriptions and publish-safe provenance — the released
inputs are represented by public Kids First DRC DRS identifiers plus GTEx v10 download references.

---

## Package Structure

Outputs follow the shared `<library>_all_models` layout used by GTEx, HuBMAP, LINCS_L1000, and
MoTrPAC:

```
kidsfirst_all_models/
  genesets/
    <comparison>/                       ← e.g. KF-ESGR-vs-muscle
      models/
        HZ1/                            ← harmonizome DE (all 13 comparisons)
          genesets.gmt                  ← comparison-level GMT (up + dn), descriptions populated
          workflow/
            run_summary.json
            run_summary.txt
          extractor/
            genesets.gmt
            geneset.tsv                 ← selected gene set members
            geneset.full.tsv            ← full ranked gene list with scores
            geneset.meta.json
            geneset.provenance.json
            geneset.model.json          ← model sidecar (library / model_id / inputs / params)
        HZ2/                            ← curated disease-up (11 disease partitions; same file set)
          genesets.gmt
          workflow/{run_summary.json,run_summary.txt}
          extractor/{genesets.gmt, geneset.tsv, geneset.full.tsv,
                     geneset.meta.json, geneset.provenance.json, geneset.model.json}
```

Each `geneset.provenance.json` begins from the released inputs (Kids First DRC RSEM via DRS
`drs://nci-crdc.datacommons.io/dg.4DFC/` + GTEx v10), through `kidsfirst_prepare` →
`rna_de_prepare` → `deg_long`, to the model's extractor (`rna_deg_multi` for HZ1,
`kidsfirst_curate` for HZ2). The refresh step produces `.orig` snapshots of the pre-refresh HZ1
metadata/provenance and retains them in the repository; they are **excluded from the external
submission package** because they hold pre-sanitization local working paths (see
`SUBMISSION_MANIFEST.md`).

---

## Running the Pipeline

**Differential expression + extraction** (produces the raw DE outputs; requires SLURM,
`PROJECT_DIR`/`DIG_DIR` set at the top of each `sbatch_*.sh`):

```bash
sbatch run/sbatch_01_de_only.sh          # KidsFirst DE (6 comparisons)
sbatch run/sbatch_02_cbtn_de.sh          # CBTN DE (7 brain tumor comparisons)
sbatch run/sbatch_03_extract_genesets.sh # HZ1 harmonizome gene sets
sbatch run/sbatch_04_curate_genesets.sh  # HZ2 curated disease-up gene sets
```

Matrix prep and curation are DIG-owned: `sbatch_01/02` delegate the prep steps to the DIG
`kidsfirst_prepare` workflow and `sbatch_04` calls `kidsfirst_curate`. For one study end-to-end
against the DIG workflow directly (matching the delivered provenance), use
`run/run_kf_de_study.sh`, whose prep step is a single `geneset-extractors workflows
kidsfirst_prepare` call. Run the batch scripts under the DIG environment.

**Branch-standard model operations** (config/env-driven, no in-script path editing) use the shared
wrappers at the repo-level `run/`:

```bash
# regenerate geneset.model.json sidecars for all enabled models (HZ1 + HZ2)
bash geneset-extractor-dev/run/submit_kidsfirst_models_cluster.sh --submit --write_model_only

# refresh metadata/provenance/GMT descriptions and inject public source identifiers
# (local_input_source_map.tsv is a repo-internal refresh aid; it is EXCLUDED from the external
#  submission package because it holds local working paths — see SUBMISSION_MANIFEST.md)
LOCAL_INPUT_SOURCE_MAP_TSV=geneset-extractor-dev/KidsFirst/config/local_input_source_map.tsv \
bash geneset-extractor-dev/run/submit_kidsfirst_models_cluster.sh --submit --refresh_metadata_and_provenance
```

An Apptainer-backed variant (`submit_kidsfirst_models_cluster_apptainer.sh`) is provided for
container execution. Use `--model_id HZ1|HZ2` and `--comparison <id>` to filter.

Supporting scripts are in `src/`. The core prep + curation logic is **DIG-owned**: the prep
scripts are thin shims over `geneset_extractors.workflows.kidsfirst_prepare` and the curation
entrypoint delegates to `kidsfirst_curate` (branch two-repo standard). They require the DIG
environment; the canonical entry points are `geneset-extractors workflows kidsfirst_prepare`
and `... kidsfirst_curate`.

| Script | Purpose |
|--------|---------|
| `build_rsem_matrix.py` | Shim → DIG `kidsfirst_prepare.build_tumor_matrix` (tumor RSEM matrix) |
| `extract_gtex_counts.py` | Shim → DIG `kidsfirst_prepare.extract_gtex_matrix` (GTEx normal matrix) |
| `prepare_de_inputs.py` | Shim → DIG `kidsfirst_prepare.merge_de_inputs` (combined_counts + sample_metadata) |
| `merge_study_matrices.py` | Wrapper orchestration: combine multi-study matrices (e.g. KF-BLOOD = TALL + MMC) |
| `curate_disease_genesets.py` | Legacy compatibility entrypoint that delegates to DIG `kidsfirst_curate` |
| `expand_gene_map_cbtn.py` | Expand ENSG→HGNC gene map for CBTN using mygene.info |
