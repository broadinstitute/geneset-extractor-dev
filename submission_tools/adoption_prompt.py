"""Pattern-aware instructions for agents adopting legacy libraries.

The prompt is deliberately guidance, not a second workflow specification.  It
points contributors to the established wrapper layout while keeping all
scientific and reusable extraction work in DIG.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


PATTERN_GUIDANCE = {
    "gtex": {
        "wrapper": "enumerate model × tissue/partition combinations and pass declared input and configuration paths",
        "dig": "a bulk RNA-seq, age, or differential-expression workflow",
    },
    "motrpac": {
        "wrapper": "enumerate tissue/model families and select the declared source manifests",
        "dig": "a transcriptomics workflow, including source processing, mapping, and model-specific analysis",
    },
    "hubmap": {
        "wrapper": "enumerate released model versions and source releases",
        "dig": "ASCT+B parsing, optional augmentation, gene mapping, and gene-set construction",
    },
    "lincs_l1000": {
        "wrapper": "select the model and its declared source matrix",
        "dig": "perturbation-matrix processing, ranking, gene mapping, and gene-set construction",
    },
    "generic": {
        "wrapper": "perform minimal model/partition selection and dispatch",
        "dig": "a registered or newly contributed reusable DIG workflow or converter",
    },
}


def _paths(inventory: dict[str, Any], key: str) -> str:
    values = [str(item.get("path", "")) for item in inventory.get(key, []) if isinstance(item, dict) and item.get("path")]
    return ", ".join(values) if values else "none detected"


def architecture_guidance(pattern: str, inventory: dict[str, Any]) -> str:
    profile = PATTERN_GUIDANCE.get(pattern, PATTERN_GUIDANCE["generic"])
    return f"""## Target architecture

Use the established wrapper shape as a naming and orchestration reference:

```text
<Library>/
  config/     # model list, optional model manifest, partitions, descriptions
  run/        # strict shell launcher only
  src/        # selection/dispatch code only
  reproduction/ expected/ tests/fixtures/
```

For the selected `{pattern}` pattern, the wrapper should {profile['wrapper']}.
The corresponding DIG responsibility is {profile['dig']}.

Place code by responsibility:

- **DIG:** source-table parsing and validation, normalization, statistics,
  differential testing, gene mapping, ranking, thresholding, GMT/gene-set
  construction, reusable converters, and scientific workflow fixtures/tests.
- **Wrapper:** `submission.yaml`; model, partition, manifest, and description
  configs; thin selection/dispatch; reproduction metadata; receipt refresh;
  output publication integration.

The wrapper must not read and transform biological matrices, implement gene
mapping/ranking/statistics, or write GMT files. Existing GTEx, MoTrPAC,
HuBMAP, and LINCS_L1000 directories are structural references only: some
pre-date this boundary and are not permission to copy substantive wrapper
logic.

## Evidence to resolve

- Legacy gene-set outputs: {_paths(inventory, 'gene_set_outputs')}
- Possible unexplained intermediates: {_paths(inventory, 'possible_intermediates')}
- Legacy code requiring classification: {_paths(inventory, 'code_files')}
- Manual-step findings: {_paths(inventory, 'manual_step_findings')}
- Nonportable-path/security findings: {_paths(inventory, 'nonportable_findings')}
- Environment files to translate into the declared environment: {_paths(inventory, 'environment_files')}

Classify every item as a declared source input, committed DIG-produced
intermediate, wrapper orchestration/configuration, generated output, or a
blocker. Do not accept unexplained precomputed intermediates.

## Required migration sequence

1. Read the inventory, dependency map, adoption report, and every legacy output
   reference before modifying either repository.
2. Inspect the pinned DIG checkout and reuse a scientifically equivalent
   contract where possible:

   ```bash
   geneset-extractors submission list
   geneset-extractors submission describe <identifier>
   geneset-extractors submission validate <identifier>
   ```

3. Add missing substantive logic, its fixture, tests, and registered contract
   in DIG first. Pin the exact resulting DIG commit in the wrapper manifest.
4. In the wrapper, create `config/model_list.tsv`, an optional model manifest,
   a partition/tissue list when applicable, and
   `config/model_description_templates.tsv`. Add only a strict `run/` launcher
   and a thin `src/` model dispatcher.
5. Declare every external input and fixture in `input_manifest.tsv`; add the
   expected-output manifest, smoke reproduction, and an explicit full legacy
   reference mapping. A smoke output is never a substitute for full legacy
   equivalence.
6. Run DIG contract validation, wrapper validation, smoke reproduction, and
   full mapped legacy comparison. Stop for approval before changing scientific
   parameters such as normalization, filtering, mapping, ranking, contrasts,
   thresholds, or model definitions.

A wrapper dispatcher may only select configuration and invoke DIG, for example:

```python
command = [sys.executable, "-m", "geneset_extractors", "workflows", workflow_id,
           "--model-manifest", str(model_manifest), "--model-id", model_id,
           "--out-dir", str(model_output_dir)]
subprocess.run(command, check=True)
```

Its launcher should be similarly thin and strict:

```bash
#!/usr/bin/env bash
set -euo pipefail
exec "${{PYTHON_BIN:-python3}}" src/build_<library>_genesets.py "$@"
```

## Completion criteria

Do not declare adoption complete until every source input is manifested, every
transformation is committed code, declared DIG identifiers validate at the
pinned exact commit, the wrapper-boundary validator passes without unapproved
deviations, smoke reproduction succeeds, a full/reference mapping passes (or
an approved discrepancy is documented), and declared `provenance.contracts`
pass `provenance_complete`. Ready submissions require a full provenance graph
linking declared sources through workflow/operation nodes to materialized gene
set output, plus a ready-valid submission and run receipt.
"""
