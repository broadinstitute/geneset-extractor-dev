# PsychENCODE `released_dex` / `released_modules` Integration Proposal

This mirrors the HuBMAP `hz_released_asctb` and LINCS_L1000 `hz_released_matrix` proposals: a thin
`geneset-extractor-dev` wrapper drives released-resource workflows implemented in
`dig-gene-set-extractors`, which emit a term-gene TSV that the shared converters turn into the
authoritative GMT plus metadata/provenance/model sidecars.

## Closest existing pattern

PsychENCODE publishes **released, processed** gene-level products, so it follows the
library-generation-from-a-released-resource pattern — not the raw-counts GTEx/MoTrPAC path:

- **HZ1** is signed (up/down per disorder) → reuses the LINCS_L1000 `signed_term_gene` contract.
- **HZ2** is unsigned (one set per module) → reuses the HuBMAP `unsigned_term_gene` contract.

Partition is `all_signatures` (no tissue dimension), identical to LINCS_L1000 and HuBMAP.

## Models

| model_id | model_family | DIG workflow | converter | gene_set pattern | source file |
|----------|--------------|--------------|-----------|------------------|-------------|
| HZ1 | `released_dex` | `psychencode_dex` | `signed_term_gene` | `PsychENCODE_<disorder>_up\|dn` | `DER-13_Disorder_DEX_Genes.csv` |
| HZ2 | `released_modules` | `psychencode_modules` | `unsigned_term_gene` | `PsychENCODE_<module>` | `DER-16_Disorder_Gene_Modules.csv` |

Source: PsychENCODE released cross-disorder layer (`resource.psychencode.org`), from Gandal et al.
2018, *Science* aat8127. Human, GENCODE v19 / GRCh37 (`hg19`). See `inputs/PsychENCODE/SOURCES.md`.

## DIG-side logic (owns the workflow)

- `geneset_extractors/workflows/psychencode_dex.py` — parses the `Disorder.DGE_RegulationDirection`
  field (`ASD.DGE_down` → term `ASD`, sign `-1`), emits `psychencode_signed_term_gene.tsv`
  (`term, gene_id, gene_symbol, score, sign`; score=1 binary membership) + provenance graph.
- `geneset_extractors/workflows/psychencode_modules.py` — emits `psychencode_unsigned_term_gene.tsv`
  (`term, gene_id, gene_symbol, score`; score=1), one row per gene keyed by its WGCNA `Module`,
  excluding the grey/unassigned bucket (`--exclude_modules geneM0`) + provenance graph.
- CLI: `workflows psychencode_dex` and `workflows psychencode_modules` (additive registration in
  `cli.py`). The authoritative GMTs are written by the existing `signed_term_gene` /
  `unsigned_term_gene` converters — no new converter or output structure was introduced.

## Wrapper-side (orchestration only)

`PsychENCODE/{config,src,run}` mirror LINCS_L1000 file-for-file:

- `config/{model_list,model_manifest,model_description_templates}.tsv`
- `src/psychencode_selection_io.py`, `src/build_psychencode_genesets.py`,
  `src/run_psychencode_hz_model.py`
- `run/build_psychencode_genesets.sh`

`run_psychencode_hz_model.py` selects the workflow + converter per model, writes
`geneset.model.json`, and rebuilds `geneset.provenance.json` via `provenance build`.

## Shared-tooling compatibility (verified)

- Output layout: `genesets/all_signatures/models/HZ{1,2}/{workflow,extractor}` with
  `extractor/{genesets.gmt, geneset.meta.json, geneset.provenance.json, geneset.model.json}`.
- `run/refresh_model_metadata_and_provenance.sh` patches descriptions from
  `model_description_templates.tsv` (template var `{model.model_id}`) and rewrites provenance
  paths — confirmed working with no library-specific exceptions (file inputs `--dex_csv` /
  `--modules_csv` are rewritten through the same source-map path used by LINCS `--expression_tsv`).

## Deferred

- `HZ3` (`released_grn`, unsigned, `PsychENCODE_GRN_<TF>`) — source `INT-10` GRN (~3.3 GB). Not built.
- Gandal Table S1 per-gene effect sizes (would replace HZ1 `score=1` with `|stat|`) — blocked to
  automated fetch; browser-download only if continuous DE scores are later wanted (see `SOURCES.md`).
