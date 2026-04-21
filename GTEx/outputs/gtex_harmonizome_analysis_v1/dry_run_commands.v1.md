# GTEx Harmonizome Dry Run v1

- total_commands: 28

These are the exact external commands the script would run.
Internal Python dataframe preparation and file writes are not included.

## Commands

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `AdiposeTissue`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/AdiposeTissue.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/AdiposeTissue.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/AdiposeTissue.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/AdiposeTissue.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `AdrenalGland`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/AdrenalGland.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/AdrenalGland.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/AdrenalGland.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/AdrenalGland.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `Bladder`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/Bladder.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/Bladder.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/Bladder.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/Bladder.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `Blood`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/Blood.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/Blood.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/Blood.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/Blood.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `BloodVessel`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/BloodVessel.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/BloodVessel.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/BloodVessel.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/BloodVessel.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `Brain`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/Brain.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/Brain.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/Brain.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/Brain.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `Breast`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/Breast.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/Breast.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/Breast.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/Breast.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `Colon`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/Colon.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/Colon.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/Colon.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/Colon.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `Esophagus`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/Esophagus.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/Esophagus.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/Esophagus.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/Esophagus.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `Heart`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/Heart.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/Heart.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/Heart.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/Heart.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `Kidney`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/Kidney.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/Kidney.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/Kidney.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/Kidney.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `Liver`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/Liver.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/Liver.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/Liver.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/Liver.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `Lung`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/Lung.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/Lung.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/Lung.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/Lung.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `Muscle`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/Muscle.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/Muscle.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/Muscle.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/Muscle.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `Nerve`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/Nerve.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/Nerve.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/Nerve.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/Nerve.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `Ovary`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/Ovary.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/Ovary.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/Ovary.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/Ovary.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `Pancreas`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/Pancreas.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/Pancreas.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/Pancreas.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/Pancreas.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `Pituitary`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/Pituitary.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/Pituitary.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/Pituitary.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/Pituitary.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `Prostate`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/Prostate.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/Prostate.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/Prostate.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/Prostate.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `Skin`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/Skin.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/Skin.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/Skin.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/Skin.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `SmallIntestine`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/SmallIntestine.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/SmallIntestine.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/SmallIntestine.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/SmallIntestine.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `Spleen`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/Spleen.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/Spleen.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/Spleen.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/Spleen.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `Stomach`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/Stomach.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/Stomach.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/Stomach.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/Stomach.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `Testis`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/Testis.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/Testis.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/Testis.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/Testis.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `Thyroid`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/Thyroid.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/Thyroid.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/Thyroid.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/Thyroid.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `Uterus`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/Uterus.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/Uterus.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/Uterus.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/Uterus.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_de_prepare

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`
- legacy_tissue: `Vagina`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
workflows \
rna_de_prepare \
--modality \
bulk \
--counts_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/Vagina.v1.tsv \
--matrix_orientation \
gene_by_sample \
--feature_id_column \
Name \
--matrix_gene_symbol_column \
Description \
--sample_metadata_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/Vagina.v1.tsv \
--sample_id_column \
sample_id \
--group_column \
age_bin \
--comparisons_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/Vagina.v1.tsv \
--covariates \
sex,smtsd \
--de_mode \
harmonizome \
--balance_seed \
1 \
--backend \
lightweight \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/Vagina.v1 \
--organism \
human \
--genome_build \
hg38
```

### rna_deg_multi

- workdir: `/home/ryank/work/geneset_extractors/gtex/dig-gene-set-extractors`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 \
-m \
geneset_extractors.cli \
convert \
rna_deg_multi \
--deg_tsv \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/combined/deg_long_combined.v1.tsv \
--comparison_column \
comparison_id \
--out_dir \
/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_deg_multi.v1 \
--organism \
human \
--genome_build \
hg38
```

