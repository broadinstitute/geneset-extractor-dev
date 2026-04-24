# GTEx Harmonizome Dry Run v1

- total_examples: 2

This workflow first runs one `rna_de_prepare` command per tissue, then runs one `rna_deg_multi` conversion after the tissue-level DE results are combined.

The commands below are representative examples, not the full expanded command list.
Each example shows the first command of that type in the order the script would run it.
Internal Python dataframe preparation and file writes are not included.

## Internal Preparation

### 1. build_tissue_matrices

- explanation: Internal Python step that creates the per-tissue matrix, metadata, and comparison TSV files before the external workflow commands run.
- example_tissue: `AdiposeTissue`

```python
counts_gct_gz_path = downloads_dir / "GTEx_Analysis_2017-06-05_v8_RNASeQCv1.1.9_gene_reads.gct.gz"
matrix_dir = prepared_dir / "tissue_matrices"
metadata_dir = prepared_dir / "tissue_metadata"
comparisons_dir = prepared_dir / "tissue_comparisons"

tissue_metadata_df = metadata_df[metadata_df["legacy_tissue"] == "AdiposeTissue"].copy()
tissue_metadata_df = tissue_metadata_df[[
    "sample_id", "subjid", "age_bin", "sex", "smts", "smtsd", "legacy_tissue"
]].drop_duplicates(subset=["sample_id"])

with gzip.open(counts_gct_gz_path, "rt", encoding="utf-8") as handle:
    version_line = handle.readline().strip()
    dims_line = handle.readline().strip()
    header = handle.readline().rstrip("\n").split("\t")
    sample_columns = header[2:]
    sample_index = {sample_id: idx for idx, sample_id in enumerate(sample_columns)}
    indices = [sample_index[sample_id] for sample_id in tissue_metadata_df["sample_id"] if sample_id in sample_index]
    ordered_samples = [sample_columns[idx] for idx in indices]

    with open(r"outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/AdiposeTissue.v1.tsv", "w", encoding="utf-8", newline="") as matrix_handle:
        writer = csv.writer(matrix_handle, delimiter="\t")
        writer.writerow(["Name", "Description", *ordered_samples])
        for raw_line in handle:
            fields = raw_line.rstrip("\n").split("\t")
            gene_id = fields[0]
            gene_symbol = fields[1]
            values = fields[2:]
            selected_values = [values[idx] if idx < len(values) else "" for idx in indices]
            writer.writerow([gene_id, gene_symbol, *selected_values])

tissue_metadata_df.to_csv(r"outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/AdiposeTissue.v1.tsv", sep="\t", index=False)
tissue_comparisons_df = comparison_df[comparison_df["legacy_tissue"] == "AdiposeTissue"][[
    "comparison_id", "comparison_kind", "group_column", "group_a", "group_b"
]]
tissue_comparisons_df.to_csv(r"outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/AdiposeTissue.v1.tsv", sep="\t", index=False)
```

## Example Commands

### 2. rna_de_prepare

- explanation: Example tissue-level differential expression workflow command. The real run repeats this pattern for each tissue in the manifest.
- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- example_tissue: `AdiposeTissue`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 -m geneset_extractors.cli workflows rna_de_prepare \
  --modality bulk \
  --counts_tsv outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/AdiposeTissue.v1.tsv \
  --matrix_orientation gene_by_sample \
  --feature_id_column Name \
  --matrix_gene_symbol_column Description \
  --sample_metadata_tsv outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/AdiposeTissue.v1.tsv \
  --sample_id_column sample_id \
  --group_column age_bin \
  --comparisons_tsv outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/AdiposeTissue.v1.tsv \
  --covariates sex,smtsd \
  --de_mode harmonizome \
  --balance_seed 1 \
  --backend lightweight \
  --out_dir outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/AdiposeTissue.v1 \
  --organism human \
  --genome_build hg38
```

### 3. rna_deg_multi

- explanation: Example downstream conversion command that turns the combined DEG table into gene sets after the tissue workflows finish.
- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 -m geneset_extractors.cli convert rna_deg_multi \
  --deg_tsv outputs/gtex_harmonizome_analysis_v1/combined/deg_long_combined.v1.tsv \
  --comparison_column comparison_id \
  --out_dir outputs/gtex_harmonizome_analysis_v1/rna_deg_multi.v1 \
  --organism human \
  --genome_build hg38
```

