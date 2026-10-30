# Overall Table 1 transport. All numerical summaries belong to table1.R.
study_overall_table1 <- function(task, data) {
  spec <- task$analysis$baseline %||% list()
  if (!is.null(spec$group)) {
    return(list(status = "BLOCKED", code = "TABLE1_OVERALL_REQUIRES_NULL_GROUP"))
  }
  variables <- spec$variables %||% list()
  if (!length(variables)) {
    return(list(status = "BLOCKED", code = "TABLE1_VARIABLES_REQUIRED"))
  }
  required <- unique(vapply(variables, `[[`, character(1L), "name"))
  missing_columns <- setdiff(required, names(data))
  if (length(missing_columns)) {
    return(list(status = "BLOCKED", code = "TABLE1_MISSING_COLUMNS", missing_columns = as.list(missing_columns)))
  }
  denominator_method <- spec$categorical_denominator %||% "nonmissing"
  include_overall <- isTRUE(spec$include_overall %||% TRUE)
  formatted_rows <- list()
  statistic_rows <- list()

  add_row <- function(name, label, type, level, display_level, summary) {
    row <- data.frame(Variable = label, Level = display_level, stringsAsFactors = FALSE, check.names = FALSE)
    if (include_overall) row[["Overall"]] <- summary$formatted
    row[["SMD"]] <- ""
    formatted_rows[[length(formatted_rows) + 1L]] <<- row
    statistic_rows[[length(statistic_rows) + 1L]] <<- table1_stat_row(
      name, label, type, level, "overall", summary
    )
  }

  for (variable in variables) {
    name <- variable$name
    label <- variable$label %||% name
    type <- variable$type
    summary_method <- variable$summary %||% if (identical(type, "continuous")) "mean_sd" else NULL
    x <- data[[name]]
    if (identical(type, "continuous")) {
      summary <- table1_group_summary(x, type, summary_method, NULL, denominator_method)
      display_level <- if (identical(summary_method, "median_iqr")) "Median [Q1, Q3]" else "Mean (SD)"
      add_row(name, label, type, NULL, display_level, summary)
    } else {
      levels <- unlist(variable$levels %||% list(), use.names = FALSE)
      if (!length(levels)) levels <- sort(unique(x[!is.na(x)]))
      if (identical(type, "binary") && length(levels) > 1L) levels <- utils::tail(levels, 1L)
      for (level in levels) {
        summary <- table1_group_summary(x, type, summary_method, level, denominator_method)
        add_row(name, label, type, level, as.character(level), summary)
      }
    }
    # Missing counts always use all records, exactly as in build_table1. Passing
    # the missingness indicator to the same owner avoids a second percent rule.
    missing_summary <- table1_group_summary(is.na(x), "categorical", NULL, TRUE, "all")
    if (missing_summary$n > 0L) {
      add_row(name, label, type, "Missing", "Missing", missing_summary)
    }
  }

  formatted <- if (length(formatted_rows)) do.call(rbind, formatted_rows) else {
    empty <- data.frame(Variable = character(), Level = character(), stringsAsFactors = FALSE)
    if (include_overall) empty[["Overall"]] <- character()
    empty[["SMD"]] <- character()
    empty
  }
  statistics <- if (length(statistic_rows)) do.call(rbind, statistic_rows) else {
    empty_summary <- table1_group_summary(numeric(), "continuous", "mean_sd", NULL, denominator_method)
    table1_stat_row("", "", "continuous", NULL, "overall", empty_summary)[FALSE, , drop = FALSE]
  }
  list(
    status = "COMPLETE", group_variable = NULL, group_values = list(), group_labels = list(),
    group_missing_n = 0L, categorical_denominator = denominator_method,
    formatted = formatted, statistics = statistics,
    smd_definition = "Not applicable: overall table without a comparison group."
  )
}

