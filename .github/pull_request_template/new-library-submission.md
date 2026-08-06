<!--
Use this specialized template for a new-format library that includes submission.yaml.
The normal repository PR experience remains unchanged: append
?template=new-library-submission.md to the new-PR URL when needed.
-->

## New-library submission

- Wrapper library path:
- `submission.yaml` path:
- Paired DIG PR (URL, or `N/A` with justification):
- Pinned DIG commit (full 40-character SHA for ready submissions):
- Submission status (`draft` or `ready`):

## Reproduction and inputs

- Full reproduction command:
- Smoke command:
- Input manifest path:
- Expected-output manifest path:
- Source access restrictions and any reviewer access prerequisites:

## Boundary and reproducibility confirmations

- [ ] All code needed to transform declared source inputs into final gene sets is included in the paired repositories.
- [ ] No manual transformation, private script, or unexplained precomputed intermediate is required.
- [ ] Substantive preprocessing, statistical analysis, normalization, differential testing, gene mapping, ranking, gene-set construction, and reusable converters are implemented in `dig-gene-set-extractors`.
- [ ] This repository contains only configuration, dispatch, execution, refresh, provenance/metadata orchestration, and publishing integration.
- [ ] I declared every intentional exception in `submission.yaml` under `deviations`.

## Validation

Commands run and results (include output or links to CI):

```text
python3 -m submission_tools validate --submission <library>/submission.yaml
python3 -m submission_tools validate --submission <library>/submission.yaml --dig-repo ../dig-gene-set-extractors --smoke
```

Additional validation notes:

## Reviewer notes

- Closest existing pattern:
- Deviations from the standard architecture:
- Open questions or follow-up work:
