# analyze_missing_legacy_set_representation v1

This script checks whether legacy GTEx aging sets that are missing from the reproduced GMT were even represented in the reproduction input.

Inputs:

- reference legacy GMT
- reproduced GMT
- prepared comparison manifest
- prepared sample metadata
- combined DEG table

Outputs:

- `missing_set_representation.v1.tsv`
- `missing_set_representation_summary.v1.tsv`
- `missing_set_representation_by_tissue.v1.tsv`
- `missing_set_representation.v1.md`
- `analyze_missing_legacy_set_representation.v1.log`

Usage:

```bash
python3 src/analyze_missing_legacy_set_representation.v1.py \
  --reference_gmt_gz GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt.gz \
  --generated_gmt_gz outputs/harmonizome_legacy_gtex_reproduction_v1/gtex_aging_signatures_legacy_format.v1.gmt.gz \
  --comparison_manifest_tsv outputs/harmonizome_legacy_gtex_reproduction_v1/prepared/comparison_manifest_all.v1.tsv \
  --sample_metadata_tsv outputs/harmonizome_legacy_gtex_reproduction_v1/prepared/sample_metadata_all.v1.tsv \
  --combined_deg_tsv outputs/harmonizome_legacy_gtex_reproduction_v1/deg_long_combined.v1.tsv \
  --output_dir outputs/harmonizome_missing_set_representation_v1
```
