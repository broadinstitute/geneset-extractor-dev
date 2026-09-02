# Independent legacy-library adoption and comparability plan

## Purpose

Some legacy gene-set libraries were developed independently of the DIG and
wrapper architecture. Their scripts may download publicly available data from
hard-coded URLs, use input filenames that are not currently manifested, and
write GMT files directly. The legacy implementation is useful scientific
evidence, but is not the target architecture.

The adopted result must be recreated as a standard coordinated library:

```text
legacy scripts, public data references, and legacy GMTs
                    ↓  read-only specification and evidence
new reusable DIG workflow/converter and tests
                    ↓  exact pinned DIG commit
thin geneset-extractor-dev configuration and dispatcher
                    ↓
smoke/full reproduction, provenance, and comparison report
```

All substantive source-data processing, normalization, statistical analysis,
gene mapping, ranking, and GMT construction belong in
`dig-gene-set-extractors`. `geneset-extractor-dev` remains responsible only
for configuration, model/partition enumeration, DIG invocation, runtime
launch, metadata/provenance refresh, and publishing-compatible orchestration.

This plan does not preserve independent analysis scripts in the wrapper or
create a second implementation framework.

## Why a second comparison policy is needed

There are two materially different adoption cases.

| Adoption class | Source-data certainty | Expected legacy comparison | Ready criterion |
| --- | --- | --- | --- |
| `exact_reproduction` | The original inputs/releases and effective processing are known and obtainable. | Exact set-equivalent GMT comparison. | Every declared full mapping is set-equivalent. |
| `scientific_reimplementation` | The original code is inspectable, but a public source has unclear, mutable, or unavailable historical versioning. | Quantified scientific comparability; exact equality is not asserted. | Reproduction, provenance, predefined metrics, documented source uncertainty, and explicit maintainer review all pass. |

`scientific_reimplementation` is not a lower-quality silent fallback. It is a
separate, explicit claim: the new DIG implementation follows the recoverable
scientific method and produces a documented close result from the best
identified public source release. It must never be labelled `set_equivalent`
when it is not exact.

## Proposed submission manifest extension

Keep the existing `adoption.reference_outputs` mapping and add an additive
`adoption.comparison_policy` object. Existing adopted submissions remain
`exact_reproduction` by default and require no migration.

```yaml
adoption:
  comparison_policy:
    mode: scientific_reimplementation
    reason: >
      The legacy script downloads a public provider file whose historical
      release was not versioned. The current provider release is documented
      below and differs from the archived legacy input checksum.
    source_version_assessment:
      legacy_input_availability: unavailable
      reproduction_input_version: provider-release-2026-08
      confidence: best_available_public_release
      evidence_paths:
        - adoption/source_assessment.md
        - reproduction/input_manifest.tsv
    required_review:
      status: pending
      approval_reference: TBD
  reference_outputs:
    - legacy: /read-only/legacy/genesets.gmt
      regenerated: outputs/full/genesets.gmt
      comparison: scientific_comparability
      scope: full
      metrics:
        min_named_set_recall: 0.95
        min_gene_set_jaccard_median: 0.90
        min_gene_set_jaccard_min: 0.60
        max_unmapped_legacy_sets: 0
      mapping_file: adoption/gene_set_mapping.tsv
```

For `exact_reproduction`, retain the current form:

```yaml
comparison: set_equivalent
scope: full
```

### Required source assessment

Add `adoption/source_assessment.md` for `scientific_reimplementation`. It must
state:

- every legacy URL, local filename, accession, and release clue discovered;
- whether each historical input was obtained, unavailable, mutable, or
  inferred from a provider release;
- the selected public source URL/stable identifier, observed release/version,
  retrieval date, and checksum when feasible;
- how input differences plausibly affect models or gene sets;
- what scientific parameters were preserved from the legacy scripts;
- all known intentional departures; and
- why the declared metric thresholds are scientifically appropriate.

`input_manifest.tsv` remains authoritative for actual reproduction inputs. It
must not contain a blank, invented, or generic source version merely to make a
manifest validate. Additive fields such as `source_version_confidence` and
`legacy_input_relationship` should be added to the input-manifest contract:

```text
source_version_confidence: exact_historical | provider_release | best_available_public_release | unknown
legacy_input_relationship: identical | documented_successor | inferred_equivalent | unknown
```

Ready scientific reimplementations may use `provider_release` or
`best_available_public_release`, but not `unknown`, and must include the
source assessment and review approval.

## Proposed tooling changes

### 1. Adoption discovery and generated materials

Extend `submission_tools adopt` to generate the following read-only analysis
of the legacy directory:

```text
adoption/
  implementation_inventory.json
  migration_map.yaml
  source_assessment.md
  comparison_plan.md
```

`implementation_inventory.json` should identify executable files, likely entry
points, command-line arguments, hard-coded public URLs, referenced local input
filenames, output GMT paths, imported packages, and likely transformation
stages. It is an aid to recreate the implementation in DIG, not code to copy
into either repository.

`migration_map.yaml` should require completion of:

- each legacy operation and its corresponding DIG module/function;
- the registered DIG workflow/converter identifier;
- DIG fixture and focused test;
- wrapper config, dispatcher, and run launcher;
- source input mapping;
- exact or comparability output mapping; and
- deviations with scientific justification.

The generated `AI_ADOPTION_PROMPT.md` should identify the selected comparison
mode and state that legacy scripts are a read-only specification. It must tell
the agent to recreate all substantive logic in DIG and to use only a thin
wrapper dispatcher.

### 2. DIG implementation requirements

For both comparison modes, the adoption is not ready unless DIG contains:

- a registered workflow/converter identifier;
- reusable source parsing and transformation logic;
- a lightweight fixture and focused test;
- a stable CLI/smoke contract; and
- metadata/provenance generation compatible with the existing DIG contract.

The wrapper manifest pins the exact resulting 40-character DIG commit. The
normal paired DIG PR remains required. An independently developed legacy
script is never accepted as the runtime implementation in the wrapper.

### 3. Wrapper requirements

The wrapper contains only:

- input/model/partition/description configuration;
- a strict `run/` launcher;
- a thin `src/` dispatcher that selects configuration and invokes DIG;
- `reproduction/reproduce.sh` and input/output manifests;
- provenance overlays and output metadata refresh; and
- tiny committed smoke fixtures.

The existing wrapper-boundary validator remains in force. The new comparison
mode is not an allowlist for pandas, statistical analysis, gene mapping, or
GMT writing in the wrapper.

### 4. Static public-input checks

Add a validator that scans submitted legacy inventory/configuration and DIG
workflow configuration for operational URL and input-path references. It
should:

- require every operational public source URL/accession to be declared in
  `input_manifest.tsv` or explicitly classified as documentation-only;
- require local input names to map to a manifest input ID or documented input
  root;
- reject contributor home paths, path traversal, and undeclared private files;
- require a source-assessment entry whenever the historical release cannot be
  confirmed; and
- continue to prohibit automatic download execution in CI.

The validator must not attempt to parse arbitrary legacy code as if it can
prove data lineage. It reports discovered references and requires the adopter
to classify them.

### 5. Comparison engine

Keep the current `set_equivalent` comparison unchanged. Add a separate
`scientific_comparability` engine that accepts an explicit one-to-one mapping
of legacy to regenerated GMT set names and writes a versioned comparison
report. It should calculate at minimum:

- legacy and regenerated set counts;
- mapped, missing, and extra set counts;
- per-set gene intersection, union, precision, recall, and Jaccard index;
- median/minimum Jaccard across mapped sets;
- per-set cardinality change; and
- aggregate up/down or signed-set agreement where the library uses signed
  gene sets.

The comparison must fail if mappings are ambiguous, duplicate, missing for a
required legacy set, or if a declared threshold is not met. It must report
metrics rather than converting a near match into an exact-equivalence claim.

