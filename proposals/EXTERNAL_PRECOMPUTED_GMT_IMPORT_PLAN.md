# External precomputed GMT import plan

## Purpose

Add an additive import path for one documented external source release that
supplies one or more already-generated GMT files.  Each GMT is assigned a
stable `model_id`, materialized into a conventional model output directory,
and receives standard DIG metadata plus legacy-JSON and DAPPER-YAML provenance
sidecars.  The path must never imply that the repository regenerated the
scientific gene sets when the original code is unavailable.

## Ownership

`dig-gene-set-extractors` owns a small reusable `external-precomputed-import`
command.  It validates an existing GMT, copies it unchanged, calculates its
checksum, and generates metadata/provenance describing a documented external
generation operation followed by a verified import operation.  It performs no
scientific processing, mapping, ranking, or GMT construction.

`geneset-extractor-dev` owns the multi-model manifest, source documentation,
thin shell dispatch, input/output declarations, submission scaffold,
validation, and publishing selection.  It does not construct provenance graph
nodes itself; it invokes DIG.

## Input contract

The wrapper command accepts a single `source.yaml` and a tabular GMT manifest.

```yaml
schema_version: "1"
source:
  name: Colleague gene-set release
  uri_or_identifier: doi:10.example/release
  release: "2026-09-01"
  license: CC-BY-4.0
  access_restrictions: public
  organism: human
  genome_build: hg38
  assay: rna_seq
  data_type: precomputed_gene_sets
  documentation: https://example.org/methods
  regeneration_status: incomplete_code
```

```text
model_id	display_name	source_gmt_path	sha256	description	partition_id
tissue_a	Tissue A	/path/tissue_a.gmt		Published gene sets for tissue A	tissue_a
```

`model_id`, display name, source path, description, and partition are required.
The importer computes a missing checksum, but rejects a supplied checksum that
does not match.  Source GMT files remain read-only and are not committed.

## Generated library

The wrapper creates an `external_precomputed_import`-classified generic
library with source/model manifests, a strict reproduction/import script, an
output manifest containing one standard output bundle per model, and explicit
attestations that regeneration code is incomplete.  The runtime command takes
an external input root, checks each GMT, and delegates each model to DIG.

Each materialized model output contains:

```text
genesets.gmt
geneset.meta.json
geneset.provenance.legacy.json
geneset.provenance.dapper.yaml
```

## Delivery phases

Phase 1 provides `submission_tools import-external-library` as a direct,
non-destructive library scaffold command. It validates the read-only source
GMT inventory, records relative runtime paths/checksums, and creates the
wrapper package. Phase 2 may add the existing isolated fork/workspace and PR
automation around that already-generated package; it is deliberately not a
prerequisite for truthful import or standard output generation.

## Truthfulness and readiness

The import provenance describes the externally documented generation method
and the repository's checksum-verified import.  It never claims that DIG or
the wrapper performed the external scientific analysis.  Ready imports require
a stable source release, licenses/access terms, every GMT checksum, source
documentation, explicit incomplete-code attestation, and a reviewed import
classification.  Existing generated-library and legacy-library contracts are
unchanged.

## Publishing

The wrapper publisher must discover both current sidecars and include only
model-selected GMTs, metadata, legacy provenance, and DAPPER provenance when
publishing provenance-selected outputs.  Source directories and temporary
runtime work remain excluded.

## Tests

Use only synthetic two-model GMT fixtures.  Cover valid multi-model import,
duplicate model IDs, missing/malformed GMT, checksum mismatch, sidecar
creation, external-origin metadata, and current-sidecar publisher discovery.
