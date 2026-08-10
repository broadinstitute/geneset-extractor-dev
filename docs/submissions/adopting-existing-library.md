# Adopting an existing library

Use this path when gene sets were produced outside the submission framework.
It inventories the old directory without changing it, then creates a separate
normal submission scaffold. It does not provide a weaker legacy standard.

```bash
python3 -m submission_tools adopt --existing ../old_library --library-id MY_LIBRARY --output MY_LIBRARY
```

Review `MY_LIBRARY/adoption/adoption_report.md` and give
`AI_ADOPTION_PROMPT.md` to a coding agent. Every intermediate must be either a
declared source input or produced by committed code. Substantive processing,
statistics, mapping, ranking, and gene-set construction belong in
`dig-gene-set-extractors`; this repository remains wrapper-only.

After migration, run ordinary validation and compare outputs:

```bash
python3 -m submission_tools validate --submission MY_LIBRARY/submission.yaml --dig-repo ../dig-gene-set-extractors --smoke --receipt-out MY_LIBRARY/run_receipt.json
python3 -m submission_tools compare-legacy --library MY_LIBRARY
python3 -m submission_tools adoption-status --library MY_LIBRARY
```

`READY` never bypasses normal submission validation. Use the usual paired-PR
and review process after the migration is complete.
