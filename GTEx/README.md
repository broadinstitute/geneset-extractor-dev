# GTEx gene-set library modernization

This library retains its historical launchers and model configuration while
adding the current submission contract. `submission.yaml` is deliberately a
draft until every active model family has a pinned DIG implementation, declared
released inputs, a complete output/provenance contract, and full comparison to
the authoritative GTEx outputs.

The submitted runtime boundary is [`run/`](run/), led by
[`run/run_submission_models.sh`](run/run_submission_models.sh) and its thin
[`src/dispatch_gtex_submission.py`](src/dispatch_gtex_submission.py) adapter.
It dispatches the existing DIG-backed AB4 age-binned path with a small,
synthetic smoke fixture. Historical scripts remain compatibility material, not
new wrapper implementation.

## Full execution

The declared reproduction contract can run natively with
`reproduction/reproduce.sh`, in a container with
`run/run_submission_models_apptainer.sh`, or as one explicit qsub job with
`run/submit_submission_models_cluster_apptainer.sh --submit`. The Apptainer
launchers require `APPTAINER_IMAGE`, `DIG_REPO`, and `SUBMISSION_WORK_DIR`.
Full mode requires the V10, V8, V8 human-gene-info, and GTF variables listed
in `reproduction/input_manifest.tsv`. It covers every enabled GTEx model over
every configured broad tissue (currently 990 array tasks). Without `--submit`,
the scheduler launcher only prints its planned command.

For a remote Apptainer array run, set the eight full-input variables plus
`APPTAINER_IMAGE`, `DIG_REPO`, and an external `SUBMISSION_WORK_DIR`, then use:

```bash
bash run/submit_submission_models_cluster_apptainer.sh --full
bash run/submit_submission_models_cluster_apptainer.sh --full --submit
```

The first command is a non-submitting review step. The second delegates to the
established GTEx array launcher with the declared V10/V8 input split and writes
outputs under `SUBMISSION_WORK_DIR/genesets/`.

`config/partition_list.tsv`, `config/task_manifest.tsv`,
`expected/output_manifest.tsv`, and `expected/smoke_output_manifest.tsv` are
generated declarative contract files. Regenerate them after changing enabled
models or broad tissues:

```bash
python3 src/generate_submission_manifests.py
```
