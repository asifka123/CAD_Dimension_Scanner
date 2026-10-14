"""
main.py — Entry point for DimScan.

Usage
-----
# Process all images in the 'input/' folder (default):
    python main.py

# Process a single image:
    python main.py path/to/drawing.png

# Process a whole folder:
    python main.py path/to/folder/

Jupyter
-------
Paste this file into one cell and run.
CONFIG values at the top of dimscan/config.py are always used in Jupyter.
"""

import sys
from pathlib import Path

# ── Make sure the package is importable from this directory ──────────────────
sys.path.insert(0, str(Path(__file__).parent))

from dimscan import config as cfg
from dimscan.agent import run_agent, run_folder


def _is_jupyter():
    try:
        return get_ipython().__class__.__name__ in (   # noqa: F821
            "ZMQInteractiveShell", "TerminalInteractiveShell"
        )
    except NameError:
        return False


def _main():
    """Dispatch based on CONFIG settings."""
    if cfg.INPUT_FOLDER.strip():
        run_folder(str(cfg.BASE_DIR / cfg.INPUT_FOLDER.strip()))
    elif cfg.INPUT_IMAGE.strip():
        run_agent(str(cfg.BASE_DIR / cfg.INPUT_IMAGE.strip()))
    else:
        raise ValueError(
            "Set INPUT_IMAGE or INPUT_FOLDER in dimscan/config.py before running."
        )


if _is_jupyter():
    # Jupyter passes -f kernel.json via sys.argv — always use config.py
    _main()

elif __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = Path(sys.argv[1])
        if arg.is_dir():
            run_folder(str(arg))
        else:
            run_agent(str(arg))
    else:
        _main()
