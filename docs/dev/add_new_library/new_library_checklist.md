# New Library Checklist

Use this checklist before opening a PR.

## Repository Setup

- cloned both `geneset-extractor-dev` and `dig-gene-set-extractors`
- branched from `main` in both repos with a unique branch name
- collected and documented required library input data

## DIG Requirements

- workflow logic lives in `dig-gene-set-extractors`
- DIG CLI entrypoint exists or was added cleanly
- workflow follows an existing assay pattern where possible
- no unrelated DIG regressions were introduced

## Wrapper Requirements

- `geneset-extractor-dev` only wraps DIG logic
- new library directory exists under `geneset-extractor-dev/LIBRARY_X/`
- `config/`, `run/`, and `src/` were added
- wrapper code follows existing style from GTEx, MoTrPAC, HuBMAP, or LINCS_L1000

## Config Requirements

- `model_list.tsv` exists if models are used
- `model_manifest.tsv` exists if model-specific parameters are needed
- `model_description_templates.tsv` exists
- partition lists such as `tissue_list.tsv` or `dataset_list.tsv` exist when needed
- all TSVs have headers

## Model Requirements

- model IDs are stable and documented
- model families/groups are explicit
- multiple models are config-driven rather than hard-coded ad hoc
- model sidecars can be generated as `geneset.model.json`

## Output Requirements

- final layout follows existing standards
- final output directory is `extractor/`
- intermediate outputs are under `workflow/`
- `geneset.meta.json` is present
- `geneset.provenance.json` is present
- `geneset.model.json` is present

## Shared Tooling Requirements

- metadata refresh works
- provenance refresh works
- S3 publish works
- local paths can be rewritten cleanly
- no library-specific hacks were added unless unavoidable

## Validation

- at least one small end-to-end test run completed
- output names and directory structure were reviewed manually
- metadata/provenance graph connectivity was checked
- shared code changes were checked against existing libraries
