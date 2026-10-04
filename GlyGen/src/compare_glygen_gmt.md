# Changes from the handoff comparator

This companion supersedes the handoff's `compare_gmt.py` with deterministic JSON output while preserving its parsing rule: GMT genes begin at column three, so both blank and populated description columns are handled correctly. It reports candidate/target set counts, exact matches, both shared-term and global `(term, gene)` recall, precision, and Jaccard, plus set-size distribution.
