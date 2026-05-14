# Tissue Prep Comparison: Current GTEx Code vs `GTEx_AgeComparison_Tissue_Sigs.ipynb`

This note compares the current tissue-preparation code in:

- `geneset-extractor-dev/GTEx/src/build_tissue_inputs.py`

to the notebook:

- `GTEx_AgeComparison_Tissue_Sigs.ipynb`

## Main Differences

### Input format and scope

- The notebook starts from one global GTEx v8 `gctx` matrix and iterates across all tissues.
- The current script takes one per-tissue GTEx v10 `gct.gz` file and prepares one tissue at a time.

### Tissue grouping

- The notebook groups tissues by `SMTS`.
- The current script carries both:
  - `SMTS` as `primary_tissue`
  - `SMTSD` as `detailed_tissue`

### Sample and subject alignment

- The notebook derives a subject ID from `SAMPID` and joins subject metadata on that value.
- The current script does the same basic join, but also supports a fallback subject-ID derivation if the sample metadata does not provide a usable subject ID.

### Age and sex normalization

- The notebook uses metadata values as-is.
- The current script normalizes:
  - GTEx age codes `1..6` to `20-29` through `70-79`
  - GTEx sex codes `1/2` to `M/F`

### Gene filtering before DE

- The notebook performs gene preprocessing before any differential expression step:
  - maps Ensembl IDs to gene symbols using `Homo_sapiens.gene_info`
  - drops genes without a mapping
  - applies `filter_by_expr` per tissue before building age comparisons
- The current script does none of that during prep. It keeps all rows from the input GCT and writes:
  - `gene_id`
  - `gene_symbol`
  - retained sample columns

### Comparison construction

- The notebook directly constructs balanced age-comparison sample sets by random subsampling each comparison group to the same size as the `20-29` reference group, using `random_state=1`.
- The current script only writes a `comparisons.tsv` manifest. It does not subsample or balance samples at prep time.

### Minimum sample threshold

- The notebook requires at least `3` samples in the `20-29` reference group and at least `3` in each comparison age group.
- The current script defaults to `2` using `--min_samples_per_group`.

### Where balancing and filtering happen

- In the notebook, balancing and expression filtering happen during prep and comparison generation.
- In the current pipeline, those decisions are deferred to downstream `rna_de_prepare` model runs and can vary by model.

### Outputs

- The notebook directly writes per-comparison DE result TSVs and one metadata table describing selected case/control sample IDs.
- The current script writes a reusable prepared bundle:
  - `tissue_counts.tsv`
  - `sample_metadata.tsv`
  - `comparisons.tsv`
  - `prepare_summary.json`
  - `naming_reference.md`

## Summary

The notebook performs heavier preprocessing at prep time:

- gene filtering
- gene ID to symbol mapping
- per-comparison sample balancing
- direct DE output generation

The current GTEx prep script is intentionally lighter:

- it aligns samples and subject metadata
- normalizes age/sex labels
- writes one reusable prepared bundle
- leaves balancing and many filtering decisions to downstream model-specific DE steps
