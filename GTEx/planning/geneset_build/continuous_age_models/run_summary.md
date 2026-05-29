# GTEx Tissue Continuous-Age Planning Summary

This planning bundle replaces reuse of the old 22 contrast-oriented GTEx models for the tissue-level continuous-age workflow.

Current decisions:
- use one continuous-age regression per tissue
- keep the model panel compatible with signed directional GMT output
- reduce the active panel to `AC1` through `AC10`
- center model variation on covariate adjustment, annotation, extractor strategy, and strictness
- avoid absolute `logFC` thresholds in continuous-age models because the fitted per-year coefficients are on a much smaller scale than pairwise age-bin contrasts
- use `AB*` for age-binned models, `AC*` for continuous-age models, `HZ*` for notebook-style/Harmonizome-style aging-signature models, and reserve `TV*` for future tissue-versus-reference models

Files:
- `model_manifest.tsv`
- `model_catalog.md`
- `commands.md`

Status:
- planning complete
- runner updated to read `model_manifest.tsv` directly
- no tissue models were rerun as part of this planning update

Current runtime notes:

- `build_genesets.sh` is the main user-facing entry point for `AC*`
- the active continuous-age extractor names are `GTEx_<tissue>_up` and `GTEx_<tissue>_dn`
- the default output root is `./gtex_outputs`
- both detailed tissues and broad `SMTS` tissues are supported in the active pipeline
