# Comprehensive gene-set reporting

`run/summarize_comprehensive_reports.sh` creates a versioned, wrapper-side
report from final GMT files. It does not regenerate gene sets and it does not
modify DIG. The compute contract is `schema_version: "1.0"`.

## Manifest

Use JSON by default (YAML is accepted only when PyYAML is already installed).
All paths are relative to the manifest.

```json
{
  "libraries": [{
    "library_id": "GTEx",
    "models": [{
      "model_id": "HZ1",
      "outputs": [{
        "output_id": "main",
        "gmt": "outputs/GTEx.HZ1.gmt",
        "provenance": "outputs/geneset.provenance.dapper.yaml",
        "legacy_references": [{
          "reference_id": "2023-release",
          "gmt": "legacy/GTEx.2023.gmt",
          "name_mapping": "mappings/GTEx.HZ1.tsv"
        }]
      }]
    }]
  }]
}
```

Legacy references are explicit. A model with no `legacy_references` is valid
and is reported as `not_applicable`. A nonempty mapping must be one-to-one.
An empty mapping compares exact set names directly.

## Local use

Selection is mandatory: use one or more `--library` values or
`--all-libraries`. `--model` further restricts models within the selected
libraries.

```bash
bash run/summarize_comprehensive_reports.sh plan \
  --manifest reporting.json --library GTEx --output-dir reports/gtex

bash run/summarize_comprehensive_reports.sh run \
  --manifest reporting.json --library GTEx --output-dir reports/gtex

bash run/summarize_comprehensive_reports.sh render \
  --library GTEx --output-dir reports/gtex
```

`render` reads only `metrics/*.json` and `metrics/*.genes.txt.gz`, never GMTs.
It fails for missing/incompatible task artifacts unless `--allow-partial` is
specified. `run --resume` skips successful schema-compatible metric files.

Outputs are isolated by run: `manifest.json`, `tasks/`, `metrics/`, `status/`,
and `rendered/`. The rendered directory contains offline `report.html`,
`report.md`, gzipped TSVs, JSON summary, and standalone reports under
`rendered/libraries/<library_id>/`.

### Convert the existing legacy/current TSV

The existing `legacy_current_mapping.tsv` is not itself the comprehensive
manifest. Convert it once; paths that were recorded on another host are
resolved by unique basename under the supplied roots (or the TSV's sibling
`legacy_gmts/`, `current_gmts/`, and `reference_mappings/` directories).

```bash
bash run/summarize_comprehensive_reports.sh convert-tsv \
  --input legacy_current_mapping/legacy_current_mapping.tsv \
  --output legacy_current_mapping/reporting.json
```

When the three file collections are elsewhere, pass `--legacy-root`,
`--current-root`, and `--mapping-root`. The generated JSON keeps paths
relative where possible and is ready for `plan`, `run`, or `submit`.

## Metrics

GMT records are terms with unique nonblank genes. Reported coverage includes
set count, memberships, unique genes, min/median/max sizes, empty sets, and
duplicate-name warnings. Across outputs, set/membership counts are sums while
the overall unique-gene count is a deduplicated union.

For an explicit legacy pair, name recall/precision use exact names. Membership
recall, precision, and Jaccard use explicitly mapped pairs, or exact shared
names when there is no map. Per-term metrics include size differences,
precision, recall, Jaccard, and exact equality. Undefined ratios are `null`
in JSON/TSV and `N/A` in reports; they are never silently converted to zero.

`--dapper-validator /path/to/validator` invokes an installed validator with the
sidecar path and records `PASS`, `FAIL`, or `ERROR`; without one, provenance is
reported as `NOT_RUN` rather than inferred as valid.

## Apptainer and SGE

The local command works in an existing image when the wrapper and inputs are
bound explicitly:

```bash
apptainer exec --cleanenv --bind "$PWD:/work" image.sif \
  bash /work/run/summarize_comprehensive_reports.sh run \
  --manifest /work/reporting.json --all-libraries --output-dir /work/reports/all
```

For SGE, first inspect the generated command. No submission occurs with
`--dry-run`.

```bash
bash run/summarize_comprehensive_reports.sh submit \
  --manifest reporting.json --all-libraries --output-dir reports/all \
  --memory 8G --walltime 04:00:00 --dry-run
```

The generated `run_task.sh` is an absolute executable `qsub` target and uses
`SGE_TASK_ID`; it never submits `qsub ... bash script.sh`. Add
`--apptainer-image image.sif --bind /data:/data:ro` to run workers in a
container. Run `render` only after all task status files are successful; SGE
completion dependencies alone do not establish success.

Known limitation: qsub flags and image contents are site-specific. The wrapper
generates configurable `h_vmem`, `h_rt`, queue, project, bind, and executable
arguments, but does not assume a cluster-specific hold-job syntax.
