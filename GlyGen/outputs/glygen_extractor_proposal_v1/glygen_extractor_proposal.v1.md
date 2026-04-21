# GlyGen Extractor Proposal v1

## Purpose

Build a reproducible GlyGen extractor that converts GlyGen human glycosylation-site citation exports into glycan-centric human gene sets. The target product is a binary association library where each gene set represents proteins glycosylated by one GlyTouCan glycan accession.

This proposal is based on `glygen/inputs.txt`, the legacy Harmonizome GlyGen notebook at `gtex/HarmonizomePythonScripts/GlyGen/Glycosylated Proteins/GlyGen.ipynb`, and the current `dig-gene-set-extractors` package style for workflow staging, converter specs, run summaries, provenance, GMT output, and validation.

## Input Files

The `glygen/inputs.txt` file identifies three GlyGen source tables:

| source_key | glygen_id | expected_file | source_url |
|---|---:|---|---|
| unicarbkb | GLY_000138 | `human_proteoform_citations_glycosylation_sites_unicarbkb.csv` | `https://data.glygen.org/GLY_000138` |
| harvard | GLY_000513 | `human_proteoform_citations_glycosylation_sites_harvard.csv` | `https://data.glygen.org/GLY_000513` |
| glyconnect | GLY_000483 | `human_proteoform_citations_glycosylation_sites_glyconnect.csv` | `https://data.glygen.org/GLY_000483` |

The legacy Harmonizome notebook also used `human_protein_masterlist.csv` to map `uniprotkb_canonical_ac` to gene symbols, then applied a Harmonizome-specific gene symbol mapping table. The new extractor should make this mapping explicit rather than implicit:

- Require an input protein masterlist when the source CSVs do not already contain an approved gene symbol column.
- Support optional mapping resources for UniProt accession to HGNC/NCBI gene symbol harmonization.
- Emit all mapping failures to a QC table instead of silently dropping them.

## Proposed Extractor Scope

The GlyGen data are association data, not quantitative PTM contrast data. The best fit is a small public-resource workflow and a binary converter, rather than reuse of `ptm_site_diff` or `ptm_site_matrix`.

Proposed extractor name:

- CLI converter: `glygen_glycosylated_proteins`
- Workflow helper: `workflows glygen_prepare_public`
- Local analysis script name for this extractor subdirectory: `glygen/src/prepare_glygen_glycosylated_proteins.v1.py`
- Matching wrapper: `glygen/run/prepare_glygen_glycosylated_proteins.v1.sh`

The package implementation in `dig-gene-set-extractors` should follow existing package layout:

| proposed_path | role |
|---|---|
| `src/geneset_extractors/extractors/glygen/__init__.py` | extractor namespace |
| `src/geneset_extractors/extractors/glygen/public_prepare.py` | load raw GlyGen CSVs, normalize columns, map genes, write standardized edges |
| `src/geneset_extractors/extractors/glygen/workflow.py` | build gene sets, metadata, QC tables, GMT |
| `src/geneset_extractors/extractors/converters/glygen_glycosylated_proteins.py` | CLI-facing converter |
| `src/geneset_extractors/extractors/converters/specs/glygen_glycosylated_proteins.json` | converter input/output contract |
| `docs/assays/glygen/guide.md` | practical guide and commands |
| `tests/test_glygen_glycosylated_proteins_converter.py` | converter smoke and schema tests |

## Data Model

The first standardized table should be an edge table with one row per unique evidence-supported gene-glycan association.

Recommended `glygen_edges.v1.tsv` columns:

| column | description |
|---|---|
| `gene_symbol` | approved uppercase human gene symbol |
| `gene_id` | optional NCBI Gene identifier when available |
| `protein_accession` | source `uniprotkb_canonical_ac` |
| `glytoucan_ac` | GlyTouCan glycan accession |
| `source_key` | one of `unicarbkb`, `harvard`, `glyconnect` |
| `source_glygen_id` | GlyGen download id, for example `GLY_000138` |
| `evidence_count` | number of source rows collapsed into this edge |
| `source_row_count` | synonym of evidence count if no finer evidence model is available |

Recommended `glygen_gene_sets.v1.tsv` columns:

| column | description |
|---|---|
| `gene_set_id` | stable set id, preferably `glygen_glycan:<glytoucan_ac>` |
| `gene_set_name` | display name, preferably `glygen_glycosylated_by_<glytoucan_ac>` |
| `glytoucan_ac` | GlyTouCan glycan accession |
| `gene_symbol` | member gene |
| `gene_id` | optional NCBI Gene identifier |
| `weight` | `1.0` for binary membership |
| `evidence_count` | total collapsed evidence for this gene-glycan edge |

The extractor should also write a `glygen_gene_set_summary.v1.tsv` table with one row per glycan:

- `gene_set_id`
- `glytoucan_ac`
- `n_genes`
- `n_edges`
- `n_sources`
- `total_evidence_count`
- `emit_gmt`
- `small_set_reason`

## Processing Steps

1. Discover input files from explicit CLI flags or an input manifest TSV.
2. Load the three CSV files with logging for file paths, row counts, and column names.
3. Add `source_key` and `source_glygen_id` before concatenation.
4. Select and normalize the core columns: `uniprotkb_canonical_ac`, `glytoucan_ac`, and optional evidence fields if present.
5. Drop rows missing either protein accession or glycan accession, with counts written to QC.
6. Map protein accessions to approved human gene symbols.
7. Normalize all output column names to lowercase snake case.
8. Collapse duplicate `(gene_symbol, glytoucan_ac, source_key)` records and retain evidence counts.
9. Aggregate to `(gene_symbol, glytoucan_ac)` membership rows across sources.
10. Emit complete edge and gene-set tables before size filtering.
11. Apply GMT emission filters, defaulting to the legacy Harmonizome threshold of at least 5 genes per glycan.
12. Write classic GMT output for downstream compatibility and optional DIG two-column GMT if package conventions require it.
13. Write run metadata, provenance, run summary, manifest, and log files.

