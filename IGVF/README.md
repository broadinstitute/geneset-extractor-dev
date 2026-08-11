# IGVF Perturb-seq

This wrapper dispatches the DIG `igvf_perturbseq` workflow and the shared
`signed_term_gene` converter for 16 released IGVF Perturb-seq differential-expression tables.

The committed `config/analysis_set_list.tsv` is the scientific contract: it declares each
source accession, table schema, column mapping, significance threshold, and per-direction
top-k selection. Full regeneration uses `bash reproduction/reproduce.sh full`; smoke
validation uses `bash reproduction/reproduce.sh --smoke`.

The authoritative full legacy GMTs are explicitly paired with the regenerated full GMTs in
`submission.yaml` under `adoption.reference_outputs`, using `set_equivalent` comparison.
