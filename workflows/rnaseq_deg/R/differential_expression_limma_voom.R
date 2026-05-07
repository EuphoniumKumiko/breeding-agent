#!/usr/bin/env Rscript

suppressPackageStartupMessages(library(limma))

args <- commandArgs(trailingOnly = TRUE)

usage <- function() {
  cat(
    "Usage: differential_expression_limma_voom.R",
    "--counts FILE --outdir DIR [--prefix NAME]",
    "[--contrast JM-LM] [--fdr 0.05] [--lfc 1] [--min-count 10]",
    "[--min-samples 3]\n",
    file = stderr()
  )
}

parse_args <- function(args) {
  opts <- list(
    prefix = "JM_vs_LM",
    contrast = "JM-LM",
    fdr = 0.05,
    lfc = 1,
    min_count = 10,
    min_samples = 3
  )
  if (length(args) %% 2 != 0) {
    usage()
    stop("Arguments must be provided as --key value pairs", call. = FALSE)
  }
  for (i in seq(1, length(args), by = 2)) {
    key <- sub("^--", "", args[[i]])
    value <- args[[i + 1]]
    key <- gsub("-", "_", key)
    opts[[key]] <- value
  }
  required <- c("counts", "outdir")
  missing <- required[!vapply(required, function(x) !is.null(opts[[x]]), logical(1))]
  if (length(missing) > 0) {
    usage()
    stop("Missing required arguments: ", paste(missing, collapse = ", "), call. = FALSE)
  }
  opts$fdr <- as.numeric(opts$fdr)
  opts$lfc <- as.numeric(opts$lfc)
  opts$min_count <- as.numeric(opts$min_count)
  opts$min_samples <- as.numeric(opts$min_samples)
  opts
}

infer_group <- function(sample_names) {
  base <- basename(sample_names)
  base <- sub("\\.sorted\\.bam$", "", base)
  base <- sub("\\.bam$", "", base)
  group <- rep(NA_character_, length(base))
  group[grepl("(^|_)JM(_|$)", base)] <- "JM"
  group[grepl("(^|_)LM(_|$)", base)] <- "LM"
  if (anyNA(group)) {
    bad <- paste(base[is.na(group)], collapse = ", ")
    stop("Could not infer group for sample(s): ", bad, call. = FALSE)
  }
  data.frame(sample = base, group = group, stringsAsFactors = FALSE)
}

opts <- parse_args(args)
dir.create(opts$outdir, recursive = TRUE, showWarnings = FALSE)

fc <- read.delim(opts$counts, comment.char = "#", check.names = FALSE)
count_cols <- grep("\\.bam$", names(fc), value = TRUE)
if (length(count_cols) == 0) {
  stop("No BAM count columns were found in featureCounts output", call. = FALSE)
}

counts <- as.matrix(fc[, count_cols, drop = FALSE])
storage.mode(counts) <- "integer"
rownames(counts) <- fc$Geneid

sample_info <- infer_group(count_cols)
rownames(sample_info) <- count_cols

contrast_parts <- strsplit(opts$contrast, "-", fixed = TRUE)[[1]]
if (length(contrast_parts) != 2) {
  stop("--contrast must look like CASE-CONTROL, for example JM-LM", call. = FALSE)
}
case_group <- contrast_parts[[1]]
control_group <- contrast_parts[[2]]
group_levels <- c(control_group, case_group)
if (!all(group_levels %in% sample_info$group)) {
  stop("Contrast groups are not both present in inferred sample groups", call. = FALSE)
}

keep <- rowSums(counts >= opts$min_count) >= opts$min_samples & rowSums(counts) >= opts$min_count * 2
if (sum(keep) < 2) {
  stop("Too few genes remain after expression filtering", call. = FALSE)
}

group <- factor(sample_info$group, levels = group_levels)
design <- model.matrix(~0 + group)
colnames(design) <- group_levels

filtered_counts <- counts[keep, , drop = FALSE]
v <- voom(
  filtered_counts,
  design = design,
  lib.size = colSums(counts),
  normalize.method = "none",
  plot = FALSE
)
contrast_name <- paste(case_group, "vs", control_group, sep = "_")
contrast_matrix <- makeContrasts(contrasts = paste(case_group, "-", control_group), levels = design)
fit <- lmFit(v, design)
fit2 <- eBayes(contrasts.fit(fit, contrast_matrix))

de <- topTable(fit2, coef = 1, number = Inf, sort.by = "P")
de$Geneid <- rownames(de)
case_cols <- sample_info$group == case_group
control_cols <- sample_info$group == control_group
de[[paste0("mean_count_", case_group)]] <- rowMeans(counts[de$Geneid, case_cols, drop = FALSE])
de[[paste0("mean_count_", control_group)]] <- rowMeans(counts[de$Geneid, control_cols, drop = FALSE])
de$significant <- de$adj.P.Val <= opts$fdr & abs(de$logFC) >= opts$lfc
de <- de[, c(
  "Geneid", "logFC", "AveExpr", "t", "P.Value", "adj.P.Val", "B",
  paste0("mean_count_", case_group),
  paste0("mean_count_", control_group),
  "significant"
)]

all_out <- file.path(opts$outdir, paste0(opts$prefix, ".all_genes.tsv"))
sig_out <- file.path(opts$outdir, paste0(opts$prefix, ".significant_genes.tsv"))
sample_out <- file.path(opts$outdir, paste0(opts$prefix, ".sample_info.tsv"))
summary_out <- file.path(opts$outdir, paste0(opts$prefix, ".summary.txt"))

write.table(de, all_out, sep = "\t", quote = FALSE, row.names = FALSE)
write.table(de[de$significant, , drop = FALSE], sig_out, sep = "\t", quote = FALSE, row.names = FALSE)
write.table(sample_info, sample_out, sep = "\t", quote = FALSE, row.names = FALSE)

sink(summary_out)
cat("count_file\t", opts$counts, "\n", sep = "")
cat("contrast\t", contrast_name, "\n", sep = "")
cat("fdr_cutoff\t", opts$fdr, "\n", sep = "")
cat("abs_log2fc_cutoff\t", opts$lfc, "\n", sep = "")
cat("genes_total\t", nrow(counts), "\n", sep = "")
cat("genes_after_filter\t", sum(keep), "\n", sep = "")
cat("significant_genes\t", sum(de$significant), "\n", sep = "")
cat("libraries\n")
print(data.frame(sample = sample_info$sample, group = sample_info$group, lib_size = colSums(counts)))
sink()

cat("Wrote:\n")
cat("  ", all_out, "\n", sep = "")
cat("  ", sig_out, "\n", sep = "")
cat("  ", sample_out, "\n", sep = "")
cat("  ", summary_out, "\n", sep = "")
