# GTEx gene-set library modernization

This library retains its historical launchers and model configuration while
adding the current submission contract. `submission.yaml` is deliberately a
draft until every active model family has a pinned DIG implementation, declared
released inputs, a complete output/provenance contract, and full comparison to
the authoritative GTEx outputs.

The submitted wrapper boundary is [`src/dispatch_gtex_submission.py`](src/dispatch_gtex_submission.py). It dispatches
the existing DIG-backed AB4 age-binned path with a small, synthetic smoke
fixture. Historical scripts outside that directory are compatibility material,
not new wrapper implementation.
