# Commands

This planning bundle defines the age-binned model set. No `AB*` models were run when this catalog was written.

The current top-level entry point is `build_genesets.sh`. It now passes raw GTEx
inputs directly into a `dig` GTEx workflow for the selected tissue and model(s).

Current broad-tissue example:

```bash
cd /home/ryank/software/geneset_extractors

bash geneset-extractor-dev/GTEx/run/build_genesets.sh \
  --tissue_granularity broad \
  --tissues adipose_tissue \
  --models AB1 \
  --counts_gct inputs/GTEx/v10/GTEx_Analysis_v10_RNASeQCv2.4.2_gene_reads.gct.gz \
  --sample_metadata_tsv inputs/GTEx/v10/GTEx_Analysis_v10_Annotations_SampleAttributesDS.txt \
  --subject_metadata_tsv inputs/GTEx/v10/GTEx_Analysis_v10_Annotations_SubjectPhenotypesDS.txt \
  --gtf inputs/GTEx/v10/gencode.v39.annotation.gtf.gz \
  --dig_dir /home/ryank/software/geneset_extractors/dig-gene-set-extractors
```

Current detailed-tissue example:

```bash
cd /home/ryank/software/geneset_extractors

bash geneset-extractor-dev/GTEx/run/build_genesets.sh \
  --tissues adipose_subcutaneous \
  --models AB1 \
  --counts_gct inputs/GTEx/v10/GTEx_Analysis_v10_RNASeQCv2.4.2_gene_reads.gct.gz \
  --sample_metadata_tsv inputs/GTEx/v10/GTEx_Analysis_v10_Annotations_SampleAttributesDS.txt \
  --subject_metadata_tsv inputs/GTEx/v10/GTEx_Analysis_v10_Annotations_SubjectPhenotypesDS.txt \
  --gtf inputs/GTEx/v10/gencode.v39.annotation.gtf.gz \
  --dig_dir /home/ryank/software/geneset_extractors/dig-gene-set-extractors
```

Direct runner example from raw GTEx inputs:

```bash
cd /home/ryank/software/geneset_extractors

python3 geneset-extractor-dev/GTEx/src/run_age_binned_model.py \
  --model_id AB1 \
  --tissue_id adipose_subcutaneous \
  --tissue_label "Adipose - Subcutaneous" \
  --expression_gct "$PWD/inputs/GTEx/v10/gtex_v10_gene_reads_by_tissue/gene_reads_v10_adipose_subcutaneous.gct.gz" \
  --sample_attributes_tsv "$PWD/inputs/GTEx/v10/GTEx_Analysis_v10_Annotations_SampleAttributesDS.txt" \
  --subject_phenotypes_tsv "$PWD/inputs/GTEx/v10/GTEx_Analysis_v10_Annotations_SubjectPhenotypesDS.txt" \
  --run_root "$PWD/gtex_outputs/genesets/adipose_subcutaneous/models" \
  --python_bin "$(command -v python3)" \
  --dig_dir /home/ryank/software/geneset_extractors/dig-gene-set-extractors
```

Default output root behavior:

- if `--out_root` is omitted, outputs are written under `./gtex_outputs`
- age-binned outputs then land under `./gtex_outputs/genesets/<tissue>/models/<model_id>/`

The original planning-time inspection commands were moved to:

- `planning_provenance.md`
