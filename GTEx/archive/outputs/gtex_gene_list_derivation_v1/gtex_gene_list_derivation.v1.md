# GTEx Gene List Derivation

## High-Level Summary

The gene lists in `gtex_harmonizome_analysis_v1` and `gtex_no_harmonizome_analysis_v1` were derived from the same starting GTEx V8 RNA-seq counts and the same GTEx sample/subject metadata. Both workflows first restricted the analysis to tissues that appear in the legacy GTEx aging reference library, then built age-based comparisons within each tissue using `20-29` as the reference age bin and older age bins as the comparison groups. For each eligible tissue and age contrast, the workflows ran differential expression and then converted each comparison into `Up` and `Down` gene sets.

The main difference between the two outputs is not the input data or the tissue/age comparison structure. The difference is how the differential-expression results were postprocessed into gene sets. `gtex_harmonizome_analysis_v1` used a Harmonizome-oriented postprocessing path that imposed significance-based filtering and threshold-based inclusion rules, while `gtex_no_harmonizome_analysis_v1` used a legacy-style postprocessing path that kept the default top-ranked-gene selection behavior. As a result, the two workflows can produce gene sets with the same names but different memberships and different set counts.

## Shared Inputs And Comparison Setup

Both workflows started from the same three GTEx files:

- `GTEx_Analysis_2017-06-05_v8_RNASeQCv1.1.9_gene_reads.gct.gz`
- `GTEx_Analysis_v8_Annotations_SampleAttributesDS.txt`
- `GTEx_Analysis_v8_Annotations_SubjectPhenotypesDS.txt`

The runner loaded the reference GMT set names from `GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt.gz` and parsed those names to determine which tissues should be analyzed. Only tissues present in that reference library were kept.

Sample metadata were built by:

- reading `SAMPID`, `SMTS`, and `SMTSD` from the sample-attributes table
- reading `SUBJID`, `AGE`, and `SEX` from the subject-phenotypes table
- deriving `SUBJID` from the first two components of `SAMPID`
- joining sample-level and subject-level metadata
- mapping GTEx broad tissue names (`SMTS`) to the legacy tissue names used in the GTEx aging set names
- dropping samples without an age bin

For each retained tissue, the workflow created age comparisons using:

- reference group: `20-29`
- comparison group: each older age bin present in that tissue with at least 2 samples

This yielded comparison names of the form:

- `GTEx_<Tissue>_20-29_vs_30-39`
- `GTEx_<Tissue>_20-29_vs_40-49`
- `GTEx_<Tissue>_20-29_vs_50-59`
- `GTEx_<Tissue>_20-29_vs_60-69`
- `GTEx_<Tissue>_20-29_vs_70-79`

The workflow then built one per-tissue expression matrix and one per-tissue comparison table. Files such as `outputs/gtex_no_harmonizome_analysis_v1/prepared/tissue_matrices/AdiposeTissue.v1.tsv` were created by streaming the GTEx GCT file once and extracting the sample columns belonging to that tissue. Each tissue matrix contains:

- `Name`
- `Description`
- one column per GTEx sample ID for that tissue

The corresponding per-tissue metadata table recorded the sample ID, subject ID, age bin, sex, GTEx tissue labels, and legacy tissue name. The per-tissue comparison table recorded the age-bin contrasts to run.

## Differential Expression Stage

After matrix preparation, both workflows ran `geneset_extractors.cli workflows rna_de_prepare` separately for each tissue matrix. They used the same backend and covariates:

- backend: `lightweight`
- covariates: `sex,smtsd`

The difference was the differential-expression mode:

- `gtex_harmonizome_analysis_v1`: `--de_mode harmonizome`
- `gtex_no_harmonizome_analysis_v1`: `--de_mode modern`

Each tissue workflow produced a long-form differential-expression table, and those tissue-level tables were concatenated into:

- `outputs/gtex_harmonizome_analysis_v1/combined/deg_long_combined.v1.tsv`
- `outputs/gtex_no_harmonizome_analysis_v1/combined/deg_long_combined.v1.tsv`

Those combined DEG tables were the direct inputs to the gene-set conversion stage.

## Exact Rules Used To Determine Set Membership

### Step 1: Group DEG Rows By Comparison

The converter `geneset_extractors.cli convert rna_deg_multi` grouped the combined DEG table by comparison name. Each comparison was processed independently, so set membership was determined separately for each tissue/age contrast.

### Step 2: Score And Filter Differential-Expression Rows

The most important difference between the two workflows is the `postprocess_mode` used inside `rna_deg_multi`.

For `gtex_harmonizome_analysis_v1`, the script called `rna_deg_multi` without an explicit `--postprocess_mode`, so the CLI default `harmonizome` mode applied. In that mode, the postprocessing configuration was changed to:

- `score_mode = signed_neglog10padj`
- `padj_max = 0.05` if not otherwise specified
- `select = threshold`
- `min_score = 1.30103`
- `gmt_source = selected`
- `gmt_topk_list = 250`
- `gmt_min_genes = 5`
- `gmt_max_genes = 250`
- `emit_small_gene_sets = True`
- `gmt_biotype_allowlist = ""`
- `disable_default_excludes = True`

The practical effect is:

- genes first had to survive adjusted-p-value filtering at `padj <= 0.05`
- remaining genes were scored using signed `-log10(padj)`
- genes were kept for set construction if their absolute score was at least `1.30103`, which corresponds to `-log10(0.05)`
- if no genes survived the significance filter for a comparison, that comparison could be skipped entirely in Harmonizome mode

For `gtex_no_harmonizome_analysis_v1`, the script explicitly called `rna_deg_multi --postprocess_mode legacy`. In legacy mode, those Harmonizome overrides were not applied, so the converter kept the baseline CLI defaults:

- `select = top_k`
- `top_k = 200`
- `normalize = within_set_l1`
- `gmt_prefer_symbol = True`
- `gmt_require_symbol = True`
- `gmt_biotype_allowlist = protein_coding`
- `gmt_min_genes = 100`
- `gmt_max_genes = 500`
- `gmt_topk_list = 200`
- `gmt_split_signed = False`
- `gmt_emit_abs = False`

The practical effect is:

- there was no automatic Harmonizome-style `padj <= 0.05` postprocessing filter
- genes were selected by rank rather than by a fixed significance threshold
- membership was based on the top-ranked genes per signed direction rather than all genes passing a Harmonizome threshold
- only genes with acceptable symbols and allowed biotypes were emitted to GMT output

### Step 3: Collapse Duplicate Genes

Within each comparison, duplicate gene IDs were aggregated using the default duplicate-handling policy `max_abs`. That means if the same gene appeared multiple times, the row with the largest absolute score was the one that determined the gene's retained value for downstream ranking and selection.

### Step 4: Convert Selected Rows Into Up And Down Sets

After filtering, scoring, and selection, the chosen rows were turned into signed gene sets. Positive-direction genes became an `Up` signature and negative-direction genes became a `Down` signature.

Internally, the generated set names used the `rna_deg_multi` naming pattern:

- `rna_deg_multi__comparison=<comparison>__signature=pos__topk=<n>`
- `rna_deg_multi__comparison=<comparison>__signature=neg__topk=<n>`

The GTEx runner then converted those generated names back into the legacy GTEx naming convention:

- `__signature=pos__...` became `GTEx_<Tissue>_20-29_vs_<OlderBin>_Up`
- `__signature=neg__...` became `GTEx_<Tissue>_20-29_vs_<OlderBin>_Down`

So the final membership rule for any one GTEx set was:

1. start with all DEG rows for one tissue/age comparison
2. apply the workflow-specific postprocessing rules
3. score and rank genes
4. keep either threshold-passing genes or top-ranked genes, depending on mode
5. split the retained genes by sign into `Up` and `Down`
6. emit the signed list under the legacy GTEx set name

## What Specifically Differed Between The Two Output Libraries

`gtex_harmonizome_analysis_v1` and `gtex_no_harmonizome_analysis_v1` used the same tissues, the same age-bin comparisons, and the same underlying GTEx expression data. The differences in final gene membership came from the conversion rules applied after differential expression.

In `gtex_harmonizome_analysis_v1`, set membership was driven by significance-based inclusion. Genes entered a set only if they survived the Harmonizome-style adjusted-p-value filter and passed the score threshold. This can shrink sets, allow small sets, remove comparisons entirely when no genes remain, and include non-protein-coding genes because the biotype allowlist was cleared.

In `gtex_no_harmonizome_analysis_v1`, set membership was driven by legacy top-k selection. Genes entered a set by ranking high enough within a comparison rather than by passing the Harmonizome threshold. This makes the output closer to the older GTEx-style extraction logic, retains the protein-coding restriction, and preserves more comparison-level outputs because the converter does not skip comparisons simply because nothing survived a Harmonizome significance filter.

## Relevant Source Files

The derivation described above comes from these local files:

- `src/run_gtex_harmonizome_analysis.v1.py`
- `src/run_gtex_no_harmonizome_analysis.v1.py`
- `dig-gene-set-extractors/src/geneset_extractors/cli.py`
- `dig-gene-set-extractors/src/geneset_extractors/extractors/converters/rna_deg_multi.py`
- `dig-gene-set-extractors/src/geneset_extractors/extractors/rnaseq/deg_workflow.py`