## Outputs

All generated local outputs should be written under a named subfolder of `glygen/outputs/`, for example:

`glygen/outputs/glygen_glycosylated_proteins_v1/`

Recommended files:

| file | description |
|---|---|
| `glygen_edges.v1.tsv` | collapsed gene-glycan edge table |
| `glygen_gene_sets.v1.tsv` | long gene-set membership table |
| `glygen_gene_set_summary.v1.tsv` | one-row-per-glycan set summary |
| `glygen_mapping_failures.v1.tsv` | protein accessions or symbols that could not be mapped |
| `glygen_input_summary.v1.tsv` | file-level row counts, hashes, and source metadata |
| `glygen_glycosylated_proteins.v1.gmt` | classic GMT, filtered to eligible gene sets |
| `glygen_glycosylated_proteins.v1.meta.json` | metadata and parameter record |
| `glygen_glycosylated_proteins.v1.provenance.json` | input hashes, commands, and software versions |
| `glygen_glycosylated_proteins.v1.log` | progress and dataframe-shape log |
| `glygen_glycosylated_proteins_manifest.v1.tsv` | named output manifest with short descriptions |
| `glygen_glycosylated_proteins.v1.md` | output documentation |

No plots are required for the core extractor. If QC plots are added later, each plot should be written to both PDF and PNG with a companion TSV and MD using the same basename.

## CLI Contract

Proposed direct converter command:

```bash
geneset-extractors convert glygen_glycosylated_proteins \
  --unicarbkb_csv glygen/inputs/human_proteoform_citations_glycosylation_sites_unicarbkb.csv \
  --harvard_csv glygen/inputs/human_proteoform_citations_glycosylation_sites_harvard.csv \
  --glyconnect_csv glygen/inputs/human_proteoform_citations_glycosylation_sites_glyconnect.csv \
  --protein_masterlist_csv glygen/inputs/human_protein_masterlist.csv \
  --out_dir glygen/outputs/glygen_glycosylated_proteins_v1 \
  --organism human \
  --min_genes_per_set 5 \
  --gmt_format classic
```

Proposed local wrapper command:

```bash
bash glygen/run/prepare_glygen_glycosylated_proteins.v1.sh
```

The wrapper should call the Python entrypoint with explicit file paths and write all outputs to `glygen/outputs/glygen_glycosylated_proteins_v1/`.

## Logging Requirements

The Python workflow should use file and stderr logging. Major logged events should include:

- input discovery and existence checks
- per-file load shape
- concatenated raw shape
- selected-column shape
- missing-value drop counts
- mapping table shape
- mapped and unmapped row counts
- duplicate-collapse shape
- gene-set summary shape
- GMT eligibility counts
- every output write path and shape

## Validation Plan

The first validation target is reproducibility against known historical counts:

- `glygen/inputs.txt` reports 1910 gene sets on the Harmonizome page.
- `glygen/inputs.txt` reports 338 gene sets in the existing DCC GMT.
- The legacy Harmonizome notebook states that three GlyGen citation datasets were combined to create associations between 2128 human proteins and 1910 glycans.

The extractor should not force either historical count as a hard-coded assertion. Instead, it should write observed counts at each filtering step so differences can be explained by source-file versions, gene mapping, and minimum-gene-set thresholds.

Minimum tests:

- input CSV loading accepts the three expected GlyGen files
- output columns are lowercase snake case
- duplicate source rows collapse deterministically
- all emitted GMT sets have at least `min_genes_per_set` genes by default
- `gene_set_summary.v1.tsv` row count equals the number of unique glycans before GMT filtering
- `glygen_gene_sets.v1.tsv` has no empty `gene_symbol` or `glytoucan_ac`
- metadata records the three source URLs and input file hashes

## Open Decisions

1. Gene mapping source: use the GlyGen `human_protein_masterlist.csv` as a required input, package a stable mapping resource, or accept both with clear precedence.
2. GMT naming: use raw GlyTouCan accessions as set names for exact legacy compatibility, or prefix with `glygen_glycosylated_by_` for namespace clarity.
3. Evidence model: retain only binary membership for v1, or expose evidence count as a weight while still emitting binary GMT.
4. Harmonizome compatibility: decide whether to produce a legacy-compatible output directory with `gene_attribute_edges.txt.gz`, `gene_set_library_crisp.gmt`, and related files, or keep only the package-native DIG outputs.

## Recommendation

Implement v1 as a package-native binary association extractor with classic GMT output enabled by default. Keep the raw GlyTouCan accession in metadata and use namespaced `gene_set_id` values in TSV outputs. Retain evidence counts for QC and ranking diagnostics, but emit binary GMT membership because the source data represent curated associations rather than quantitative abundance or differential activity.

The first implementation should focus on deterministic table generation, transparent mapping failures, and count reconciliation against the 1910 Harmonizome and 338 DCC reference counts before adding optional compatibility exports.

## Output Manifest

| file | description |
|---|---|
| `glygen_extractor_proposal.v1.md` | proposal for a new GlyGen glycosylated-proteins gene-set extractor |
