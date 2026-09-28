# GTEx modernization environment

The submitted path requires Python 3, the pinned
`dig-gene-set-extractors` checkout, and the dependencies declared by that
repository. Full GTEx runs may additionally require the DIG-supported
statistical backend selected by the model manifest. The committed smoke task
uses the `AB4` lightweight backend and requires no downloaded GTEx data.

Set `DIG_REPO` to the checkout used for local execution. Generated artifacts
are written beneath `SUBMISSION_WORK_DIR`, never beneath this library.
