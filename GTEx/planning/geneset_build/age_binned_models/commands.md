# Commands

This planning bundle defines the age-binned model set. No `AB*` models were run when this catalog was written.

Build tissue inputs first:

```bash
cd /home/ryank/software/geneset_extractors

bash geneset-extractor-dev/GTEx/run/build_tissue_inputs.sh \
  --python_bin /home/ryank/software/miniconda3/envs/work/bin/python \
  --counts_gct inputs/GTEx/v10/gene_reads_v10_adipose_subcutaneous.gct.gz \
  --sample_metadata_tsv inputs/GTEx/v10/GTEx_Analysis_v10_Annotations_SampleAttributesDS.txt \
  --subject_metadata_tsv inputs/GTEx/v10/GTEx_Analysis_v10_Annotations_SubjectPhenotypesDS.txt \
  --tissue_label "Adipose - Subcutaneous" \
  --out_dir geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/prepared
```

Run one age-binned model:

```bash
cd /home/ryank/software/geneset_extractors

bash geneset-extractor-dev/GTEx/run/run_age_binned_model.sh \
  --model_id AB1 \
  --prepared_dir geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/prepared \
  --run_root geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models \
  --python_bin /home/ryank/software/miniconda3/envs/work/bin/python \
  --gtf inputs/GTEx/v10/gencode.v26.annotation.gtf.gz
```

Run all age-binned models:

```bash
cd /home/ryank/software/geneset_extractors

bash geneset-extractor-dev/GTEx/run/run_all_age_binned_models.sh \
  --prepared_dir geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/prepared \
  --run_root geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models \
  --python_bin /home/ryank/software/miniconda3/envs/work/bin/python \
  --gtf inputs/GTEx/v10/gencode.v26.annotation.gtf.gz
```

The original planning-time inspection commands were moved to:

- `planning_provenance.md`
