> Superseded provisioning checkpoint: the approved six packages are installed and both formal providers have passed native acceptance. See HANDOFF.md and FORMAL-IMPLEMENTATION.md for current supported bounds; retain the following dependency/design record as history.

# Formal latent methods: scope and explicit implementation gap

No formal LPA, LCGA, GBTM, or growth mixture has been fitted in this module.
These method IDs validate a narrow proposed definition and return an unavailable
result, an availability table and an explanation. No class count, log likelihood,
posterior, figure or frozen fitted model is fabricated. Supplying a package later
does not automatically activate a provider.

## Definitions proposed for the first formal providers

**Gaussian LPA.** An independent subject contributes a vector of continuous
indicators. Its density is a finite mixture of multivariate Gaussian densities,
with component weights summing to one. The initial scope requires diagonal
within-class covariance (conditional independence): EEI uses a common diagonal
covariance across classes; VVI allows each class its own diagonal covariance.
Class means vary. These are statistical latent classes, not proven disease types.
Full-covariance exploratory GMM in this module does not satisfy this contract.
The narrower diag exploratory GMM path is also not represented as a completed
formal provider: methods, identification, reference acceptance and downstream
assignment uncertainty remain separate responsibilities.

**Gaussian LCGA / growth mixture.** Subject likelihood, not visit likelihood, is
the independent unit. A class has a prespecified linear or quadratic mean in actual
time. LCGA fixes within-class random-effect variances at zero; growth mixture
includes prespecified random intercept or random intercept/slope. These models
must distinguish residual variance, within-subject covariance and between-class
heterogeneity. There is no automatic substitution of ordinary lme trajectories,
KMeans on subject slopes, or a mixture of unpaired visits.

## Acceptance still required after dependency provisioning

1. Pin the provider, compiled library files, precise likelihood and covariance
   constraints. Confirm lcmm's chosen no-random-effect parameterization supports
   the intended LCGA likelihood; do not infer that from package availability.
2. Keep all transforms, imputation policy (if ever supported), candidate classes
   and initial-value selection inside development patients. Version patient/time
   keys separately from historical cross-sectional methods.
3. Use multiple independently seeded starts, report every rejection, and require
   replicated best likelihood plus provider convergence/Hessian criteria. Reject
   boundary covariance, tiny/empty components, nonfinite outputs and unstable
   parameterization. No optimizer/model fallback after failure.
4. Report log likelihood, free-parameter count, AIC/BIC, class weights, posterior
   class sizes, average posterior probabilities, normalized entropy (undefined
   for K=1), separation/local-independence diagnostics, and candidate failures.
   Information criteria and high entropy alone do not prove valid subtypes.
5. Subject-level bootstrap stability must refit the entire prespecified process
   and align class labels. Distinguish stability conditional on a selected K from
   class-count selection stability. Never call bootstrap quantiles confidence
   intervals without an applicable inference procedure.
6. Freeze preprocessing, class priors, all likelihood parameters, time units and
   class-label convention. External posterior assignment must make zero fitting
   calls; use explicit likelihood for a subject's observed times and report
   missing-data assumptions. Assignment is not validation or subtype discovery.
7. Independently verify single-class closed-form cases, multiple separated and
   overlapping classes, label permutation, random starts, degeneracy, actual
   irregular time, missing observations, repeated IDs across partitions, reloading,
   and a second source/unit mapping. Compare supported models with dedicated
   provider references and hand-computed likelihoods at frozen parameters.
8. Explicitly block naive downstream regression treating assigned classes as
   observed truth. A later uncertainty-aware three-step/joint approach requires
   its own numerical owner, assumptions and acceptance.

The implemented one-component GMM closed-form test validates only exploratory
GMM arithmetic. It is not counted toward any formal latent-method acceptance.

## Minimal new package set requested, not installed

Actual local probe: R 4.6.1; nlme 3.1.169, lme4 2.0.6, jsonlite 2.0.0, Rcpp 1.1.2,
survival 3.8.6, parallel 4.6.1, foreach 1.5.2, iterators 1.0.14,
numDeriv 2016.8.1.1 and codetools 0.2.20 load successfully.

| Missing package | Purpose | Required dependencies already present / other missing packages |
|---|---|---|
| mclust | Gaussian LPA EEI/VVI provider candidate | R stats/utils/graphics/grDevices already present |
| lcmm | Subject-level LCGA/growth-mixture provider candidate | nlme/survival/parallel/numDeriv present; four missing packages below |
| mvtnorm | lcmm multivariate Gaussian probabilities/sampling | stats/utils present |
| spacefillr | lcmm quasi-Monte Carlo sequences | Rcpp present |
| marqLevAlg (>2.0) | lcmm optimizer | foreach present; doParallel missing |
| doParallel | required runtime import for lcmm/marqLevAlg | foreach/iterators/parallel/utils present |

Thus the currently identified minimal new runtime set is **six R packages**;
tidyLPA, flexmix, lavaan and suggested vignette packages are not required by this
narrow proposed route. Package build/binary compatibility still needs validation
in a separately authorized isolated library. This is a dependency request, not an
installation instruction or claim that all formal methods become available.

Primary metadata checked 2026-10-24:
[mclust](https://cran.r-project.org/package=mclust),
[lcmm](https://cran.r-project.org/package=lcmm),
[mvtnorm](https://cran.r-project.org/package=mvtnorm),
[spacefillr](https://cran.r-project.org/package=spacefillr),
[marqLevAlg](https://cran.r-project.org/package=marqLevAlg),
[doParallel](https://cran.r-project.org/package=doParallel).
Method documentation: [lcmm authors' documentation](https://cecileproust-lima.github.io/lcmm/),
[mclust authors' documentation](https://mclust-org.github.io/mclust/).