The generated report should be stored under an ignored `work/` location during
execution and its digest/summary recorded in the versioned run receipt. A
small expected report fixture may be committed for tests, but real source data
and generated full GMTs remain untracked.

### 6. Ready-state decision gate

For `exact_reproduction`, preserve current ready behavior: a full
set-equivalent mapping and full provenance contract are mandatory.

For `scientific_reimplementation`, `verify-adoption` may pass only when all of
the following are true:

1. DIG and wrapper architecture/contract checks pass.
2. Smoke reproduction passes using committed fixtures.
3. Full reproduction runs using the declared public source inputs.
4. The full provenance graph links declared inputs through DIG operations to
   materialized outputs without local contributor paths.
5. All required comparability mappings and thresholds pass.
6. `source_assessment.md` is complete and reports no `unknown` ready inputs.
7. The required review field contains an approving PR URL or other approved
   maintainer reference.

The result should read `scientifically comparable; not set-equivalent` in both
the verification summary and run receipt. `submit-adoption` must refuse to
submit a ready scientific reimplementation whose review is still `TBD`.

## Schema and code ownership

| Component | Repository | Ownership |
| --- | --- | --- |
| Reusable implementation, parsing, statistics, mapping, ranking, GMT generation, metadata/provenance creation | `dig-gene-set-extractors` | DIG workflow/converter and tests |
| Source/model/partition configuration, dispatch, reproduction adapter, manifests, publication integration | `geneset-extractor-dev` | Thin wrapper library |
| Adoption inventory, migration map, schema validation, comparison report, workspace verification | `geneset-extractor-dev/submission_tools` | Submission tooling |
| Runtime legacy scripts | Neither final implementation repository | Read-only adoption evidence only |

## Implementation phases

1. Add schema support for comparison mode, source-version confidence, required
   review, and explicit mapping metrics while preserving all current manifests.
2. Generate the adoption inventory, migration map, source assessment template,
   and comparison plan from `adopt`.
3. Extend the prompt and verification messages to select the appropriate
   completion gate.
4. Implement the scientific-comparability report engine and receipt summary.
5. Add ready-state gating and safe static URL/input-reference checks.
6. Add local fixtures and tests, then document contributor/reviewer policy.
7. Add CI coverage for static validation only; CI must not download public data
   or execute untrusted reproduction scripts.

## Tests

Add lightweight tests for:

- unchanged exact-reproduction behavior;
- a valid scientific-reimplementation draft;
- rejection of a ready comparison with `unknown` source version confidence;
- missing source assessment, review approval, DIG identifier, or exact DIG
  SHA;
- mapped sets meeting and failing declared similarity thresholds;
- ambiguous/duplicate/missing set mappings;
- hard-coded source URL or local input reference not declared in the manifest;
- wrapper analysis code still failing boundary validation;
- run receipt recording the comparison mode, report digest, metrics summary,
  and non-equivalence claim; and
- CI discovery and static validation without network access or reproduction.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| A close result is misrepresented as exact reproduction. | Separate comparison modes and terminology; preserve strict `set_equivalent`; record the mode in PR, report, and receipt. |
| Thresholds are chosen after seeing results. | Require thresholds and mapping before final full comparison; record them in the manifest and receipt; require maintainer approval. |
| Public data mutates without versioning. | Require release assessment, retrieval date, checksum where feasible, immutable/archive identifier when available, and explicit confidence classification. |
| Legacy analysis is copied into the wrapper. | Keep boundary validation strict; require a DIG workflow, test, identifier, and commit. |
| CI executes unsafe external code/data access. | Limit CI to static checks and lightweight committed tests; full reproduction remains explicit local validation. |

## Non-goals

- Do not change existing exact-adoption behavior or output formats.
- Do not permit arbitrary analytical scripts in `geneset-extractor-dev`.
- Do not treat undocumented source changes as acceptable.
- Do not claim that a run receipt or metric threshold cryptographically proves
  reproducibility or scientific equivalence.
