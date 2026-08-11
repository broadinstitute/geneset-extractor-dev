# IGVF

IGVF Perturb-seq adoption. The DIG `igvf_perturbseq` workflow performs all
long-form differential-expression parsing, filtering, direction assignment,
ranking, and construction of the signed term-gene table. This wrapper only
declares the released IGVF inputs and dispatches DIG per analysis set.

Download the declared public source inputs, then reproduce the complete library:

```bash
bash reproduction/download_inputs.sh /path/to/inputs/IGVF
IGVF_INPUTS_ROOT=/path/to/inputs/IGVF bash reproduction/reproduce.sh
```

For the committed small fixture, run `bash reproduction/reproduce.sh --smoke`.
