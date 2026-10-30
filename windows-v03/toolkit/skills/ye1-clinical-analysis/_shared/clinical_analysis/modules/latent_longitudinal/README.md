> Current completion status: all five method IDs are implemented and verified within their explicit model bounds. Use `dispatch_api.py` for integration. See [HANDOFF.md](HANDOFF.md) and [FORMAL-IMPLEMENTATION.md](FORMAL-IMPLEMENTATION.md). Earlier reserved-formal statements below describe the prior checkpoint and are superseded.

# latent_longitudinal — isolated development module

Status: development; synthetic engineering validation only; scientific review pending.

This directory is the only write target assigned by the 2026-10-24 delegation. The
older DISPATCH split clustering / longitudinal-growth / latent-trajectories-profiles
into separate paused tasks; that discrepancy was reported before implementation.
The later explicit resume and this directory assignment govern this work.

Current supported scope, evidence and pending dependencies are in `HANDOFF.md`.
The frozen v0.10 source, installed R/Python libraries, other modules, and shared
registries/schemas are read-only. No installer, database copy, or publish action is
part of this module.

Entry points: `module.py` (local JSON CLI / Python API),
`latent_longitudinal_adapter.R` (thin R transport), `contracts.py` (closed local
request validation and canonical mapping). Nothing registers itself on import.

Formal LPA and latent trajectory methods have explicit unavailable paths until
dedicated providers and independent validation exist. Exploratory GMM and ordinary
mixed growth must never be relabelled as these methods.
