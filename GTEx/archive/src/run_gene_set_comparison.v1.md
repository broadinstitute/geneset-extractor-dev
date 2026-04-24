# run_gene_set_comparison v1

Compares the gene content of all gene-set names shared across the three GTEx GMT libraries.

Workflow:

1. Load the three GMT files.
2. Identify the gene-set names common to all three.
3. Compute per-set pairwise and three-way overlap statistics.
4. Write summary TSV tables.
5. Generate readable PDF/PNG plots with companion markdown notes.
6. Write a short narrative findings summary to a text file.
