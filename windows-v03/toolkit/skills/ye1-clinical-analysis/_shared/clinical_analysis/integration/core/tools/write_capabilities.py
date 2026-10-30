"""Current candidate metadata entry."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).with_name('write_capabilities_v04.py')),run_name='__main__')
