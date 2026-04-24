# run_harmonizome_legacy_gtex_reproduction.v2

This runner hardens the GTEx aging-signature preprocessing path by processing exactly one tissue per invocation.

Key differences from `v1`:

- one tissue is processed per invocation
- a status table tracks `pending`, `running`, `completed`, and `error` tissues
- existing raw tissue matrices and completed processed tissues are reused
- disconnects only risk the currently active tissue instead of the whole batch

Main outputs:

- `prepared/prepared_tissue_status.v1.tsv`
- `prepared/prepared_tissue_status.v1.md`
- `prepared/prepared_tissue_inputs.v1.tsv`
- `run_summary.v2.md`

Typical usage:

- `bash run/run_harmonizome_legacy_gtex_reproduction.v2.sh`
- `bash run/run_harmonizome_legacy_gtex_reproduction.v2.sh --tissue_name Colon`

The default wrapper uses `--next_pending_tissue`, so repeated invocations will walk forward through the remaining tissues one at a time.
