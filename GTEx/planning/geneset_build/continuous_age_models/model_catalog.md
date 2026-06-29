# GTEx Tissue Continuous-Age Model Catalog

This catalog defines the GTEx-local model panel for tissue-level GMT generation from a single continuous-age regression across all retained tissue samples.

Design principles:
- keep age modeling coherent: one regression per tissue, not pairwise age-bin contrasts
- keep emitted GMTs directional: positive sets increase with age, negative sets decrease with age
- vary only dimensions that still matter in this setting: covariates, annotation, extractor style, and strictness
- avoid dimensions that were specific to the old contrast workflow such as group balancing or contrast-scope filtering

Why there are no nonlinear age models in this panel:
- the current GMT output format assumes directional signed gene sets
- spline or quadratic age terms do not map cleanly to one positive and one negative set without additional conventions
- linear continuous-age models are the most interpretable starting point for directional tissue-aging GMTs

Model families:
- `core`: recommended defaults
- `sensitivity`: assess whether a modeling choice changes the tissue-aging signature materially
- `annotation`: assess mapping and gene-space sensitivity
- `threshold`: thresholded directional signatures
- `strictness`: stricter threshold variants
- `ranked`: top-k ranked directional signatures

Recommended starting subset:
- `AC1`: canonical ranked default
- `AC5`: canonical thresholded directional model
- `AC6`: stricter significance model
- `AC8`: ranked-by-stat alternative

Full panel:
- `AC1`: linear age + `SEX`; harmonizome ranked; `gct_symbols_only`; protein-coding GMT
- `AC2`: same as `AC1` without `SEX`
- `AC3`: same as `AC1` with `gtf_annotated`
- `AC4`: same as `AC3` but broader GMT gene space
- `AC5`: thresholded legacy signed `-log10(padj)` model
- `AC6`: stricter version of `AC5`
- `AC7`: stricter threshold variant using a higher score floor
- `AC8`: top-k ranked-by-stat model
- `AC9`: top-k ranked by `logFC * -log10(p)`
- `AC10`: top-k ranked by `logFC`

Naming convention:
- `AB*`: age-binned contrast models
- `AC*`: continuous-age models
- `HZ*`: notebook-style/Harmonizome-style aging-signature models
- `TV*`: reserved for future tissue-versus-reference models
