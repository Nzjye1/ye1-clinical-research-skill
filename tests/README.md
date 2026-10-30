# Local integration regression

Current source integration keeps the installer test below and brings the
existing final8 synthetic engineering regressions into `tests/regression/`.
`regression/PROVENANCE.json` records original paths and hashes; changes to those
drivers only relocate repository-relative test assets. No historical outputs,
installed environments or patient data are copied. The independent references
retain their stated scope (some share stats/glmnet primitives).

After installing all documented groups into a new project with this source:

```powershell
& '<Python-3.14.5/python.exe>' -I -B -X utf8 tests/run_regression.py --package '<project>/.agents/skills/ye1-clinical-analysis' --area '<new-absent-output-directory>'
```

This runs core/module forward methods, 5 tests + 4 planning operations, frozen
operations, input guards, independent numeric references, 8 aliases/11 result
views and model reload operations. Each command and stdout/stderr are retained.
Failures stop dependent batches; use a new area for a rerun and preserve the
first attempt. Fixture construction is synthetic; the fixed public PBC case
and admission suite are separate, documented in PUBLIC-FIXTURES.md.

Product declarations and manifest hashes must be consistent before installing.
This is local source regression, not archive, cold-PC, GUI or scientific approval.

## Installer recovery regression

For integrated2's optional-export/repeated-output repair, run the focused
stdlib unit regression and the fresh declared-method install regression:

```powershell
& '<Python-3.14.5/python.exe>' -I -B -X utf8 tests/test_optional_exports_and_repeat.py --workdir '<new-unit-area>' -v
& '<Python-3.14.5/python.exe>' -I -B -X utf8 tests/test_optional_method_install.py --workdir '<new-fresh-area>' --rscript '<R-4.6.1/bin/Rscript.exe>' --wheelhouse '<independent-locked-wheel-cache>'
& '<Python-3.14.5/python.exe>' -I -B -X utf8 tests/test_public_fixture_utf8.py --workdir '<new-public-generator-area>' --rscript '<R-4.6.1/bin/Rscript.exe>' --r-library '<R-4.6.1/library>'
```

The fresh install test proves base+ml has no PIL, refuses the random-forest
doctor until its declared plot group is installed by `--method`, and checks
actual RF/HGB and other affected module exports. It does not use `--all` or a
manual `--groups plot` workaround. Repeated completed/failed-snapshot paths
must return an explicit non-executed status with old files unchanged. The
generator test only covers the fixed public fixture, not ordinary PBC baseline
research, a real human confirmation chain or Codex GUI discovery.

Run from a clean checkout on Windows x64 with Python 3.14.5 and R 4.6.1
(including the recommended packages required by INSTALL.md):

```powershell
& '<Python-3.14.5/python.exe>' -I -B -X utf8 tests/test_installer_resume.py --workdir '<new-absent-directory>' --rscript '<R-4.6.1/bin/Rscript.exe>' --wheelhouse '<official-wheel-directory>'
```

Omit `--wheelhouse` to use the installer's official downloads. The original
version/hash locks apply in either mode. This is a base/KM dependency test,
not an all-groups, new-physical-PC, or clinical validation claim.

The script runs the actual setup/dependency CLIs for a fresh project, repeats
installation in that project, and recovers a separate installer-owned partial
venv created with `venv --without-pip`. It verifies both KM doctors and preserves
user-file/peer-Skill sentinels, prior logs, and the partial venv's executable,
configuration and marker. All commands, stdout/stderr, installer logs and the
final result remain in the new work directory, including on failure.

If a host blocks local child processes, retain that failed directory and follow
the host's permission workflow. Use a new work directory for a complete rerun;
do not change security settings or delete the failed environment.
