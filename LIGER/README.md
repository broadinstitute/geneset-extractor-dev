# LIGER Docker Workflow

This directory contains the Docker-oriented batch wrapper for running the DIG
LIGER workflow against one or more `.h5ad` files.

## What it runs

The batch runner:

1. scans an input root recursively for `.h5ad` files
2. runs `geneset-extractors workflows scrna_liger_prepare` for each file
3. runs the generated `run_liger.sh`
4. runs the generated `run_geneset_extractors_from_liger.sh`

The implementation entrypoint inside the container is:

```bash
python LIGER/src/run_liger_h5ad_batch.py
```

## Recommended launch command

From the repository root:

```bash
INPUT_ROOT=/Users/mduby/Data/Broad/GeneSetIncubator/Liger/H5adTestDataDocker \
OUTPUT_ROOT=/Users/mduby/Code/DccWorkspace/ServerGeneSetCompute/LIGER/outputs/docker_run \
run/run_liger_docker.sh
```

That wrapper builds `geneset-extractor.Dockerfile` with:

- `DIG_BRANCH=md_liger`

and then mounts:

- this repo at `/work`
- the input h5ad tree at `/inputs` read-only
- the host output directory at `/liger_outputs`

## Raw docker commands

Build:

```bash
docker build \
  -f geneset-extractor.Dockerfile \
  -t geneset-extractors-liger:md_liger \
  --build-arg DIG_BRANCH=md_liger \
  .
```

Run:

```bash
docker run --rm \
  -v /Users/mduby/Code/DccWorkspace/ServerGeneSetCompute:/work \
  -v /Users/mduby/Data/Broad/GeneSetIncubator/Liger/H5adTestDataDocker:/inputs:ro \
  -v /Users/mduby/Code/DccWorkspace/ServerGeneSetCompute/LIGER/outputs/docker_run:/liger_outputs \
  geneset-extractors-liger:md_liger \
  python LIGER/src/run_liger_h5ad_batch.py \
    --input_root /inputs \
    --out_root /liger_outputs \
    --dataset_column donor_id \
    --cell_type_column cell_type__kp \
    --organism human \
    --genome_build hg38
```

If your h5ad metadata uses different columns, override `--dataset_column` and
`--cell_type_column`.

## Inputs

The batch runner expects `.h5ad` files anywhere under the mounted input root.
With the sample tree, examples are:

- `/inputs/Kidney/Vascular Smooth Muscle Cell Pericyte.h5ad`
- `/inputs/Kidney/distal tubule epithelial cell.h5ad`
- `/inputs/Pancreas/macrophage.h5ad`

## Outputs

One output directory is created per input file under `OUTPUT_ROOT`, preserving
the relative input subdirectory and using the h5ad stem as the final directory
name.

Examples:

- host: `LIGER/outputs/docker_run/Kidney/Vascular_Smooth_Muscle_Cell_Pericyte/`
- host: `LIGER/outputs/docker_run/Pancreas/macrophage/`

Each run directory contains:

- `prepare_summary.json`
- `subsets_manifest.tsv`
- `subsets/all/run_liger.sh`
- `subsets/all/run_geneset_extractors_from_liger.sh`
- `subsets/all/liger_out/<program>/gene_loadings.tsv`
- `subsets/all/liger_out/<program>/gene_programs.txt`
- `subsets/all/liger_out/<program>/geneset_extractors_programs/`

The batch manifest is written to:

- host: `LIGER/outputs/docker_run/run_manifest.json`
