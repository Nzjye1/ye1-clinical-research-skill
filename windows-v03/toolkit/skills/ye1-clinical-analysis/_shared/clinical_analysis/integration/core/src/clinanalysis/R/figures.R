utils::globalVariables(c("estimate", "numeric_label", "text_x", "model_display"))

publication_palette <- c("#0072B2", "#D55E00", "#009E73", "#CC79A7")

journal_max_width <- function(target_journal) {
  profiles <- c(
    generic = 7.00, ajr = 6.83, radiology = 6.83,
    radiology_ai = 6.83, european_radiology = 6.85, kjr = 6.89
  )
  key <- tolower(gsub("[^a-z0-9]+", "_", target_journal))
  unname(profiles[[key]] %||% profiles[["generic"]])
}

tiff_lzw_device <- function(filename, width, height, units = "in", res = 300, bg = "white", ...) {
  ragg::agg_tiff(
    filename = filename, width = width, height = height, units = units,
    res = res, background = bg, compression = "lzw"
  )
}

publication_theme <- function(base_size = 10) {
  ggplot2::theme_classic(base_size = base_size) +
    ggplot2::theme(
      plot.title.position = "plot",
      plot.title = ggplot2::element_text(face = "bold", size = ggplot2::rel(1.05)),
      axis.title = ggplot2::element_text(color = "black"),
      axis.text = ggplot2::element_text(color = "black"),
      axis.line = ggplot2::element_line(linewidth = 0.35, color = "black"),
      axis.ticks = ggplot2::element_line(linewidth = 0.35, color = "black"),
      strip.background = ggplot2::element_blank(),
      strip.text = ggplot2::element_text(face = "bold"),
      panel.spacing = grid::unit(1.1, "lines"),
      legend.position = "bottom",
      legend.box = "horizontal",
      legend.key.width = grid::unit(1.7, "lines"),
      plot.margin = ggplot2::margin(6, 8, 6, 6)
    )
}

figure_output_spec <- function(task) {
  outputs <- task$outputs %||% list()
  formats <- unique(tolower(unlist(outputs$figure_formats %||% list("png", "pdf", "svg", "tiff"), use.names = FALSE)))
  supported <- c("png", "pdf", "svg", "tiff")
  unknown <- setdiff(formats, supported)
  if (length(unknown)) stop(sprintf("Unsupported figure format(s): %s", paste(unknown, collapse = ", ")), call. = FALSE)
  list(
    formats = formats,
    dpi = as.integer(outputs$figure_dpi %||% 600L),
    target_journal = outputs$target_journal %||% "generic",
    width_in = outputs$figure_width_in %||% NULL
  )
}

save_publication_figure <- function(plot, output_dir, stem, task, width, height) {
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
  spec <- figure_output_spec(task)
  requested_width <- width
  maximum_width <- journal_max_width(spec$target_journal)
  if (!is.null(spec$width_in) && spec$width_in > maximum_width) {
    stop(sprintf("Configured figure width %.2f in exceeds the %.2f in maximum for %s.", spec$width_in, maximum_width, spec$target_journal), call. = FALSE)
  }
  width <- spec$width_in %||% min(width, maximum_width)
  height <- height * width / requested_width
  device_dpi <- if (spec$dpi >= 600L) spec$dpi + 1L else spec$dpi
  paths <- list()
  tiff_compression <- "not_applicable"
  for (format in spec$formats) {
    path <- file.path(output_dir, paste0(stem, ".", format))
    device <- switch(
      format,
      pdf = grDevices::cairo_pdf,
      svg = grDevices::svg,
      png = "png",
      tiff = tiff_lzw_device
    )
    save_args <- list(
      filename = path, plot = plot, width = width, height = height,
      units = "in", dpi = device_dpi, bg = "white", device = device
    )
    do.call(ggplot2::ggsave, save_args)
    if (identical(format, "tiff")) tiff_compression <- "LZW"
    paths[[format]] <- normalizePath(path, mustWork = TRUE)
  }
  list(
    path = unname(paths$png %||% paths[[1L]]),
    formats = paths,
    dpi = device_dpi,
    requested_minimum_dpi = spec$dpi,
    width_in = width,
    height_in = height,
    journal_max_width_in = maximum_width,
    target_journal = spec$target_journal,
    tiff_compression = tiff_compression
  )
}

label_exposure_groups <- function(groups, labels = NULL) {
  groups <- as.character(groups)
  if (is.null(labels) || !length(labels)) return(sub("^[^=]+=", "", groups))
  values <- sub("^[^=]+=", "", groups)
  mapped <- vapply(values, function(value) {
    label <- labels[[value]] %||% NULL
    if (is.null(label)) value else as.character(label)
  }, character(1))
  unname(mapped)
}
