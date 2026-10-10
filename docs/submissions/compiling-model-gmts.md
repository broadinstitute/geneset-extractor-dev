# Compiling split model GMT outputs

The wrapper-side compiler combines final `genesets.gmt` files from split,
tissue-specific, or other grouped output directories for one model. It never
changes the source run tree and refuses to overwrite the compiled target.

```bash
bash run/compile_model_gmts.sh \
  --run-root GTEx/outputs/archive \
  --model-id M1 \
  --output GTEx/outputs/compiled/M1.genesets.gmt
```

When child GMTs occur below an `extractor/` or `tissue_extractor/` directory,
the compiler excludes that directory's aggregate `genesets.gmt` to prevent
double-counting. It preserves source-path order and GMT record order.

Duplicate gene-set names fail by default. Use `--duplicate-policy prefix_source`
only when distinct source-specific names are intended; that mode prefixes the
duplicate's source-relative path. A gzipped manifest and a `.log` companion are
written next to the compiled GMT.
