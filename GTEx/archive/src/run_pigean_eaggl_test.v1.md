# run_pigean_eaggl_test v1

Runs one reproducible PIGEAN to EAGGL example using a single Adipose tissue gene set from the no-harmonizome GTEx aging signature GMT.

Workflow:

1. Select the first `GTEx_AdiposeTissue_*` set from the source GMT.
2. Write the selected genes to a plain-text gene list file.
3. Run `python -m pigean beta_tildes` with `--gene-list-in` and `--eaggl-bundle-out`.
4. Run `python -m eaggl factor` from the generated bundle.

Outputs are written under a named subfolder in `outputs/`.
