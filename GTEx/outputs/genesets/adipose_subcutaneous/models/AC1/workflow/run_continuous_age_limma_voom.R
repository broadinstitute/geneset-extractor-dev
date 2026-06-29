suppressPackageStartupMessages({
  library(edgeR)
  library(limma)
})

counts <- read.delim("/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/prepared/tissue_counts.tsv", check.names=FALSE)
meta <- read.delim("/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models/AC1/workflow/continuous_sample_metadata.tsv", check.names=FALSE)
feature_ids <- counts[[1]]
gene_symbols <- if ("gene_symbol" %in% colnames(counts)) as.character(counts[["gene_symbol"]]) else as.character(feature_ids)
count_cols <- setdiff(colnames(counts), c(colnames(counts)[1], "gene_symbol"))
count_mat <- as.matrix(counts[, count_cols, drop=FALSE])
storage.mode(count_mat) <- "numeric"
rownames(count_mat) <- feature_ids
meta$sample_id <- as.character(meta$sample_id)
meta$SEX <- factor(as.character(meta$SEX))
meta$age_mid <- as.numeric(meta$age_mid)
count_mat <- count_mat[, meta$sample_id, drop=FALSE]
y <- DGEList(counts=count_mat)
keep_genes <- filterByExpr(y)
y <- y[keep_genes, , keep.lib.sizes=FALSE]
y <- calcNormFactors(y)
design <- model.matrix(as.formula("~ age_mid + SEX"), data=meta)
v <- voom(y, design, plot=FALSE)
fit <- lmFit(v, design)
coef_name <- "age_mid"
fit <- eBayes(fit)
tt <- topTable(fit, coef=coef_name, number=Inf, sort.by="none")
tt$comparison_id <- "continuous_age"
tt$gene_id <- rownames(tt)
tt$gene_symbol <- gene_symbols[match(rownames(tt), feature_ids)]
tt$group_a <- "older"
tt$group_b <- "younger"
tt$stratum <- ""
tt$backend <- "r_limma_voom_continuous_age"
tt$n_group_a <- nrow(meta)
tt$n_group_b <- nrow(meta)
tt$mean_expr <- tt$AveExpr
tt$model_formula <- "age_mid + SEX"
keep_cols <- c("comparison_id", "gene_id", "gene_symbol", "logFC", "t", "P.Value", "adj.P.Val", "group_a", "group_b", "stratum", "backend", "n_group_a", "n_group_b", "mean_expr", "model_formula")
tt <- tt[, keep_cols, drop=FALSE]
colnames(tt)[colnames(tt) == "t"] <- "stat"
colnames(tt)[colnames(tt) == "P.Value"] <- "pvalue"
colnames(tt)[colnames(tt) == "adj.P.Val"] <- "padj"
write.table(tt, file="/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models/AC1/tissue_extractor/tissue_deg.tsv", sep="\t", row.names=FALSE, quote=FALSE)
