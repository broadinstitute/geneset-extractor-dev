# GTEx Tissue Continuous-Age Planning Summary

This planning bundle replaces reuse of the old 22 contrast-oriented GTEx models for the tissue-level continuous-age workflow.

Current decisions:
- use one continuous-age regression per tissue
- keep the model panel compatible with signed directional GMT output
- reduce the active panel to `T1` through `T10`
- center model variation on covariate adjustment, annotation, extractor strategy, and strictness
- avoid absolute `logFC` thresholds in continuous-age models because the fitted per-year coefficients are on a much smaller scale than pairwise age-bin contrasts

Files:
- `model_manifest.tsv`
- `model_catalog.md`
- `commands.md`

Status:
- planning complete
- runner updated to read `model_manifest.tsv` directly
- no tissue models were rerun as part of this planning update
