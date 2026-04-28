# genesets.gmt Command Provenance

- generated_at: `2026-04-28T15:41:42+00:00`
- output_gmt: `/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models/M20/extractor/genesets.gmt`
- tissue_id: `genesets`
- model_group: `models`
- model_id: `models`
- scope: `combined`
- scope_label: `all comparisons`

## Top-Level Wrapper Command

```bash
bash /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/run/run_gtex_model.sh --model_id models --prepared_dir /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/prepared --run_root /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/models --python_bin /home/ryank/software/miniconda3/envs/work/bin/python --gtf /home/ryank/software/geneset_extractors/inputs/GTEx/v10/gencode.v26.annotation.gtf.gz
```

## Logged Executed Commands

No explicit `$ ...` command lines were recorded in `run.log` for this model output.

## Notes

- For comparison models, one workflow run produces `workflow/deg_long.tsv` and one extractor run produces both the combined root `genesets.gmt` and the per-comparison `age*/genesets.gmt` files.
- The same wrapper, workflow, and extractor commands apply to each `age*/genesets.gmt` file under the model.