# Lossless display wrapping, including long unbroken category names. This changes
# line breaks only; the formatted table and its CSV export remain untouched.
.study_table1_wrap <- function(text, width) {
  text <- as.character(text)
  widths <- rep_len(width, length(text))
  vapply(seq_along(text), function(i) {
    value <- text[[i]]
    limit <- widths[[i]]
    if (is.na(value) || !nzchar(value)) return("")
    chars <- strsplit(enc2utf8(value), "", fixed = TRUE)[[1L]]
    lines <- character()
    line <- character()
    used <- 0L
    for (ch in chars) {
      ch_width <- nchar(ch, type = "width")
      if (identical(ch, "\n") || (used + ch_width > limit && length(line))) {
        lines <- c(lines, paste0(line, collapse = ""))
        line <- character()
        used <- 0L
      }
      if (!identical(ch, "\n")) {
        line <- c(line, ch)
        used <- used + ch_width
      }
    }
    paste(c(lines, paste0(line, collapse = "")), collapse = "\n")
  }, character(1L), USE.NAMES = FALSE)
}

study_table1_figure <- function(tb, task, path, source_label) {
  if (!identical(tb$status, "COMPLETE") || !is.data.frame(tb$formatted)) {
    stop("TABLE1_FIGURE_REQUIRES_COMPLETE_TABLE1", call. = FALSE)
  }
  if (!is.character(source_label) || length(source_label) != 1L || is.na(source_label) || !nzchar(source_label)) {
    stop("TABLE1_FIGURE_SOURCE_LABEL_REQUIRED", call. = FALSE)
  }
  origin <- task$data_origin
  purpose <- task$task_purpose
  if (!is.character(origin) || length(origin) != 1L || !origin %in% c("real", "synthetic")) {
    stop("TABLE1_FIGURE_DATA_ORIGIN_REQUIRED", call. = FALSE)
  }
  if (!is.character(purpose) || length(purpose) != 1L || !purpose %in% c("engineering_test", "research_analysis")) {
    stop("TABLE1_FIGURE_TASK_PURPOSE_REQUIRED", call. = FALSE)
  }

  # Only the already calculated formatted strings are rendered. In particular,
  # this function never fits, summarizes, changes denominators or promotes review.
  total_rows <- nrow(tb$formatted)
  shown_rows <- min(total_rows, 40L)
  display <- tb$formatted[seq_len(shown_rows), , drop = FALSE]
  display[] <- lapply(display, function(x) { x <- as.character(x); x[is.na(x)] <- ""; x })
  declarations <- task$variables %||% list()
  declared_names <- vapply(declarations, function(x) x$name %||% "", character(1L))
  declared_units <- vapply(declarations, function(x) x$unit %||% "unit not declared", character(1L))
  unit_map <- list()
  if ("Variable" %in% names(display)) {
    for (i in seq_len(shown_rows)) {
      label <- display$Variable[[i]]
      candidates <- if (is.data.frame(tb$statistics)) {
        unique(as.character(tb$statistics$variable[tb$statistics$label == label]))
      } else character()
      name <- if (length(candidates) == 1L) candidates[[1L]] else label
      index <- match(name, declared_names)
      unit <- if (is.na(index)) "unit not declared" else declared_units[[index]]
      display$Variable[[i]] <- paste0(label, " [", unit, "]")
      unit_map[[name]] <- unit
    }
  }
  origin_label <- if (identical(origin, "real")) "REAL DATA" else "SYNTHETIC DATA"
  title <- paste0("Table 1. Baseline characteristics\n", origin_label, " | ", purpose, " | scientific review pending")
  source_text <- paste0("Source: ", source_label)
  row_note <- if (shown_rows < total_rows) {
    sprintf("Figure shows first %d of %d rows (%d omitted); the complete CSV retains all %d rows.",
            shown_rows, total_rows, total_rows - shown_rows, total_rows)
  } else sprintf("Figure shows all %d rows; the complete CSV retains all %d rows.", total_rows, total_rows)
  footer <- paste(
    row_note,
    paste0("Categorical denominator: ", tb$categorical_denominator, "; Missing rows use all records in each displayed column."),
    "Units follow task.variables declarations; values are displayed without recomputation.",
    sep = "\n"
  )

  col_names <- names(display)
  if (!length(col_names)) stop("TABLE1_FIGURE_HAS_NO_COLUMNS", call. = FALSE)
  col_widths <- vapply(seq_along(col_names), function(j) {
    name <- col_names[[j]]
    chars <- max(nchar(c(name, display[[j]]), type = "width"), 1L)
    bounds <- if (name == "Variable") c(2.2, 3.4) else if (name == "Level") c(1.8, 4.8) else if (name == "SMD") c(.7, 1) else c(1.8, 2.6)
    min(bounds[[2L]], max(bounds[[1L]], chars * .075 + .25))
  }, numeric(1L))
  wrap_widths <- pmax(6L, floor((col_widths - .24) / .075))
  wrapped <- lapply(seq_along(col_names), function(j) .study_table1_wrap(display[[j]], wrap_widths[[j]]))
  line_count <- function(x) lengths(strsplit(x, "\n", fixed = TRUE))
  row_lines <- if (shown_rows) vapply(seq_len(shown_rows), function(i) max(vapply(wrapped, function(x) line_count(x[[i]]), integer(1L)), 1L), integer(1L)) else integer()
  row_heights <- pmax(.34, row_lines * .18 + .14)
  width <- sum(col_widths)
  full_wrap <- max(20L, floor((width - .24) / .075))
  title <- .study_table1_wrap(title, full_wrap)
  source_text <- .study_table1_wrap(source_text, full_wrap)
  footer <- .study_table1_wrap(footer, full_wrap)
  header <- .study_table1_wrap(col_names, wrap_widths)
  heights <- c(max(.62, line_count(title) * .20 + .12), max(.34, line_count(source_text) * .16 + .12),
               max(.38, max(line_count(header)) * .18 + .14), row_heights, line_count(footer) * .16 + .2)

  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  grDevices::png(path, width = width + .6, height = sum(heights) + .6, units = "in", res = 150L, bg = "white")
  on.exit(grDevices::dev.off(), add = TRUE)
  grid::grid.newpage()
  grid::pushViewport(grid::viewport(width = grid::unit(width, "inches"), height = grid::unit(sum(heights), "inches"),
    layout = grid::grid.layout(length(heights), length(col_names), heights = grid::unit(heights, "inches"), widths = grid::unit(col_widths, "inches"))))
  draw_cell <- function(row, columns, text, fill = "white", size = 10, bold = FALSE, color = "#23343B") {
    grid::pushViewport(grid::viewport(layout.pos.row = row, layout.pos.col = columns))
    grid::grid.rect(gp = grid::gpar(fill = fill, col = "white", lwd = .8))
    gp <- grid::gpar(fontsize = size, fontface = if (bold) "bold" else "plain", col = color, lineheight = 1.12)
    grob <- grid::textGrob(text, x = grid::unit(.10, "inches"), just = "left", gp = gp)
    text_width <- grid::convertWidth(grid::grobWidth(grob), "inches", valueOnly = TRUE)
    available <- sum(col_widths[columns]) - .20
    if (is.finite(text_width) && text_width > available) grob$gp$fontsize <- size * available / text_width
    grid::grid.draw(grob)
    grid::popViewport()
  }
  draw_cell(1L, seq_along(col_names), title, size = 11, bold = TRUE)
  draw_cell(2L, seq_along(col_names), source_text, size = 9)
  for (j in seq_along(col_names)) draw_cell(3L, j, header[[j]], fill = "#176B6B", bold = TRUE, color = "white")
  for (i in seq_len(shown_rows)) {
    for (j in seq_along(col_names)) draw_cell(i + 3L, j, wrapped[[j]][[i]], fill = if (i %% 2L) "#EFF5F5" else "#FAFCFC")
  }
  draw_cell(length(heights), seq_along(col_names), footer, size = 8)
  grid::popViewport()
  invisible(list(path = normalizePath(path, winslash = "/", mustWork = TRUE), title = title,
    source_label = source_label, data_origin = origin, task_purpose = purpose, scientific_review = "pending",
    total_rows = total_rows, displayed_rows = shown_rows, omitted_rows = total_rows - shown_rows,
    truncated = shown_rows < total_rows, units = unit_map))
}
