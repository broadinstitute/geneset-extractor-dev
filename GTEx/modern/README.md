# GTEx modern submitted path

This directory is the thin submission-wrapper boundary for GTEx. It selects a
declared model and tissue and dispatches the existing DIG-backed GTEx execution
path. It performs no source-data transformation, statistical analysis, gene
mapping, ranking, GMT writing, or provenance-graph construction.

Legacy GTEx launchers remain outside this boundary for compatibility while the
remaining orchestration/sidecar migration is completed and compared against
authoritative full outputs.
