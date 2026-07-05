#!/usr/bin/env python3
"""Compatibility entrypoint for KidsFirst HZ2 curation.

The HZ2 curation implementation is owned by DIG:
``geneset_extractors.workflows.kidsfirst_curate``.

This wrapper is kept so older local commands that call
``KidsFirst/src/curate_disease_genesets.py`` fail less abruptly, but new
provenance, metadata, model sidecars, and run scripts should cite the DIG
workflow directly.
"""

from geneset_extractors.workflows.kidsfirst_curate import main


if __name__ == "__main__":
    main()
