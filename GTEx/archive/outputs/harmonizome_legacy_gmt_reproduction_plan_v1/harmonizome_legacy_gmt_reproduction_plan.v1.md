# Harmonizome Legacy GTEx GMT Reproduction Plan

## Take-Home Summary

The cloned repository [HarmonizomePythonScripts](/home/ryank/work/geneset_extractors/gtex/HarmonizomePythonScripts) very likely contains the core processing logic used to generate the legacy GTEx aging GMT, specifically in [GTExAgingSignatures.ipynb](/home/ryank/work/geneset_extractors/gtex/HarmonizomePythonScripts/GTEx/Tissue-Specific%20Aging%20Signatures/GTExAgingSignatures.ipynb). The notebook implements the same broad structure seen in the legacy file [GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt.gz](/home/ryank/work/geneset_extractors/gtex/GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt.gz): GTEx V8 bulk RNA-seq counts, tissue-specific `20-29` versus older-age comparisons, balanced case/control sampling with `random_state=1`, limma-voom differential expression, `adj.P.Val < 0.05`, sign splitting into up/down sets, and truncation to 250 genes per set. The legacy GMT has 270 sets and every set has exactly 250 genes, which matches the notebook's `head(250)` selection rule.

The repository does not appear to contain a fully self-contained runnable pipeline for the exact final legacy GMT export. The GTEx notebook depends on external files that are not included in the clone, and the final name formatting in the legacy GMT differs slightly from the intermediate notebook export. So the most realistic path is not "run one notebook unchanged", but "reconstruct the notebook logic in a standalone script, using the same inputs and thresholds, then add a small final renaming/export step."

## Evidence From The Cloned Repository

The most relevant files are:

- [GTExAgingSignatures.ipynb](/home/ryank/work/geneset_extractors/gtex/HarmonizomePythonScripts/GTEx/Tissue-Specific%20Aging%20Signatures/GTExAgingSignatures.ipynb)
- [GTEx_AgeComparison_Tissue_Sigs.ipynb](/home/ryank/work/geneset_extractors/gtex/HarmonizomePythonScripts/GTEx/Tissue-Specific%20Age%20Comparisons/GTEx_AgeComparison_Tissue_Sigs.ipynb)

Key logic extracted from the GTEx aging notebook:

- reads GTEx V8 counts from `bulk-gex_v8_rna-seq_GTEx_Analysis_2017-06-05_v8_RNASeQCv1.1.9_gene_reads.gct`
- reads sample metadata from `GTEx_Analysis_v8_Annotations_SampleAttributesDS.txt`
- reads subject phenotypes from `GTEx_Analysis_v8_Annotations_SubjectPhenotypesDS.txt`
- maps Ensembl IDs to symbols using `../../mapping/source_files/human_gene_info`
- deduplicates Ensembl IDs by keeping the row with the highest variance
- restricts each tissue analysis to genes passing `filter_by_expr`
- requires at least 3 samples in the `20-29` group and at least 3 in the older age group
- balances the two groups by sampling the same number of samples from each side using `random_state=1`
- runs `limma_voom_differential_expression(ctl_df, pert_df)`
- filters each DEG table to `adj.P.Val < 0.05`
- assigns direction by `logFC > 0` versus `logFC < 0`
- sorts by adjusted p-value and keeps the top 250 genes per `(Aging Signature, Threshold)`
- writes up and down GMT files separately as `gene_set_library_up_crisp.gmt` and `gene_set_library_dn_crisp.gmt`

This is strongly consistent with the local legacy GMT because:

- the local legacy GMT has `270` sets
- every local set has exactly `250` genes
- set names follow the same tissue-age comparison pattern used in the notebook: `GTEx_<Tissue>_20-29_vs_<OlderBin>`

## What Is Missing From The Repository

The clone does not include all required inputs in the locations expected by the notebook:

- `../GTExTissue/bulk-gex_v8_rna-seq_GTEx_Analysis_2017-06-05_v8_RNASeQCv1.1.9_gene_reads.gct`
- `../GTExTissue/GTEx_Analysis_v8_Annotations_SampleAttributesDS.txt`
- `GTEx_Analysis_v8_Annotations_SubjectPhenotypesDS.txt`
- `../../mapping/source_files/human_gene_info`

Those paths are hardcoded relative to the notebook and are not present in the repository clone. That means the notebook cannot be rerun as-is without rebuilding the expected directory layout or modifying the code.

There is also a naming mismatch between the notebook's intermediate GMT export and the local legacy GMT:

- the notebook uses an `Aging Signature` label with spaces, produced by `sig.replace('_', ' ')`
- the notebook later appends `_up` and `_down` in lowercase when loading the crisp GMTs
- the local legacy GMT uses underscore-separated names with capitalized direction suffixes such as `GTEx_Uterus_20-29_vs_40-49_Up`

That implies a final normalization/export step occurred either outside the notebook or later in the Harmonizome publication pipeline.

## Reproduction Plan

### Phase 1: Reconstruct The Exact Input Bundle

