# Adopt a trusted existing submission

Use one of the four self-contained tutorials below. The **recommended primary
mode** is local AI authoring followed by remote/HPC full reproduction: it keeps
large inputs and expensive work off the coding workstation while preserving a
strict full-reproduction gate before submission.

All substantive data processing, statistics, gene mapping, ranking, and
gene-set construction belong in `dig-gene-set-extractors`. The wrapper remains
configuration, dispatch, runtime, provenance refresh, and publishing only.

| Scientific goal | Compute location | Tutorial |
| --- | --- | --- |
| Exact, set-equivalent reproduction | Local authoring; remote full run | **[Recommended: exact reproduction, local → remote](adopting-exact-reproduction-local-to-remote.md)** |
| Scientific comparability when historical data cannot be recovered exactly | Local authoring; remote full run | **[Recommended: scientific reimplementation, local → remote](adopting-scientific-reimplementation-local-to-remote.md)** |
| Exact, set-equivalent reproduction | One machine | [Exact reproduction, single machine](adopting-exact-reproduction-single-machine.md) |
| Scientific comparability | One machine | [Scientific reimplementation, single machine](adopting-scientific-reimplementation-single-machine.md) |

Use `exact_reproduction` only when every required full legacy output can be
compared set-equivalently. Use `scientific_reimplementation` when historical
inputs or implementation details cannot be recovered exactly; it requires a
source assessment, declared comparability metrics, and scientific review
before a submission is ready.

For technical details of handoffs and `input-bindings.yaml`, see
[remote-reproduction.md](remote-reproduction.md). For architecture and review
rules, see [adopting-existing-library.md](adopting-existing-library.md) and
[review-policy.md](review-policy.md).
