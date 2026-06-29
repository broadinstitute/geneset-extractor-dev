# HZ1 Historical Wrapper Notes

This file tracks the original MoTrPAC `HZ1` wrapper:

- wrapper: `build_motrpac_rat_endurance_gmt_hz1.py`
- source script: `notebooks_adapted/build_motrpac_rat_endurance_gmt.py`

## Current Status

The active pipeline no longer uses this wrapper as the runtime entrypoint.

Current runtime shape:

- workflow:
  - `geneset_extractors.cli workflows motrpac_released_dea`
- extractor:
  - `geneset_extractors.cli convert signed_term_gene`

The extractor now runs with a notebook-faithful ternary-matrix emission mode so the final GMT behavior is closer to the standalone script than the generic grouped-row converter path.

So the released-DEA processing logic now lives in `dig-gene-set-extractors`, and the MoTrPAC repo is back to being a thin wrapper around resolved `dig` commands.

## Why Keep This File

It still documents:

- the original notebook-replica entrypoint
- the source standalone script that the new `dig` workflow was adapted from

That makes it easier to compare the historical wrapper-based implementation against the current dig-native one.
