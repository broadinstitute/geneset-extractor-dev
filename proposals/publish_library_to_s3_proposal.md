# Proposal: Publish Library Outputs And Inputs To Mirrored S3 Paths

This proposal describes a repository-level publishing method for `geneset-extractor-dev/` that:

1. takes a local output directory containing model results
2. takes an AWS S3 URI that mirrors that local output root
3. takes an AWS S3 URI where provenance-discovered rerun inputs should be published
4. checks whether the mirrored files already exist in S3
5. uploads only the new files to S3 unless `--overwrite` is set

The goal is to make publication reproducible, explicit, and compatible with the existing provenance model that already understands local-to-remote mirror prefixes.

## Goal

Given a local output tree such as:

- `geneset-extractor-dev/GTEx/outputs/...`
- `geneset-extractor-dev/MoTrPAC/outputs/...`
- or a run-specific output root like `./gtex_outputs_raw_runtime_test/...`

publish that tree under a mirrored S3 prefix such as:

- `s3://dig-gene-set-data/gtex/...`
- `s3://dig-gene-set-data/motrpac/...`

without reuploading files that are already present.

## Proposed Interface

Add a new top-level publisher script:

- `geneset-extractor-dev/src/publish_library_to_s3.py`

and matching shell wrapper:

- `geneset-extractor-dev/run/publish_library_to_s3.sh`

### Required CLI inputs

- `--local_output_root`
  - local directory containing generated outputs
- `--s3_output_root`
  - destination S3 URI prefix mirroring the local output root
- `--s3_input_root`
  - destination S3 URI prefix for provenance-discovered rerun inputs

### Optional CLI inputs

- `--manifest_out`
  - optional TSV/JSON manifest path describing the publish decision
- `--overwrite`
  - if set, allow replacing objects already present in S3
- `--dry_run`
  - compute mirror paths and existence checks without uploading
- `--aws_cli_bin`
  - explicit AWS CLI executable, default `aws`
- `--require_hash_match`
  - if an S3 object exists, compare local checksum to remote metadata/etag when possible
- `--update_provenance_json`
  - if set, rewrite mirrored paths into provenance-oriented summary outputs

## Mirror Semantics

The publish rule should be:

- local relative path under `local_output_root`
- becomes the same relative path under `s3_output_root`

and provenance-discovered rerun inputs:

- absolute local path from provenance, with the leading slash removed
- becomes the same relative path under `s3_input_root`

Example:

- local:
  - `/data/runs/gtex_outputs/genesets/adipose_tissue/models/AB1/tissue_extractor/genesets.gmt`
- `local_output_root`:
  - `/data/runs/gtex_outputs`
- relative path:
  - `genesets/adipose_tissue/models/AB1/tissue_extractor/genesets.gmt`
- S3 mirror:
  - `s3://bucket/prefix/genesets/adipose_tissue/models/AB1/tissue_extractor/genesets.gmt`

Input example:

- local:
  - `/data/inputs/GTEx/v10/GTEx_Analysis_v10_RNASeQCv2.4.2_gene_reads.gct.gz`
- relative path:
  - `data/inputs/GTEx/v10/GTEx_Analysis_v10_RNASeQCv2.4.2_gene_reads.gct.gz`
- S3 mirror:
  - `s3://bucket/input-prefix/data/inputs/GTEx/v10/GTEx_Analysis_v10_RNASeQCv2.4.2_gene_reads.gct.gz`

This is intentionally simple and consistent with how provenance mirror prefixes already behave.

## Input Resolution

The publisher should resolve required rerun inputs from the final output provenance files:

- scan `extractor/geneset.provenance.json` under `local_output_root`
- collect file nodes that are external to `local_output_root`
- treat those external files as the publishable rerun inputs needed to reproduce the final GMTs

This keeps the published input set aligned with what the recorded provenance actually says is needed for rerun, rather than relying on a library-specific heuristic list.

All external provenance file paths should be mirrored under `s3_input_root` by stripping the leading slash from the local path.

## File Discovery

The script should recursively walk `local_output_root` and build a candidate file list.

Recommended default behavior:

- include regular files only
- skip directories and symlinks
- skip obvious transient files:
  - `.DS_Store`
  - `Thumbs.db`
  - editor swap files
  - `__pycache__`
- otherwise include all output artifacts:
  - `gmt`
  - `tsv`
  - `tsv.gz`
  - `json`
  - `md`
  - `log`
  - `pdf`
  - `png`

This is better than a narrow allowlist because the output trees intentionally contain companion manifests, logs, and markdown files that should be published with the biological results.

## S3 Existence Check

For each candidate local file:

1. compute its mirrored S3 URI
2. query whether the S3 object exists
3. classify the object as:
   - `missing`
   - `present`
   - `present_but_overwrite_requested`

Recommended implementation:

