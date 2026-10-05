# GaultonLab source assessment

The twelve supplied GMTs are the direct generation inputs and the canonical
library artifacts. Their scientific generation code is upstream at
https://github.com/kjgaulton/liana-ccc-pipeline, but was not supplied as a
reproducible pinned execution environment with the inputs needed to recreate
these particular files.

This wrapper therefore uses DIG's `external-import` contract: it validates
ordinary GMT structure, verifies the per-file SHA-256 declared in
`config/task_manifest.tsv`, then copies each artifact byte-for-byte. It does
not alter gene-set names, GMT descriptions, member ordering, membership, or
perform a new cell-cell communication analysis.
