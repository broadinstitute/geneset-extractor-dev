# PsychENCODE Pipeline Inputs

The PsychENCODE pipeline supports two all-signatures `HZ*` models, following the
**released-resource → GMT** pattern used by HuBMAP and LINCS_L1000 (partition `all_signatures`,
no tissue dimension):

- `HZ1`
  - released disorder differential-expression (DEX) signatures — signed up/down per disorder
- `HZ2`
  - released gene co-expression modules — unsigned, one set per module

(`HZ3`, an optional GRN model, is deferred — see "Deferred".)

## Planning inputs

- `config/model_list.tsv`
- `config/model_manifest.tsv`
- `config/model_description_templates.tsv`

## Biological and mapping inputs

Open-access **derived** products only (no controlled NDA 5032 raw data). Staged, git-ignored, under
`inputs/PsychENCODE/raw/`; provenance (URLs, DOI, date, sha256) in `inputs/PsychENCODE/SOURCES.md`.
All human, GENCODE v19 (GRCh37/hg19). Source: `resource.psychencode.org` released layer for
Gandal et al. 2018, *Science* aat8127 (DOI 10.1126/science.aat8127).

For `HZ1` (`released_dex`, signed):

- `inputs/PsychENCODE/raw/DER-13_Disorder_DEX_Genes.csv`
  - columns: `Gene_Name` (symbol), `Ensembl_Name` (Ensembl gene id), `Disorder.DGE_RegulationDirection`
  - 6 signed sets: ASD/BD/SCZ × up/down (399–2450 genes each)
  - `term` = disorder, `sign` = up/down, `gene_id` = Ensembl, `gene_symbol` = `Gene_Name`, `score` = 1
    (released list has no per-gene stat; for continuous scores see the deferred Gandal Table S1)

For `HZ2` (`released_modules`, unsigned):

- `inputs/PsychENCODE/raw/DER-16_Disorder_Gene_Modules.csv` (primary)
  - columns include: `ensembl_gene_id`, `gene_name` (symbol), `Module`, `Mod.number`, `kME0`–`kME34`
  - 35 modules `geneM0`–`geneM34`; `geneM0` is the WGCNA grey/unassigned bucket (exclude),
    real modules `geneM1`–`geneM34` span 54–2645 genes
  - `term` = `Module`, unsigned, `gene_id` = `ensembl_gene_id`, `gene_symbol` = `gene_name`,
    `score` = kME of assigned module (or 1)
- `inputs/PsychENCODE/raw/INT-08_WGCNA_modules_ensembl_ids.xlsx`,
  `inputs/PsychENCODE/raw/INT-09_WGCNA_modules_hgnc_ids.xlsx` (secondary; wide format,
  versioned Ensembl ids / HGNC symbols)
- `inputs/PsychENCODE/raw/Cross-disorder_README.csv` (column dictionary / build documentation)

A human gene-id → symbol mapping (as HuBMAP/LINCS use `inputs/human_gene_info`) is **not required**:
both id types ship in the same files (Ensembl + HGNC symbol).

## Software inputs

- `dig-gene-set-extractors/`

## Output behavior

If `--out_root` is omitted, outputs go under:

- `./psychencode_outputs/`

The all-signatures output tree is:

- `psychencode_outputs/genesets/all_signatures/models/HZ1/`
- `psychencode_outputs/genesets/all_signatures/models/HZ2/`

The authoritative GMT output for each model is:

- `extractor/genesets.gmt`

## Runtime shape (mirrors HuBMAP/LINCS)

- `HZ1`
  - `geneset_extractors.cli workflows psychencode_dex` (released disorder DEX → signed term-gene TSV)
  - `geneset_extractors.cli convert signed_term_gene`
  - gene_set pattern: `PsychENCODE_<disorder>_up|dn` (emits `PsychENCODE_{ASD,BD,SCZ}_{up,dn}`)
- `HZ2`
  - `geneset_extractors.cli workflows psychencode_modules` (released modules → unsigned term-gene TSV)
  - `geneset_extractors.cli convert unsigned_term_gene`
  - gene_set pattern: `PsychENCODE_<module>` (emits `PsychENCODE_geneM1` … `PsychENCODE_geneM34`)

The wrapper entrypoint is `run/build_psychencode_genesets.sh` →
`src/build_psychencode_genesets.py` → `src/run_psychencode_hz_model.py`, which calls the DIG
workflow + converter, writes `geneset.model.json`, and rebuilds `geneset.provenance.json` — the same
shape as `LINCS_L1000` and `HuBMAP`.

`geneset-extractor-dev/PsychENCODE` is responsible only for model selection, argument resolution, and
commands/log packaging; the functional workflow logic lives in `dig-gene-set-extractors`.

Optional provenance mirror inputs supported by the build entrypoint:

- `--provenance_mirror_local_prefix`
- `--provenance_mirror_remote_prefix`

## Deferred

- `HZ3` (`released_grn`, unsigned, `PsychENCODE_GRN_<TF>`): source
  `resource.psychencode.org/Datasets/Integrative/INT-10_Reference_Network_GRN_1.csv` (~3.3 GB).
  Not downloaded; pull only when HZ3 is implemented.
- Gandal 2018 *Science* Table S1/S5 (per-gene effect sizes) — blocked to automated fetch; browser
  download only if continuous DE scores are later needed (see `SOURCES.md`).
- NDA 5032 controlled raw data — out of scope (needs DUC).
