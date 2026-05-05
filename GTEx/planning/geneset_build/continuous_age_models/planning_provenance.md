# Planning Provenance

These notes describe how the continuous-age model panel was derived.

The `AC1` through `AC10` model family was designed to fit the current GTEx-local continuous-age workflow rather than the earlier pairwise age-bin contrast workflow.

Key design decisions:

- one regression per tissue using continuous age rather than pairwise age-bin contrasts
- directional output only: positive sets increase with age, negative sets decrease with age
- model variation limited to dimensions that still matter in this setting:
  - covariate adjustment
  - annotation mode
  - extractor style
  - threshold/ranking strictness
- exclusion of dimensions that were specific to the contrast workflow:
  - group balancing
  - contrast-scope versus stratum-scope filtering
  - contrast-reference construction choices

Why nonlinear age models were not included:

- the current GMT output format assumes one directional positive set and one directional negative set
- spline and quadratic terms do not map cleanly to one positive and one negative geneset without an additional interpretation convention
- linear continuous-age models are the clearest first-pass directional aging models

Inputs used to derive the panel:

- the current GTEx-local continuous-age runner under `geneset-extractor-dev/GTEx/src/`
- the current DIG RNA-seq differential-expression and converter interfaces in the workspace
- the existing age-binned GTEx planning bundle as a source of prior extractor options worth retaining

This provenance note exists for planning consistency with the age-binned model bundle. It is documentation only and is not used by the runtime pipeline.
