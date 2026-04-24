# run_harmonizome_legacy_gtex_reproduction.v1

This script implements a standalone, memory-safe approximation of the GTEx aging-signature notebook logic found in the cloned Harmonizome repository.

Inputs:

- GTEx V8 bulk RNA-seq counts GCT
- GTEx sample attributes table
- GTEx subject phenotypes table
- an Ensembl-to-symbol mapping file
- optionally the local legacy GTEx aging GMT for comparison

Pipeline:

1. load GTEx metadata and build tissue-wise `20-29` versus older-age comparison manifests
2. stream the raw GCT once and write per-tissue matrices
3. map Ensembl IDs to symbols and deduplicate rows by maximum variance
4. optionally run limma-voom by tissue through `Rscript`
5. apply the legacy membership rule:
   - `adj.P.Val < 0.05`
   - split by sign of `logFC`
   - top 250 genes per comparison and direction
   - minimum set size 5
6. emit a candidate legacy-format GMT and compare it to the local reference GMT

Important implementation note:

The original notebook reads the full GTEx matrix into memory and deduplicates globally before tissue splitting. This script uses a memory-safe per-tissue extraction path instead. That should preserve the main logic, but it can introduce small differences relative to the original environment.

Execution modes:

- default: full run, requires `Rscript` plus installed `limma` and `edgeR`
- `--prepare_only`: stop after preprocessing and balanced comparison construction
