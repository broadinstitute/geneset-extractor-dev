# Review policy

Run `python3 -m submission_tools validate --submission <library>` before review.
Errors block approval. Warnings require review but do not block validation.

The wrapper boundary scan rejects analytical-package imports; GMT writing;
normalization, differential-analysis, ranking, statistics, and gene-mapping
heuristics; and direct provenance graph construction. A narrowly justified,
documented exception can list its finding code in
`deviations.allow_wrapper_findings`. This mechanism records an exception; it is
not permission to move substantive logic out of DIG.

The scanner deliberately skips a directory without `submission.yaml`, so it
does not retroactively fail GTEx, MoTrPAC, HuBMAP, LINCS_L1000, or another
legacy library. New libraries must comply from their first submitted scaffold.

Paired PR sequence: test the DIG code PR; create/test the wrapper/config PR;
pin the wrapper to the exact DIG commit; run integration at that commit; merge
DIG; update the wrapper pin if needed; then merge the wrapper PR.
