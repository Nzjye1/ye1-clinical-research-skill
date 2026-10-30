# Cox evaluation and affine explanation candidate

This module applies an existing v0.10 LASSO or elastic-net Cox wrapper. It does not expose training, refit coefficients, re-estimate the baseline, learn preprocessing, or choose a background from application data.

The private entry point is `module_api.py::analyze(request)`. Methods are:

| Method | Operations | Numerical owner |
|---|---|---|
| `evaluation.survival.cox.penalized.ipcw` | `evaluate` | v10 frozen inference, then unchanged `survival_evaluation.evaluate` |
| `interpretation.survival.cox.penalized.interventional` | `fit_explainer`, `explain` | v10 frozen preprocessing/prediction, existing generic grouping, module affine explanation/display arithmetic |

`fit_explainer` freezes a separate explanation sidecar from the immutable model and prespecified display domains; it estimates no model. `explain` applies that sidecar and also returns a numerical nomogram with score/risk reconstruction checks.

Read `METHODS.md` for scales and assumptions and `GAPS.md` for limits. `contracts/` contains the four owned closed schemas and a separate closed explainer schema. `integration-request.json` is the handoff manifest. Registration and the final public StudySpec/result contract remain owned by integration.

Inputs use a subject-wide normalized row shape: `subject_id`, nullable `group_id`, ordered feature `values`, and nullable `duration`/`event`. Variable names, types, roles, units and measurement/availability timing are explicit. Endpoints are complete and mature for evaluation; explanation refuses endpoint values. Maximum application size is 200 subjects, with at most 12 original features, 60 retained encoded columns and eight horizons, matching v10 constraints.

The model is carried as the exact UTF-8 JSON string `payload.model_json`. Original bytes are hashed before parsing; the wrapper's method, versions, runtime packages, source hashes, semantics and training identities are checked. The worker writes a private temporary copy and verifies its hash before calling the v10 owner. The returned private model string is unchanged. There is no v05/v08 model conversion.

The common envelope's five bindings keep the unique public entry point's definitions: raw task-file bytes, the full plan excluding its output directory, registered module/schema/manifest snapshot, raw core runtime-lock bytes, and raw model bytes. Common `prepare` must validate the first four against its trusted context before calling `analyze`. The module independently verifies actual model bytes and wrapper contents. Its additional `rows_sha256`, `payload_plan_sha256`, `numerical_code_sha256` and `runtime_binding_sha256` are separately named scientific provenance, never substitutes for common bindings. `make_request(..., bindings)` only constructs an envelope; it does not authenticate a context.

`module_api.py::project(response, output_dir, context)` writes a new output directory, with public aggregate JSON/CSV/PNG and a separate local `private/record.json`. It rejects existing output directories. Context has `result_id` and the common `binding` object. Projection never fits or recomputes model estimates. IPCW tables and plots reuse the core presentation helper; nomogram layout reuses the core wrapping/lane/layout helpers with Cox-specific labels.

Run local acceptance using the pinned Python executable and `tests/run_acceptance.py`. Every run gets a fresh evidence directory, and failed receipts are retained. Synthetic training setup uses only the original v10 numerical owner. Source, dependency and runtime hashes are recorded. This command is module-local acceptance, not the final integrated regression suite.
