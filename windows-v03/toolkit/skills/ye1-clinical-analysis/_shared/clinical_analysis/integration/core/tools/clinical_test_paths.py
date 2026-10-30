"""Test/tool bootstrap; effective executable paths are local configuration."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from clinical_test_runtime import (  # noqa: E402,F401
    configure_process, configured_reference, local_root, load_runtime,
    reference_path, runtime_path,
)
