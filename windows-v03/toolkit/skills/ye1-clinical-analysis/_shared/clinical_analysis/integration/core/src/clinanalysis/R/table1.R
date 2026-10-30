format_mean_sd <- function(x) {
  observed <- x[!is.na(x)]
  if (!length(observed)) return("NA")
  sprintf("%.1f (%.1f)", mean(observed), stats::sd(observed))
}

format_median_iqr <- function(x) {
  observed <- x[!is.na(x)]
  if (!length(observed)) return("NA")
  quartiles <- stats::quantile(observed, c(0.25, 0.75), names = FALSE)
  sprintf("%.1f [%.1f, %.1f]", stats::median(observed), quartiles[[1L]], quartiles[[2L]])
}

format_n_percent <- function(n, denominator) {
  percent <- if (denominator > 0) 100 * n / denominator else NA_real_
  if (is.na(percent)) sprintf("%d (NA)", n) else sprintf("%d (%.1f%%)", n, percent)
}

continuous_smd <- function(x0, x1) {
  x0 <- x0[!is.na(x0)]
  x1 <- x1[!is.na(x1)]
  if (length(x0) < 2L || length(x1) < 2L) return(NA_real_)
  denominator <- sqrt((stats::var(x0) + stats::var(x1)) / 2)
  if (!is.finite(denominator) || denominator == 0) return(if (mean(x0) == mean(x1)) 0 else NA_real_)
  abs(mean(x1) - mean(x0)) / denominator
}

proportion_smd <- function(p0, p1) {
  if (any(is.na(c(p0, p1)))) return(NA_real_)
  denominator <- sqrt((p0 * (1 - p0) + p1 * (1 - p1)) / 2)
  if (!is.finite(denominator) || denominator == 0) return(if (p0 == p1) 0 else NA_real_)
  abs(p1 - p0) / denominator
}

maximum_pairwise_smd <- function(values, groups, group_values, variable_type, level = NULL) {
  pairs <- utils::combn(group_values, 2L, simplify = FALSE)
  smds <- vapply(pairs, function(pair) {
    left <- values[groups == pair[[1L]] & !is.na(groups)]
    right <- values[groups == pair[[2L]] & !is.na(groups)]
    if (identical(variable_type, "continuous")) {
      continuous_smd(left, right)
    } else {
      left_observed <- left[!is.na(left)]
      right_observed <- right[!is.na(right)]
      left_p <- if (length(left_observed)) mean(left_observed == level) else NA_real_
      right_p <- if (length(right_observed)) mean(right_observed == level) else NA_real_
      proportion_smd(left_p, right_p)
    }
  }, numeric(1L))
  finite <- smds[is.finite(smds)]
  if (length(finite)) max(finite) else NA_real_
}

table1_group_summary <- function(x, variable_type, summary_method, level, denominator_method) {
  observed <- x[!is.na(x)]
  if (identical(variable_type, "continuous")) {
    formatted <- if (identical(summary_method, "median_iqr")) format_median_iqr(x) else format_mean_sd(x)
    return(list(
      formatted = formatted, n = length(observed), denominator = length(x), proportion = NA_real_,
      mean = if (length(observed)) mean(observed) else NA_real_,
      sd = if (length(observed) > 1L) stats::sd(observed) else NA_real_,
      median = if (length(observed)) stats::median(observed) else NA_real_,
      q1 = if (length(observed)) unname(stats::quantile(observed, 0.25)) else NA_real_,
      q3 = if (length(observed)) unname(stats::quantile(observed, 0.75)) else NA_real_
    ))
  }
  denominator <- if (identical(denominator_method, "all")) length(x) else length(observed)
  n <- sum(observed == level)
  list(
    formatted = format_n_percent(n, denominator), n = n, denominator = denominator,
    proportion = if (denominator > 0) n / denominator else NA_real_,
    mean = NA_real_, sd = NA_real_, median = NA_real_, q1 = NA_real_, q3 = NA_real_
  )
}

table1_stat_row <- function(variable, label, type, level, group, summary, smd = NA_real_) {
  data.frame(
    variable = variable, label = label, type = type,
    level = if (is.null(level)) "" else as.character(level), group = group,
    n = summary$n, denominator = summary$denominator, proportion = summary$proportion,
    mean = summary$mean, sd = summary$sd, median = summary$median,
    q1 = summary$q1, q3 = summary$q3,
    smd = smd,
    stringsAsFactors = FALSE
  )
}

