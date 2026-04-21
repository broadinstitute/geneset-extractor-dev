# run_pigean_eaggl_batch v1

Runs the full batch analysis described in `pigean_eaggl_commands.txt`.

Workflow:

1. Load gene sets from three sources:
   `gtex_harmonizome_analysis_v1`,
   `gtex_no_harmonizome_analysis_v1`,
   and `GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021`.
2. Write one input gene-list file per set.
3. Run `python -m pigean beta_tildes` for each input gene list.
4. Run `python -m eaggl factor` on each successful PIGEAN bundle with explicit stats-column mappings.
5. Write per-set summary tables and a markdown report under a named `outputs/` subdirectory.
