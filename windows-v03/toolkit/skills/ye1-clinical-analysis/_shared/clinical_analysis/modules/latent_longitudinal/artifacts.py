"""Aggregate-only local tables, static figures and explanation. No patient rows."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SOURCES = {
    "KMeans": "https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html",
    "GaussianMixture": "https://scikit-learn.org/stable/modules/generated/sklearn.mixture.GaussianMixture.html",
    "nlme::lme": "https://stat.ethz.ch/R-manual/R-devel/library/nlme/html/lme.html",
    "mclust": "https://mclust-org.github.io/mclust/",
    "lcmm": "https://cecileproust-lima.github.io/lcmm/",
}


def artifact(path, root, kind, caption, admission=None):
    if admission is not None:
        caption = f"{admission.data_origin.upper()} DATA | {admission.task_purpose} | scientific review pending | " + caption
    return {"path": path.relative_to(root).as_posix(), "kind": kind,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "caption": caption,
            "classification": "local_only_aggregate_synthetic_engineering" if admission is None else
                f"local_only_aggregate_{admission.data_origin}_{admission.task_purpose}_scientific_pending"}


def write_artifacts(root, public, admission=None):
    root = Path(root)
    tables, figures = [], []
    record = public["analysis"]
    table_names = ["selection", "initializations", "class_counts", "profiles", "stability",
                   "preprocessing", "coefficients", "trajectories", "availability"]
    for key in table_names:
        values = record.get(key, [])
        if not values:
            continue
        path = root/"tables"/(key+".csv")
        path.parent.mkdir(exist_ok=True)
        fields = list(dict.fromkeys(k for row in values for k in row))
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(values)
        tables.append(artifact(path, root, "table", ("Synthetic aggregate " if admission is None else "Aggregate ") + key.replace("_", " "), admission=admission))

    def save(fig, filename, caption):
        path = root/"figures"/(filename+".png")
        path.parent.mkdir(exist_ok=True)
        if admission is not None:
            for ax in fig.axes:
                ax.set_title(ax.get_title().removeprefix("SYNTHETIC ONLY | "))
            fig.suptitle(f"{admission.data_origin.upper()} DATA | {admission.task_purpose} | scientific review pending", fontsize=10)
            fig.tight_layout(rect=(0, 0, 1, .93))
        fig.savefig(path, dpi=140, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        figures.append(artifact(path, root, "figure", caption, admission=admission))

    if record.get("profiles"):
        profile = record["profiles"]
        features = list(dict.fromkeys(row["feature"] for row in profile))
        fig, ax = plt.subplots(figsize=(max(7, min(13, len(features)*.7)), 4.5))
        for c in sorted({row["class"] for row in profile}):
            ax.plot(features, [row["standardized_center"] for row in profile if row["class"] == c],
                    marker="o", label=f"Class {c}")
        ax.axhline(0, color="grey", lw=.7)
        ax.set(ylabel="Centre in training SD units", title="SYNTHETIC ONLY | Exploratory cluster profiles")
        ax.tick_params(axis="x", labelrotation=35)
        ax.legend(loc="best", ncol=2)
        fig.tight_layout()
        save(fig, "profiles", "Frozen training centres. No confidence intervals; labels are not clinical severity.")
    if record.get("selection"):
        valid = [r for r in record["selection"] if r["status"] == "accepted"]
        if valid:
            metric = "bic" if valid[0]["bic"] is not None else "silhouette"
            fig, ax = plt.subplots(figsize=(6.4, 4))
            ax.plot([r["k"] for r in valid], [r[metric] for r in valid], "o-")
            if record.get("selected_k"):
                ax.axvline(record["selected_k"], ls="--", color="grey", label="Selected K")
                ax.legend()
            ax.set(xlabel="Candidate K", ylabel=metric.upper(), title="SYNTHETIC ONLY | Training selection")
            ax.set_xticks([r["k"] for r in record["selection"]])
            fig.tight_layout()
            save(fig, "selection", "Training-only selection; rejected candidates are documented in the table.")
    if record.get("stability"):
        valid = [r for r in record["stability"] if r["status"] == "accepted"]
        if valid:
            fig, ax = plt.subplots(figsize=(6.4, 4))
            ax.plot([r["replicate"] for r in valid], [r["ari"] for r in valid], "o-")
            ax.set(xlabel="Bootstrap replicate", ylabel="Adjusted Rand index", ylim=(-.1, 1.05),
                   title="SYNTHETIC ONLY | Conditional partition stability")
            fig.tight_layout()
            save(fig, "stability", "Bootstrap refits include training-local transforms; selected K is held fixed. No confidence interval.")
    if record.get("coefficients"):
        rows = record["coefficients"]
        fig, ax = plt.subplots(figsize=(7, max(3.5, len(rows)*.45)))
        for i, row in enumerate(rows):
            ax.plot([row["lower"], row["upper"]], [i, i], color="#235789", lw=2)
            ax.plot(row["estimate"], i, "o", color="#235789")
        ax.set_yticks(range(len(rows)), [row["term"] for row in rows])
        ax.axvline(0, color="grey", ls="--")
        ax.set(xlabel="Coefficient and 95% pointwise t interval", title="SYNTHETIC ONLY | Ordinary mixed growth")
        fig.tight_layout()
        save(fig, "growth_coefficients", "Prespecified ML model, unadjusted fixed-effect covariance; term-specific nlme denominator df.")
    if record.get("trajectories"):
        rows = record["trajectories"]
        fig, ax = plt.subplots(figsize=(7, 4.4))
        ax.plot([r["time"] for r in rows], [r["estimate"] for r in rows], color="#235789")
        ax.fill_between([r["time"] for r in rows], [r["lower"] for r in rows],
                        [r["upper"] for r in rows], alpha=.2, color="#235789")
        spec = public["definition"]
        ax.set(xlabel="Time ("+spec["time"]["unit"]+")", ylabel=spec["outcome"]["name"]+" ("+spec["outcome"]["unit"]+")",
               title="SYNTHETIC ONLY | Population mean growth")
        fig.tight_layout()
        save(fig, "growth_mean", "Fixed mean at training covariate means. Pointwise 95% t bands use minimum fixed-term df; no individual forecast.")

    public["tables"], public["figures"] = tables, figures
    lines = ["# Local synthetic engineering result" if admission is None else
             f"# Local {admission.data_origin.upper()} DATA | {admission.task_purpose} | scientific review pending", "", f"Method: `{public['method_id']}`.",
             f"Status: **{public['status']}**; reason: `{public['reason_code']}`.", "",
             "Scientific review is pending. No patient data or clinical efficacy has been validated.",
             "All artifacts remain local; this is not an approved clinical research result.", ""]
    if public["status"] == "complete":
        if "selected_k" in record:
            lines += [f"Selected K: {record['selected_k']}. Transform, K selection and resampling use training rows only.",
                      "KMeans assigns by squared Euclidean distance. GMM assigns by maximum posterior density.",
                      "KMeans has no posterior probabilities. GMM outputs are exploratory and do not constitute formal LPA.",
                      "Candidate scores are descriptive selection criteria, not proof that latent clinical populations exist.",
                      "Stability resamples training subjects and refits preprocessing, with selected K held fixed.",
                      "External assignment freezes all parameters; it does not establish external validity.", ""]
        else:
            lines += ["Ordinary Gaussian mixed growth uses one prespecified ML model, independent residuals, and continuous numeric covariates.",
                      "Missing outcomes/covariates remove rows; patients must retain sufficient observed times.",
                      "Time is (observed time − declared origin) / declared scale. Coefficient names tt/tt2 refer to this time.",
                      "x1, x2, … follow the covariate order in the saved definition. No outcome-based degree selection occurs.",
                      "Population mean bands are pointwise fixed-effect uncertainty, conditional on the specified model.",
                      "Random effects, residual distribution, missing-at-random assumptions, and causal interpretation are not verified.",
                      "This model has no latent classes and does not implement LCGA, GBTM, or growth mixture modelling.", ""]
    else:
        lines += ["No model or fitted claim is available for this request. See diagnostics and dependency requirements.", ""]
    lines += ["Warnings:", ""] + ["- "+w for w in public.get("warnings", [])]
    lines += ["", "Artifacts:", ""] + [f"- [{a['path']}]({a['path']}): {a['caption']}" for a in tables+figures]
    lines += ["", "Method documentation:", ""] + [f"- [{k}]({v})" for k, v in SOURCES.items()]
    (root/"report.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    public["explanation"] = artifact(root/"report.md", root, "explanation", "Method scope and limitations", admission=admission)
    return public
