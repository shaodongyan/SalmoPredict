"""Read a model directory's recorded versions and compare with the runtime.

AutoGluon serialises its version and training Python version into the model
directory (``version.txt`` and ``metadata.json``). Reading those files is far
cheaper and more robust than loading the predictor, so ``check`` and
``build-model`` use this module to warn about version mismatches before an
unpickle is attempted.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ModelInfo:
    path: Path
    exists: bool
    version_txt: Optional[str] = None       # contents of version.txt
    meta_version: Optional[str] = None      # metadata.json "version"
    py_version: Optional[str] = None        # training-time Python version
    model_best: Optional[str] = None


def installed_autogluon_version() -> Optional[str]:
    """Return the installed ``autogluon.tabular`` version, or ``None``.

    The top-level ``autogluon`` namespace package has no ``__version__``; the
    version lives on the ``autogluon.tabular`` sub-package.
    """
    try:
        import autogluon.tabular as agt

        return getattr(agt, "__version__", None)
    except Exception:
        return None


def read_model_info(model_path: Path) -> ModelInfo:
    """Read version metadata recorded inside a model directory."""
    model_path = Path(model_path)
    if not model_path.is_dir():
        return ModelInfo(path=model_path, exists=False)

    info = ModelInfo(path=model_path, exists=True)

    vtxt = model_path / "version.txt"
    if vtxt.is_file():
        info.version_txt = vtxt.read_text(encoding="utf-8").strip()

    meta = model_path / "metadata.json"
    if meta.is_file():
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        info.meta_version = data.get("version")
        info.py_version = data.get("py_version")
        info.model_best = data.get("model_best")

    return info


def runtime_py_version() -> str:
    """Return the running interpreter's ``major.minor.micro`` version."""
    v = sys.version_info
    return f"{v.major}.{v.minor}.{v.micro}"
