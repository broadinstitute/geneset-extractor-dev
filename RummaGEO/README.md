# RummaGEO submission wrapper

This directory declares and dispatches the two RummaGEO models:
`gene_perturbations` and `drug_perturbations`.  It contains no RummaGEO
selection, label normalization, orthology, gene filtering, or GMT-generation
logic; those scientific operations are implemented by DIG's `rumma_geo`
converter.

Run the committed smoke fixture:

```bash
SUBMISSION_WORK_DIR=/path/to/output DIG_REPO=../dig-gene-set-extractors \
  bash reproduction/reproduce.sh --smoke
```

For a full run, set the following local-file environment variables, then run
`bash reproduction/reproduce.sh full`:

- `RUMMAGEO_HUMAN_GMT`
- `RUMMAGEO_MOUSE_GMT`
- `RUMMAGEO_SELECTION_MANIFEST`
- `RUMMAGEO_SOURCE_MANIFEST`
- `RUMMAGEO_HUMAN_GENE_INFO`
- `RUMMAGEO_MOUSE_GENE_INFO`
- `RUMMAGEO_GENE_ORTHOLOGS`

`RUMMAGEO_GENE_LEGACY_GMT` and `RUMMAGEO_DRUG_LEGACY_GMT` are optional
validation targets. They are passed only to DIG's diagnostic comparison and
cannot alter reconstructed memberships.

The source manifest and selection manifest are required production inputs.
They preserve the historically queried selection records and pinned URLs /
versions for the RummaGEO and NCBI snapshots rather than inferring either from
sample titles or current annotations.
