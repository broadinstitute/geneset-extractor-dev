# RummaGEO submission wrapper

This directory declares and dispatches the two RummaGEO models: `HZ1` (drug
perturbations) and `HZ2` (gene perturbations). It contains no RummaGEO
selection, label normalization, orthology, gene filtering, or GMT-generation
logic; those scientific operations are implemented by DIG's
`rumma_geo_selection` and `rumma_geo` converters.

`src/run_rummageo_model.py` is the single-model execution entrypoint used by
the dispatcher and cluster-array workers; the dispatcher only resolves inputs
and selected model IDs.

Run the committed smoke fixture:

```bash
SUBMISSION_WORK_DIR=/path/to/output DIG_REPO=../dig-gene-set-extractors \
  bash reproduction/reproduce.sh --smoke
```

For a full run, set the following local-file environment variables, then run
`bash reproduction/reproduce.sh full`:

- `RUMMAGEO_HUMAN_GMT`
- `RUMMAGEO_MOUSE_GMT`
- `RUMMAGEO_QUERY_RECORDS_JSON` (a pinned cached RummaGEO GraphQL response,
  with the notebook search term attached to every record)
- `RUMMAGEO_DRUG_TERMS_JSON` (the pinned SigCom-LINCS drug-term snapshot used
  by `HZ1`)
- `LOCAL_INPUT_SOURCE_MAP_TSV` (the standard `local_path` / `source_uri` map
  used during metadata and provenance refresh)
- `RUMMAGEO_HUMAN_GENE_INFO`
- `RUMMAGEO_MOUSE_GENE_INFO`
- `RUMMAGEO_GENE_ORTHOLOGS`

`RUMMAGEO_GENE_LEGACY_GMT` and `RUMMAGEO_DRUG_LEGACY_GMT` are optional
validation targets. They are passed only to DIG's diagnostic comparison and
cannot alter reconstructed memberships.

For Apptainer, additionally set `APPTAINER_IMAGE` and run:

```bash
bash run/run_submission_models_apptainer.sh --full
```

For SGE/qsub cluster submission, inspect the generated per-model array command
first, then submit it explicitly:

```bash
bash run/submit_submission_models_cluster_apptainer.sh --full
bash run/submit_submission_models_cluster_apptainer.sh --full --submit
```

After a successful full run, refresh the completed models into the standard
publishable metadata and provenance form:

```bash
bash run/submit_submission_models_cluster_apptainer.sh --full --refresh-metadata-and-provenance
bash run/submit_submission_models_cluster_apptainer.sh --full --refresh-metadata-and-provenance --submit
```

Pass `--model-id HZ1` or `--model-id HZ2` to
the submitter to run one model. Resource and container settings are described
in `environment.modernization.md`.

The wrapper generates `workflow/selection/selection_manifest.tsv` separately
for each model before membership reconstruction. It uses only the pinned query
and drug-term snapshots; it does not query the live API or infer selections
from a legacy GMT. It also generates `workflow/source_manifest.json` from the
standard local input source map, using each input file's SHA-256 as its pinned
version identifier.
