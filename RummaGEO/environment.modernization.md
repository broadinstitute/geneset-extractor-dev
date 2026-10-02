# RummaGEO runtime contract

The wrapper supports local, Apptainer, and SGE/qsub execution. Set
`SUBMISSION_WORK_DIR` outside this checkout, `DIG_REPO` to the companion DIG
checkout, and `APPTAINER_IMAGE` for container execution. `APPTAINER_PYTHON_BIN`
defaults to `python`; use it when the image exposes another interpreter.

Full all-model runs require the seven `RUMMAGEO_*` paths listed in
`reproduction/input_manifest.tsv`; an `HZ2`-only run does not require the
`HZ1` drug-term snapshot. `LOCAL_INPUT_SOURCE_MAP_TSV` is also required for a
full run and replaces the former library-specific source manifest. Optional legacy GMT variables are
comparison-only inputs. The cluster submitter is a dry run unless `--submit`
is provided; its defaults are `16G` and `24:00:00` for full runs and `4G` and
`01:00:00` for smoke runs. Override these with `SUBMISSION_ARRAY_MEMORY`,
`SUBMISSION_ARRAY_WALLTIME`, `SUBMISSION_SMOKE_MEMORY`, and
`SUBMISSION_SMOKE_WALLTIME`.

After a completed full run, invoke the submitter with
`--refresh-metadata-and-provenance`. It runs the shared refresh utility for
each selected model, using `config/model_description_templates.tsv` by default
or `DESCRIPTION_TEMPLATE_TSV` when supplied. It forwards
`LOCAL_INPUT_SOURCE_MAP_TSV`, `PROVENANCE_MIRROR_LOCAL_PREFIX`, and
`PROVENANCE_MIRROR_REMOTE_PREFIX` to that utility.
