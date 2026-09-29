# GTEx modernization environment

The submitted path requires Python 3, the pinned
`dig-gene-set-extractors` checkout, and the dependencies declared by that
repository. Full GTEx runs may additionally require the DIG-supported
statistical backend selected by the model manifest. The committed smoke task
uses the `AB4` lightweight backend and requires no downloaded GTEx data.

Set `DIG_REPO` to the checkout used for local execution. Full library
reproduction requires GTEx V10 inputs for AB/AC models, GTEx V8 inputs plus
human-gene-info for HZ1, GENCODE v39 GTF, and an R-enabled DIG environment.
Generated artifacts are written beneath `SUBMISSION_WORK_DIR`, never beneath
this library.