1. Use the GTEx V8 bulk RNA-seq gene counts file already present locally:
   - [GTEx_Analysis_2017-06-05_v8_RNASeQCv1.1.9_gene_reads.gct.gz](/home/ryank/work/geneset_extractors/gtex/outputs/gtex_no_harmonizome_analysis_v1/downloads/GTEx_Analysis_2017-06-05_v8_RNASeQCv1.1.9_gene_reads.gct.gz)
2. Use the GTEx sample and subject metadata already present locally:
   - [GTEx_Analysis_v8_Annotations_SampleAttributesDS.txt](/home/ryank/work/geneset_extractors/gtex/outputs/gtex_no_harmonizome_analysis_v1/downloads/GTEx_Analysis_v8_Annotations_SampleAttributesDS.txt)
   - [GTEx_Analysis_v8_Annotations_SubjectPhenotypesDS.txt](/home/ryank/work/geneset_extractors/gtex/outputs/gtex_no_harmonizome_analysis_v1/downloads/GTEx_Analysis_v8_Annotations_SubjectPhenotypesDS.txt)
3. Reconstruct the `human_gene_info` mapping used by the notebook. The notebook expects NCBI-style fields including `#tax_id`, `Symbol`, and `dbXrefs`, with Ensembl IDs embedded in `dbXrefs`.
4. Verify the mapping snapshot date if possible, because symbol mapping drift could change the final membership slightly.

### Phase 2: Reimplement The Notebook As A Standalone Script

Create a standalone Python script instead of trying to execute the notebook directly. The script should reproduce the notebook logic as closely as possible:

1. Read the GTEx counts GCT with `skiprows=2`.
2. Keep only genes whose Ensembl IDs appear in the `human_gene_info` mapping.
3. Collapse duplicate Ensembl-versioned rows by keeping the row with highest variance per Ensembl ID.
4. Replace Ensembl IDs with mapped gene symbols.
5. Build sample metadata with:
   - `SAMPID`
   - `SMTS`
   - subject ID derived from the first two pieces of `SAMPID`
   - age bin from the subject phenotypes file
   - sex from the subject phenotypes file
6. For each tissue:
   - subset counts to that tissue
   - apply `filter_by_expr`
   - require at least 3 `20-29` samples
   - for each older age bin with at least 3 samples:
     - balance case and control counts by random subsampling
     - use `random_state=1`
     - run limma-voom differential expression
     - save one TSV per comparison

### Phase 3: Recreate The Legacy Membership Rule

For each comparison TSV:

1. Filter to rows with `adj.P.Val < 0.05`.
2. Label genes with `Threshold = 1` if `logFC > 0`, otherwise `Threshold = -1`.
3. Sort by ascending `adj.P.Val`.
4. Group by `(Aging Signature, Threshold)` and keep `head(250)`.
5. Split into:
   - up genes for `Threshold = 1`
   - down genes for `Threshold = -1`
6. Drop any set with fewer than 5 genes, matching the notebook's crisp GMT export rule.

This is the highest-confidence rule set for reproducing the legacy GMT membership.

### Phase 4: Recreate The Final Legacy GMT Naming

After reproducing the notebook-level up/down sets, normalize names into the exact legacy format:

1. Start from comparison names like `GTEx_Uterus_20-29_vs_40-49`
2. Append:
   - `_Up` for positive `logFC`
   - `_Down` for negative `logFC`
3. Ensure each GMT line is tab-delimited with exactly:
   - set name
   - 250 gene symbols

The local legacy GMT uses this final form:

- `GTEx_Uterus_20-29_vs_40-49_Up`
- `GTEx_Uterus_20-29_vs_40-49_Down`

### Phase 5: Validate Against The Local Legacy GMT

Compare the reproduced output directly to [GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt.gz](/home/ryank/work/geneset_extractors/gtex/GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt.gz).

Validation checks:

1. total set count should be near `270`
2. every set should have `250` genes
3. set names should match exactly
4. per-set Jaccard overlap should be measured against the legacy GMT
5. any missing or extra sets should be summarized by tissue and age bin

## Most Likely Sources Of Remaining Disagreement

Even with the repository code, exact reproduction may still drift for a few reasons:

- the `human_gene_info` snapshot may differ from the one originally used
- the version of `maayanlab_bioinformatics` used for `filter_by_expr` and limma-voom wrappers may have changed
- GTEx notebook input paths suggest this was run in a larger private or semi-private Harmonizome build environment
- the final `_Up` and `_Down` export formatting may have happened outside the notebook
- if the local legacy GMT was generated from a 2021 run and the notebook reflects a 2023 refresh, there may be subtle code or mapping differences even if the overall logic matches

## Recommended Next Step

The most defensible next step is to build a new standalone reproduction script that follows the notebook exactly, rather than trying to execute the notebook in-place. That script should use the local GTEx V8 downloads already present in this workspace, reconstruct the notebook's Ensembl-to-symbol mapping behavior, and emit a candidate GMT in the exact legacy format for direct comparison to the local reference file.
