"""Run configuration for salmopredict.

A single :class:`PredictConfig` object carries every parameter through the
pipeline so the CLI and the Streamlit GUI share exactly the same core.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Ensemble model used for prediction. The bundled model's overall best is
# WeightedEnsemble_L3, but the established workflow uses L2, so we default to L2
# for result parity. Falls back to predictor.model_best if L2 is absent.
DEFAULT_ENSEMBLE_MODEL = "WeightedEnsemble_L2"

# When more than this fraction of the model's features are missing from the
# input (and therefore filled with ``fill_value``), a prominent warning is
# emitted -- the prediction still runs.
DEFAULT_MISSING_WARN_FRACTION = 0.30

# Environment variable that can point at a default model directory.
MODEL_ENV_VAR = "SALMOPREDICT_MODEL"

# The one identifier column salmopredict recognises. When present in the input
# it is carried into the output and used to join any attached metadata; when
# absent the output holds the prediction column only.
SAMPLE_COLUMN = "Sample"

# Name of the single prediction column written to the output.
PREDICTION_COLUMN = "Incidence(%)"

# Incidence is a percentage, so predictions are clamped to this range. The
# regression model can occasionally output values slightly outside [0, 100],
# which are not physically meaningful; clamping keeps every output valid.
PREDICTION_MIN = 0.0
PREDICTION_MAX = 100.0

# Directory inside the package where a slimmed deployment model may be shipped.
_PKG_MODELS_DIR = Path(__file__).resolve().parent / "models"


def default_model_path() -> Optional[Path]:
    """Locate a default AutoGluon model directory.

    Resolution order:
      1. ``$SALMOPREDICT_MODEL`` if it points at an existing directory.
      2. The single sub-directory of the package ``models/`` folder, if exactly
         one exists (the slimmed model shipped via ``build-model``).
    Returns ``None`` when neither is available, in which case ``--model`` must
    be given explicitly.
    """
    env = os.environ.get(MODEL_ENV_VAR)
    if env:
        p = Path(env).expanduser()
        if p.is_dir():
            return p
    if _PKG_MODELS_DIR.is_dir():
        subdirs = [d for d in sorted(_PKG_MODELS_DIR.iterdir()) if d.is_dir()]
        if len(subdirs) == 1:
            return subdirs[0]
    return None


@dataclass
class PredictConfig:
    """All parameters for one salmopredict run.

    One input feature CSV is aligned to the model and predicted, producing one
    output file ``pred_<input-stem>.csv`` in ``output_dir``.

    Output columns depend on the input:
      * no ``Sample`` column  -> just the prediction (``Incidence(%)``);
      * a ``Sample`` column    -> ``Sample`` + ``Incidence(%)``, and, if
        ``attach_metadata`` is given, the metadata columns (joined on ``Sample``)
        are appended. Attaching metadata requires a ``Sample`` column.
    """

    input_path: Path
    output_dir: Path
    model_path: Optional[Path] = field(default_factory=default_model_path)
    ensemble_model: str = DEFAULT_ENSEMBLE_MODEL
    fill_value: float = 0.0
    missing_warn_fraction: float = DEFAULT_MISSING_WARN_FRACTION

    # Optional external metadata CSV joined on the ``Sample`` key.
    attach_metadata: Optional[Path] = None

    force: bool = False

    def __post_init__(self) -> None:
        self.input_path = Path(self.input_path)
        self.output_dir = Path(self.output_dir)
        if self.model_path is not None:
            self.model_path = Path(self.model_path)
        if self.attach_metadata is not None:
            self.attach_metadata = Path(self.attach_metadata)
        if not 0.0 <= float(self.missing_warn_fraction) <= 1.0:
            raise ValueError("missing_warn_fraction must be between 0 and 1")
        self.missing_warn_fraction = float(self.missing_warn_fraction)
        self.fill_value = float(self.fill_value)
