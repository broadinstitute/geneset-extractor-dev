# ImmPort Pipeline Inputs

The current ImmPort pipeline supports one per-study `IM*` model that produces
signed up/down differential-expression gene sets, partitioned by study contrast:

- `IM1`
  - per-study case-vs-control bulk RNA-seq differential-expression signatures

## Dual input mode (released DE vs counts)

`IM1` is deliberately **mixed-mode**. Each study in `config/study_list.tsv` is run in
exactly one of two modes, chosen by whether the study row carries a
`released_de_object`:

- **Released-DE mode** (`released_de_object` is set)
  - Provenance begins from the study's **published differential-expression table**
    (`released_de_object`).
  - No counts-based DE is recomputed; the released table is converted directly.
  - Sidecar records `workflow_name: released_de`,
    `parameters.de_source: study_published_de_table`,
    and `parameters.released_de_object`.
  - Gene sets are ranked by the released statistic
    (`extractor_score_mode_released`, default `stat`).
- **Counts-based mode** (`released_de_object` is empty; `expression_object` +
  `sample_metadata_object` are set)
  - Provenance begins from the study's **raw counts + sample metadata**.
  - DE is computed inside DIG via the `rna_de_prepare` workflow, then converted.
  - Sidecar records `workflow_name: rna_de_prepare` and the DE parameters
    (`group_column`, `case_label`, `control_label`, `covariates`, `backend`,
    `padj_max`).
  - Gene sets are ranked by `extractor_score_mode` (default `signed_neglog10padj`).

This distinction is surfaced to reviewers in three places, all derived from the
model sidecar during refresh:

- the per-set **GMT second-column description** (states which input each set came from),
- the templated `geneset.meta.json` `gene_set.description`,
- the **provenance graph**, whose first input node is the released DE table or the
  raw counts/metadata, respectively.

The reference studies in `config/study_list.tsv` include at least one of each mode:

- released-DE: `SDY1299_*` (published DESeq tables)
- counts-based: `SDY2948` (expression matrix + sample metadata → `rna_de_prepare`)

## Planning inputs

- `config/model_list.tsv`
- `config/model_manifest.tsv`
- `config/study_list.tsv` (partition list; one row per study contrast)
- `config/model_description_templates.tsv`

## Biological inputs

Downloaded under `inputs/ImmPort/<SDY_accession>/` (untracked), per study:

- counts-based: `expression_object` (expression matrix TSV) + `sample_metadata_object`
- released-DE: `released_de_object` (published DE table)

## Software inputs

- `dig-gene-set-extractors/` (owns `rna_de_prepare` workflow and `rna_deg` converter)

## Runtime shape

Counts-based studies run through:

- `geneset_extractors.cli workflows rna_de_prepare`
- `geneset_extractors.cli convert rna_deg`

Released-DE studies run through:

- `geneset_extractors.cli convert rna_deg` (starting from the released DE table)

## Output behavior

If `--out_root` is omitted, outputs go under:

- `./immport_all_models/`

The output tree is study-partitioned:

- `immport_all_models/genesets/<study_id>/models/IM1/{workflow,extractor}/`

The authoritative GMT output for each study is:

- `extractor/genesets.gmt`

Optional provenance mirror inputs supported by the build entrypoint:

- `--provenance_mirror_local_prefix`
- `--provenance_mirror_remote_prefix`
