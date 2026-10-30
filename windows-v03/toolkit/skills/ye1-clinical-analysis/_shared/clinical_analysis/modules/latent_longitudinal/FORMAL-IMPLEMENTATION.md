# Dedicated Gaussian profiles and trajectories

This extension uses separate `formal_*` sources and `formal_schemas/` to keep
the accepted exploratory clustering and ordinary growth provider bytes unchanged.
`dispatch_api.py` is a thin routing adapter; shared registration and final result
identifiers remain the integration owner's responsibility.

## Model definitions

| ID | Numerical owner | Supported definition |
|---|---|---|
| latent.profile.gaussian | mclust::me via explicit EEI/VVI methods | Continuous Gaussian indicators; conditional independence; EEI shares each indicator variance across classes, VVI allows each indicator variance to vary by class |
| latent.trajectory.gaussian / LCGA | lcmm::hlme | Gaussian linear/quadratic class-specific means; no individual random effects; independent residuals |
| latent.trajectory.gaussian / growth_mixture | lcmm::hlme | Gaussian linear/quadratic class-specific means; shared random intercept or correlated intercept/slope covariance; independent residuals; intercept-only class probabilities |

These models are distinct from exploratory sklearn GMM and ordinary nlme growth.
The LPA model is itself a specifically constrained Gaussian mixture; its formal
name does not establish a clinical latent construct. No wrappers are required.

## Input and fit behavior

Use the common `clinical-module-request@1.0` envelope. Formal payload schemas
require a complete semantic declaration, `split`, and `controls`. Each field is
closed; patient IDs must be unique for profiles and (patient, actual numeric time)
must be unique for long data. A patient cannot cross train/holdout partitions.
Time units, origin and positive scale are explicit, never inferred from visit order.
The formal schema extensions are intentionally separate from the former reserved
formal payloads; callers must bind the registered new schema.

The prespecified candidate set must include K=1, with K at most 6; training needs
30–3000 subjects and at least 10 per maximum candidate K. Each retained training
trajectory needs at least degree+1 observations, at least 2, and at least 3 for a
random slope. Input is capped at 20,000 rows. These are engineering guardrails,
not power/sample-size calculations. Hard class size must be at least 5 and 5% of
training subjects; mixing proportions at least 5%. Failure is reported explicitly.

Profile complete-case selection and centering/scaling use only training subjects.
Means and scales use maximum-likelihood (denominator n) variance. Trajectories use
observed outcomes; missing outcome rows and wholly missing subjects are counted.
The observed likelihood requires MAR plus the specified measurement model; it
does not handle informative dropout. Weights, covariates, categorical indicators,
non-Gaussian outcomes and residual AR structures are not supported.

For K>1, 20–200 seeded starts are fitted; at least two accepted starts must repeat
the best likelihood within the recorded tolerance. One-class fits run once and
are explicitly counted once. LPA checks EM return status, warnings, finite density,
variance/condition and class bounds. hlme requires conv=1, all three convergence
criteria within tolerance, positive inverse-Hessian eigenvalues, positive residual
variance and nonsingular random covariance. No partial Hessian or fallback is used.
Reconstructed density and posteriors must agree with the package's fitted values.
An internal adapter exception aborts analysis rather than silently dropping a
candidate. Numerical convergence cannot prove a global maximum.

Training BIC uses independent subjects as its denominator and selects the lowest
accepted value. AIC and all rejected candidates/starts are also reported. LPA
likelihood is in training-standardized indicator coordinates; trajectory likelihood
is joint within-subject density in declared outcome units. They are not comparable
across differing variables, transformations, outcome definitions or samples.

Training-subject bootstrap refits transforms and the selected K. At least 80% of
5–30 requested replicates must pass the same guards. ARI and 10th/90th percentiles
are descriptive stability summaries, not confidence intervals. K selection is not
repeated. K=1 stability is trivial and not evidence of a latent subdivision.

## Frozen application and outputs

Train and frozen application are separate operations: train/assign for profiles,
train/predict for trajectories. Trajectory `predict` means posterior class scoring
from observed outcomes; it is not a prospective outcome predictor. External
assignment uses numeric JSON parameters, not executable pickle/RDS. Byte hash,
content checksum, provider/runtime hashes, definition, units, and cohort overlap
are checked. All development IDs, including holdout IDs, contribute salted hashes.
Hashes do not imply anonymization or encryption; the artifact remains private.

External calls make zero fitting calls, never reselect K or thresholds, and reject
time extrapolation. One external subject can be scored. Uncertain assignment is
retained as private posterior probabilities. Aggregate counts/entropy/likelihood
do not constitute external clinical validation. No causal effect or hard-class
downstream analysis is automatically performed.

The public record contains aggregate selection, start/stability tables, counts,
means/parameters and curves; patient membership and model bytes are private.
`project()` only renders validated public aggregates to CSV/PNG/Markdown. Formal
means have no fabricated confidence bands; BLRT, LMR, parameter uncertainty and
three-step downstream inference are explicitly unsupported. Scientific review
stays pending and export stays local-only with synthetic engineering scope.

## Primary documentation

- [mclust EM](https://mclust-org.github.io/mclust/reference/me.html),
  [variance parameterization](https://mclust-org.github.io/mclust/reference/mclustVariance.html).
- [lcmm hlme model, parameter ordering and convergence](https://cecileproust-lima.github.io/lcmm/reference/hlme.html),
  [posterior assignment](https://cecileproust-lima.github.io/lcmm/reference/predictClass.html).
- [Official mclust metadata](https://cran.r-project.org/package=mclust),
  [official lcmm metadata](https://cran.r-project.org/package=lcmm).

Exact installed versions, source URLs, build compatibility, byte receipts and
reused dependencies are in `evidence/formal-install/receipt.json`. Native package
source inspection used to resolve calling-scope behavior is retained there.