build_table1 <- function(task, data) {
  spec <- task$tfl$table1 %||% list(enabled = FALSE)
  if (!isTRUE(spec$enabled)) return(NULL)
  group_name <- spec$group
  required <- unique(c(group_name, vapply(spec$variables, `[[`, character(1), "name")))
  missing_columns <- setdiff(required, names(data))
  if (length(missing_columns)) {
    return(list(status = "BLOCKED", code = "TABLE1_MISSING_COLUMNS", missing_columns = as.list(missing_columns)))
  }

  group <- data[[group_name]]
  observed_groups <- sort(unique(group[!is.na(group)]))
  declared_exposure_levels <- unlist(
    task$analysis$exposure_levels %||% list(),
    use.names = FALSE
  )
  group_values <- if (
    identical(group_name, task$analysis$exposure) &&
    length(declared_exposure_levels)
  ) {
    declared_exposure_levels
  } else {
    observed_groups
  }
  if (length(group_values) < 2L || length(observed_groups) < 2L) {
    return(list(
      status = "BLOCKED", code = "TABLE1_REQUIRES_AT_LEAST_TWO_GROUPS",
      observed_groups = as.list(observed_groups)
    ))
  }
  group_labels <- if (identical(group_name, task$analysis$exposure)) {
    label_exposure_groups(as.character(group_values), task$analysis$exposure_group_labels %||% NULL)
  } else {
    as.character(group_values)
  }
  denominator_method <- spec$categorical_denominator %||% "nonmissing"
  include_overall <- isTRUE(spec$include_overall %||% TRUE)
  formatted_rows <- list()
  statistic_rows <- list()

  add_formatted_row <- function(label, level, values, smd) {
    row <- data.frame(Variable = label, Level = level, stringsAsFactors = FALSE, check.names = FALSE)
    if (include_overall) row[["Overall"]] <- values[[1L]]
    offset <- if (include_overall) 1L else 0L
    for (i in seq_along(group_labels)) {
      row[[group_labels[[i]]]] <- values[[offset + i]]
    }
    row[["SMD"]] <- if (is.na(smd)) "" else sprintf("%.3f", smd)
    formatted_rows[[length(formatted_rows) + 1L]] <<- row
  }

  for (variable in spec$variables) {
    name <- variable$name
    label <- variable$label %||% name
    type <- variable$type
    summary_method <- variable$summary %||% if (identical(type, "continuous")) "mean_sd" else NULL
    x <- data[[name]]
    subsets <- list(overall = !is.na(group))
    for (i in seq_along(group_values)) {
      subsets[[group_labels[[i]]]] <- group == group_values[[i]] & !is.na(group)
    }
    display_subsets <- if (include_overall) subsets else subsets[-1L]

    if (identical(type, "continuous")) {
      summaries <- lapply(display_subsets, function(index) table1_group_summary(x[index], type, summary_method, NULL, denominator_method))
      smd <- maximum_pairwise_smd(x, group, group_values, type)
      add_formatted_row(label, if (identical(summary_method, "median_iqr")) "Median [Q1, Q3]" else "Mean (SD)", lapply(summaries, `[[`, "formatted"), smd)
      all_stats <- lapply(names(subsets), function(group_label) table1_stat_row(name, label, type, NULL, group_label, table1_group_summary(x[subsets[[group_label]]], type, summary_method, NULL, denominator_method), smd))
      statistic_rows <- c(statistic_rows, all_stats)
    } else {
      levels <- unlist(variable$levels %||% list(), use.names = FALSE)
      if (!length(levels)) levels <- sort(unique(x[!is.na(x)]))
      if (identical(type, "binary") && length(levels) > 1L) levels <- utils::tail(levels, 1L)
      for (level in levels) {
        summaries <- lapply(display_subsets, function(index) table1_group_summary(x[index], type, summary_method, level, denominator_method))
        smd <- maximum_pairwise_smd(x, group, group_values, type, level)
        add_formatted_row(label, as.character(level), lapply(summaries, `[[`, "formatted"), smd)
        all_stats <- lapply(names(subsets), function(group_label) table1_stat_row(name, label, type, level, group_label, table1_group_summary(x[subsets[[group_label]]], type, summary_method, level, denominator_method), smd))
        statistic_rows <- c(statistic_rows, all_stats)
      }
    }

    missing_n <- vapply(display_subsets, function(index) sum(is.na(x[index])), integer(1))
    if (any(missing_n > 0L)) {
      missing_values <- Map(function(n, index) format_n_percent(n, sum(index)), missing_n, display_subsets)
      add_formatted_row(label, "Missing", missing_values, NA_real_)
      missing_stats <- lapply(names(subsets), function(group_label) {
        index <- subsets[[group_label]]
        n <- sum(is.na(x[index]))
        denominator <- sum(index)
        summary <- list(
          n = n, denominator = denominator,
          proportion = if (denominator > 0) n / denominator else NA_real_,
          mean = NA_real_, sd = NA_real_, median = NA_real_, q1 = NA_real_, q3 = NA_real_
        )
        table1_stat_row(name, label, type, "Missing", group_label, summary)
      })
      statistic_rows <- c(statistic_rows, missing_stats)
    }
  }

  list(
    status = "COMPLETE",
    group_variable = group_name,
    group_values = as.list(group_values),
    group_labels = as.list(group_labels),
    group_missing_n = sum(is.na(group)),
    categorical_denominator = denominator_method,
    formatted = do.call(rbind, formatted_rows),
    statistics = do.call(rbind, statistic_rows),
    smd_definition = "Absolute standardized mean difference; categorical variables are reported per displayed level."
  )
}

write_table1_artifacts <- function(table1, output_dir) {
  tables_dir <- file.path(output_dir, "tables")
  dir.create(tables_dir, recursive = TRUE, showWarnings = FALSE)
  formatted_path <- file.path(tables_dir, "table1_baseline_characteristics.csv")
  statistics_path <- file.path(tables_dir, "table1_statistics_long.csv")
  utils::write.csv(table1$formatted, formatted_path, row.names = FALSE, na = "")
  utils::write.csv(table1$statistics, statistics_path, row.names = FALSE, na = "")
  list(
    formatted_csv = normalizePath(formatted_path, mustWork = TRUE),
    statistics_csv = normalizePath(statistics_path, mustWork = TRUE),
    source = "prespecified baseline characteristics from analysis-ready data"
  )
}
