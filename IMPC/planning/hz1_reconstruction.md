# IMPC HZ1 provenance and validation

- Input: IMPC Data Release 18 `genotype-phenotype-assertions-ALL.csv.gz`.
- Generation: direct assertion aggregation matching Ma'ayanLab Enrichr `KOMP2.ipynb`.
- Symbol normalization: Ma'ayanLab Harmonizome `mappingFile_2017.txt`, case-normalized before lookup.
- Filtering: retain at least five unique normalized genes per MP term, as documented in the Harmonizome KOMP workflow.
- Validation reference: 2022 KOMP2 GMT in `submissions/cfde_legacy/IMPC`; it is not a model input.

The historical private mouse-to-human mapping table is unavailable. HZ1 therefore uses the provided public, versioned Harmonizome symbol mapping without target-derived exceptions. Full-run comparison metrics document any resulting deviations.
