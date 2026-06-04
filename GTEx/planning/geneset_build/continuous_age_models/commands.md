# Commands

This planning bundle defines the continuous-age tissue model set. No models were run when this catalog was written.

The current top-level entry point is `build_genesets.sh`. It now passes raw GTEx
inputs directly into a `dig` GTEx workflow for the selected tissue and model(s).

Current broad-tissue example:

```bash
cd /home/ryank/software/geneset_extractors

bash geneset-extractor-dev/GTEx/run/build_genesets.sh \
  --tissue_granularity broad \
  --tissues adipose_tissue \
  --models AC1 \
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
  --models AC1 \
  --counts_gct inputs/GTEx/v10/GTEx_Analysis_v10_RNASeQCv2.4.2_gene_reads.gct.gz \
  --sample_metadata_tsv inputs/GTEx/v10/GTEx_Analysis_v10_Annotations_SampleAttributesDS.txt \
  --subject_metadata_tsv inputs/GTEx/v10/GTEx_Analysis_v10_Annotations_SubjectPhenotypesDS.txt \
  --dig_dir /home/ryank/software/geneset_extractors/dig-gene-set-extractors
```

Direct runner example from raw GTEx inputs:

```bash
cd /home/ryank/software/geneset_extractors

python3 geneset-extractor-dev/GTEx/src/run_continuous_age_model.py \
  --tissue_id adipose_subcutaneous \
  --tissue_label "Adipose - Subcutaneous" \
  --model_ids AC1,AC5,AC8 \
  --expression_gct "$PWD/inputs/GTEx/v10/gtex_v10_gene_reads_by_tissue/gene_reads_v10_adipose_subcutaneous.gct.gz" \
  --sample_attributes_tsv "$PWD/inputs/GTEx/v10/GTEx_Analysis_v10_Annotations_SampleAttributesDS.txt" \
  --subject_phenotypes_tsv "$PWD/inputs/GTEx/v10/GTEx_Analysis_v10_Annotations_SubjectPhenotypesDS.txt" \
  --run_root "$PWD/gtex_outputs/genesets/adipose_subcutaneous/models" \
  --rscript_bin Rscript \
  --dig_dir /home/ryank/software/geneset_extractors/dig-gene-set-extractors
```

Default output root behavior:

- if `--out_root` is omitted, outputs are written under `./gtex_outputs`
- continuous-age outputs then land under `./gtex_outputs/genesets/<tissue>/models/<model_id>/`
