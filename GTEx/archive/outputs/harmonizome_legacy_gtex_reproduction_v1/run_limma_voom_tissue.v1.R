args <- commandArgs(trailingOnly=TRUE)
if (length(args) != 5) {
  stop("expected args: matrix_tsv metadata_tsv comparisons_tsv out_dir tissue_name")
}

suppressPackageStartupMessages(library(edgeR))
suppressPackageStartupMessages(library(limma))

matrix_tsv <- args[[1]]
metadata_tsv <- args[[2]]
comparisons_tsv <- args[[3]]
out_dir <- args[[4]]
tissue_name <- args[[5]]

dir.create(out_dir, recursive=TRUE, showWarnings=FALSE)

expr_df <- read.table(matrix_tsv, header=TRUE, sep='\t', quote='', comment.char='', check.names=FALSE)
metadata_df <- read.table(metadata_tsv, header=TRUE, sep='\t', quote='', comment.char='', check.names=FALSE)
comparisons_df <- read.table(comparisons_tsv, header=TRUE, sep='\t', quote='', comment.char='', check.names=FALSE)

sample_ids <- colnames(expr_df)[-1]
counts <- as.matrix(expr_df[, -1, drop=FALSE])
gene_symbols <- as.character(expr_df$gene_symbol)
row_ids <- make.unique(gene_symbols, sep="__dup")
rownames(counts) <- row_ids
gene_symbol_by_row <- setNames(gene_symbols, row_ids)
storage.mode(counts) <- 'numeric'

dge <- DGEList(counts=counts)
keep <- filterByExpr(dge)
dge <- dge[keep, , keep.lib.sizes=FALSE]
dge <- calcNormFactors(dge)
filtered_counts <- dge$counts

for (i in seq_len(nrow(comparisons_df))) {
  comparison_id <- as.character(comparisons_df$comparison_id[i])
  group_a_ids <- unlist(strsplit(as.character(comparisons_df$group_a_sample_ids[i]), "\\|", fixed=FALSE))
  group_b_ids <- unlist(strsplit(as.character(comparisons_df$group_b_sample_ids[i]), "\\|", fixed=FALSE))
  selected_ids <- c(group_b_ids, group_a_ids)
  selected_ids <- selected_ids[selected_ids %in% colnames(filtered_counts)]
  if (length(selected_ids) < 6) {
    next
  }
  counts_sub <- filtered_counts[, selected_ids, drop=FALSE]
  group <- factor(c(rep("control", length(group_b_ids)), rep("case", length(group_a_ids))), levels=c("control", "case"))
  design <- model.matrix(~ group)
  v <- voom(counts_sub, design, plot=FALSE)
  fit <- lmFit(v, design)
  fit <- eBayes(fit)
  tt <- topTable(fit, coef="groupcase", number=Inf, sort.by="none")
  tt$gene_symbol <- unname(gene_symbol_by_row[rownames(tt)])
  missing_symbols <- is.na(tt$gene_symbol) | tt$gene_symbol == ""
  if (any(missing_symbols)) {
    tt$gene_symbol[missing_symbols] <- rownames(tt)[missing_symbols]
  }
  tt$comparison_id <- comparison_id
  tt$group_a <- as.character(comparisons_df$group_a[i])
  tt$group_b <- as.character(comparisons_df$group_b[i])
  tt$n_group_a <- length(group_a_ids)
  tt$n_group_b <- length(group_b_ids)
  tt <- tt[, c("comparison_id", "gene_symbol", "logFC", "AveExpr", "t", "P.Value", "adj.P.Val", "B", "group_a", "group_b", "n_group_a", "n_group_b")]
  out_path <- file.path(out_dir, paste0(comparison_id, ".v1.tsv"))
  write.table(tt, file=out_path, sep='\t', row.names=FALSE, quote=FALSE)
}
