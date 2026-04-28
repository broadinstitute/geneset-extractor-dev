# Commands

This planning bundle defines the continuous-age tissue model set. No models were run when this catalog was written.

Example commands:

```bash
cd /home/ryank/software/geneset_extractors

bash geneset-extractor-dev/GTEx/run/run_gtex_tissue_gmt.sh \
  --python_bin /home/ryank/software/miniconda3/envs/work/bin/python \
  --tissue_id adipose_subcutaneous \
  --model_ids T1,T5,T8
```

All tissue models:

```bash
cd /home/ryank/software/geneset_extractors

bash geneset-extractor-dev/GTEx/run/run_gtex_tissue_gmt.sh \
  --python_bin /home/ryank/software/miniconda3/envs/work/bin/python \
  --tissue_id adipose_subcutaneous \
  --model_ids all \
  --gtf inputs/GTEx/v10/gencode.v26.annotation.gtf.gz
```
