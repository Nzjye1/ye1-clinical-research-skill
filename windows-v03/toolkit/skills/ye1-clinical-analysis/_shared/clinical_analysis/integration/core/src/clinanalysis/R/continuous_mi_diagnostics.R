# Rank-normalized split and folded R-hat, following Vehtari et al. (2021).
# This is a local base-R implementation, not mice::convergence or posterior.
# A row is an iteration and a column is an imputation chain.
continuous_rank_normalize <- function(x) {
  n <- length(x)
  z <- stats::qnorm((rank(as.vector(x), ties.method = "average") - 3/8) / (n + 1/4))
  matrix(z, nrow = nrow(x), ncol = ncol(x))
}

continuous_split_rhat <- function(x) {
  if (!is.matrix(x) || nrow(x) < 4L || ncol(x) < 2L || any(!is.finite(x)) ||
      any(apply(x, 2L, function(z) length(unique(z)) < 2L))) return(NA_real_)
  half <- floor(nrow(x) / 2L)
  first <- x[seq_len(half), , drop = FALSE]
  last <- x[seq.int(nrow(x) - half + 1L, nrow(x)), , drop = FALSE]
  split <- cbind(first, last)
  basic <- function(draws) {
    within <- mean(apply(draws, 2L, stats::var))
    between <- nrow(draws) * stats::var(colMeans(draws))
    if (!is.finite(within) || within <= 0 || !is.finite(between)) return(NA_real_)
    sqrt(((nrow(draws) - 1) / nrow(draws) * within + between / nrow(draws)) / within)
  }
  ranked <- basic(continuous_rank_normalize(split))
  folded <- basic(continuous_rank_normalize(abs(split - stats::median(split))))
  if (any(!is.finite(c(ranked, folded)))) return(NA_real_)
  max(ranked, folded)
}

continuous_chain_diagnostics <- function(mids, targets, sd_not_applicable = character(), threshold = 1.1) {
  summarize <- function(parameter) {
    source <- if (identical(parameter, "mean")) mids$chainMean else sqrt(mids$chainVar)
    lapply(targets, function(target) {
      x <- source[target, , , drop = TRUE]
      if (!is.matrix(x)) x <- matrix(x, ncol = mids$m)
      rhat <- vapply(seq_len(nrow(x)), function(i) continuous_split_rhat(x[seq_len(i), , drop = FALSE]), numeric(1))
      lag1 <- vapply(seq_len(nrow(x)), function(i) {
        if (i < 3L) return(NA_real_)
        values <- vapply(seq_len(ncol(x)), function(j) {
          z <- x[seq_len(i), j]
          if (any(!is.finite(z)) || stats::sd(z) == 0) return(NA_real_)
          suppressWarnings(stats::cor(z[-i], z[-1L]))
        }, numeric(1))
        if (all(is.na(values))) NA_real_ else mean(values, na.rm = TRUE)
      }, numeric(1))
      last <- utils::tail(rhat, 5L)
      list(rhat = as.list(rhat), lag1_across_chain_mean = as.list(lag1),
           chain_values = lapply(seq_len(ncol(x)), function(j) as.list(x[, j])),
           stable = length(last) == 5L && all(is.finite(last) & last <= threshold))
    })
  }
  means <- summarize("mean"); sds <- summarize("sd")
  names(means) <- names(sds) <- targets
  for (target in sd_not_applicable) {
    sds[[target]] <- list(status = "STRUCTURALLY_UNDEFINED_N1", stable = TRUE)
  }
  list(mean = means, sd = sds,
       stable = all(vapply(means, `[[`, logical(1), "stable")) &&
         all(vapply(sds, `[[`, logical(1), "stable")),
       definition = "Base-R rank-normalized split/folded Rhat; lag-1 is per-chain Pearson correlation, averaged over chains.")
}
