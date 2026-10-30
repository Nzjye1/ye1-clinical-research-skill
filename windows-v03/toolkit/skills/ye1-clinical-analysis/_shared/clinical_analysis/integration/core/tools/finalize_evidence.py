"""Current candidate evidence verification entry."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).with_name('finalize_evidence_v03.py')),run_name='__main__')