- use `aws s3api head-object`
- parse bucket/key from the S3 URI

Why:

- `head-object` is explicit and script-friendly
- it avoids listing an entire prefix when only one file is needed

### Optional stronger comparison

If `--require_hash_match` is enabled:

- compute local SHA256
- compare against stored object metadata if available
- otherwise fall back to:
  - size comparison
  - or overwrite policy

This is optional because ETag is not a reliable content hash for multipart uploads.

## Upload Behavior

Default behavior:

- upload only files whose mirrored S3 object is missing

If `--overwrite` is passed:

- upload both missing and present files

Recommended implementation:

- per-file `aws s3 cp <local> <s3>`

Why:

- simpler audit trail
- easier per-file failure handling
- direct correspondence between local path, mirror path, and upload decision

Bulk `aws s3 sync` should not be the primary method here because:

- it makes per-file classification less explicit
- it is harder to emit a precise publish manifest

## Publish Manifest

The script should always produce a manifest, either to a caller-provided path or by default under:

- `<local_output_root>/publish_library_manifest.tsv`

Suggested columns:

- `local_path`
- `relative_path`
- `s3_uri`
- `size_bytes`
- `status`
  - `missing`
  - `present`
  - `uploaded`
  - `skipped_existing`
  - `overwritten`
  - `failed`
- `upload_attempted`
- `error_message`

Optional companion JSON:

- `<local_output_root>/publish_summary.json`

This makes publication inspectable and scriptable.

## Provenance Rewriting

Uploaded provenance artifacts should not preserve any local filesystem paths.

For every uploaded:

- `*.provenance.json`
- `*.provenance_graph.json`

the publisher should stage a rewritten copy for upload such that:

- output file paths point at the mirrored `s3_output_root`
- provenance-discovered rerun input paths point at the mirrored `s3_input_root`
- commands embedded in provenance are rewritten to use those mirrored S3 paths
- `local_id`
- `dcc_url`
- `drc_url`
- `command`
- `observed_command`

contain no local filesystem paths after rewriting

The local run tree should not be mutated in place. Rewriting should happen only in staged upload copies.

## Proposed Non-Destructive Policy

The publisher should:

- never delete local files
- never move local files out of the output tree
- never delete remote S3 objects unless a separate explicit cleanup command is introduced later

So “physically moves the new files to S3” should mean:

- transfers/uploads them to S3
- not removes them locally after upload

This is the safer default for scientific outputs and provenance review.

## Failure Handling

If an upload fails:

- record the failure in the publish manifest
- continue with other files
- return nonzero exit status at the end if any failures occurred

This gives the user:

- a complete publish report
- partial success when possible

## Logging

Write a companion log file:

- `<local_output_root>/publish_library_to_s3.log`

Contents should include:

- invocation command
- discovered file count
- skipped-existing count
- uploaded count
- failed count
- final exit summary

## Repository Placement

Recommended new files:

- `geneset-extractor-dev/src/publish_library_to_s3.py`
- `geneset-extractor-dev/run/publish_library_to_s3.sh`
- `geneset-extractor-dev/proposals/publish_library_to_s3_proposal.md`

Optional future shared docs:

- `geneset-extractor-dev/README.md`
  - add a short note linking to the publisher

## Example Command

```bash
bash geneset-extractor-dev/run/publish_library_to_s3.sh \
  --local_output_root ./gtex_outputs_raw_runtime_test \
  --s3_output_root s3://dig-gene-set-data/gtex/test_publish \
  --s3_input_root s3://dig-gene-set-data-inputs/gtex/test_publish \
  --dry_run
```

Real upload:

```bash
bash geneset-extractor-dev/run/publish_library_to_s3.sh \
  --local_output_root ./gtex_outputs_raw_runtime_test \
  --s3_output_root s3://dig-gene-set-data/gtex/test_publish \
  --s3_input_root s3://dig-gene-set-data-inputs/gtex/test_publish
```

## Recommended First Implementation Scope

Implement only:

- recursive file discovery
- mirror-path construction
- provenance-based rerun-input discovery
- per-file existence checks with `head-object`
- per-file upload with `aws s3 cp`
- manifest and log writing

Do not implement initially:

- remote deletion
- multipart checksum reconciliation
- in-place rewriting of existing output files
- publish batching across multiple roots in one command

That narrower first version is enough to make publication reliable and auditable.

## Summary

The recommended publishing method is:

- input:
  - local `local_output_root`
  - remote `s3_output_root`
  - remote `s3_input_root`
- compute:
  - mirrored S3 path for every output artifact
  - mirrored S3 path for every provenance-discovered rerun input
- check:
  - whether each object already exists in S3
- upload:
  - only missing objects by default
- record:
  - a local publish manifest and log

This keeps publication explicit, compatible with existing provenance mirror concepts, and safe for scientific output trees.
