# run_pigean_eaggl_test v3

Runs the updated one-set comparison analysis from `pigean_eaggl_test_commands.txt`.

Workflow:

1. Load the three GTEx GMT sources.
2. Pick one adipose-tissue set shared by all three sources.
3. Quantify gene overlap across the three versions of that set.
4. Write overlap tables plus PDF/PNG plots with companion TSV and MD files.
5. Run `python -m pigean beta_tildes` once per source-specific gene list.
6. Run `python -m eaggl factor` once per generated PIGEAN bundle.
7. Write a comparison report summarizing similarities and differences across the three EAGGL runs.
