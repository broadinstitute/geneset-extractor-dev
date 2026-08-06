# Contributor workflow for a new library

**All substantive data processing and gene-set generation logic belongs in
`dig-gene-set-extractors`. `geneset-extractor-dev` may configure, dispatch,
execute, refresh, and publish that logic, but must not independently implement
it.**

Begin with the **New gene-set source proposal** issue form. It records the
source, its access and license terms, the biological meaning of a set, the
closest existing pattern, and whether DIG work is expected. Resolve the source
and architecture questions before building a library.

Then follow the paired-PR sequence:

1. Create the DIG code PR when a workflow, converter, or reusable processing
   change is needed. Test it in `dig-gene-set-extractors`.
2. Create the wrapper/config PR in this repository using the **New-library
   submission** PR template. Include `submission.yaml`, manifests, thin
   orchestration, and reproduction metadata.
3. Pin the wrapper manifest to the exact full DIG commit produced by the DIG
   PR. Ready submissions require a 40-character SHA.
4. Run both repositories' tests independently, then run the wrapper's
   coordinated validation against that exact local DIG checkout and its smoke
   fixture.
5. Merge the DIG PR. If its final merge commit differs from the tested pin,
   update and revalidate the wrapper pin.
6. Merge the wrapper PR after the required
   `validate-new-library-submissions` check passes.

Draft submissions may use the documented commit and paired-PR placeholders,
but they cannot claim ready status. CI never runs download scripts or accesses
controlled data. See [review-policy.md](review-policy.md) and
[reproduction-contract.md](reproduction-contract.md) for the review and
reproduction requirements.

No `CODEOWNERS` file is included yet because this repository does not define a
maintainer ownership pattern. A maintainer should make that assignment before
automatic review routing is introduced.
