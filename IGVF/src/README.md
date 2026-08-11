# Wrapper source boundary

IGVF has no library-specific analytical source in this repository. The wrapper only
acquires declared public inputs and dispatches DIG entry points; all table processing,
filtering, ranking, and GMT construction live in `dig-gene-set-extractors`.
