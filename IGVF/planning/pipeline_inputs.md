# IGVF Pipeline Inputs

The current IGVF pipeline supports one per-analysis-set `PS*` model that produces
signed up/down perturbational gene sets, partitioned by IGVF analysis set:

- `PS1`
  - per-perturbation signed Perturb-seq (single-cell CRISPR) differential-expression
    signatures

## Planning inputs

- `config/model_list.tsv`
- `config/model_manifest.tsv`
- `config/analysis_set_list.tsv` (partition list; one row per IGVF analysis set)
- `config/model_description_templates.tsv`

## Biological inputs

Downloaded under `inputs/IGVF/<analysis_set_id>/` (untracked):

- processed per-perturbation differential-expression signature table (released IGVF
  Perturb-seq DE results)
- optional gene id → symbol mapping file

Provenance begins from the released IGVF processed differential-expression signature
table for the analysis set (not from raw FASTQ or count matrices).

## Software inputs

- `dig-gene-set-extractors/` (owns the `igvf_perturbseq` workflow and the
  `signed_term_gene` converter)

## Runtime shape

`PS1` runs through:

- `geneset_extractors.cli workflows igvf_perturbseq`
- `geneset_extractors.cli convert signed_term_gene`

Each perturbed element yields a signed pair of sets (`..._up` / `..._dn`); the up/down
interpretation and the released-DE origin are stated in the per-set GMT descriptions,
the templated `geneset.meta.json`, and the provenance graph.

## Output behavior

If `--out_root` is omitted, outputs go under:

- `./igvf_all_models/`

The output tree is analysis-set-partitioned:

- `igvf_all_models/genesets/<analysis_set_id>/models/PS1/{workflow,extractor}/`

The authoritative GMT output for each analysis set is:

- `extractor/genesets.gmt`

Optional provenance mirror inputs supported by the build entrypoint:

- `--provenance_mirror_local_prefix`
- `--provenance_mirror_remote_prefix`
