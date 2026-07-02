"""Model loading and prediction helpers.

AutoGluon is imported lazily inside these functions so that ``salmopredict
check`` / ``gui`` keep working even before the heavy dependency is importable.
"""

from __future__ import annotations

import logging
import warnings
from contextlib import contextmanager
from pathlib import Path
from typing import Union

import pandas as pd

# AutoGluon logs benign "Found N mismatches ..." notices from this logger when a
# model is loaded on a slightly different Python micro version / OS than it was
# trained on (e.g. Linux -> macOS).
_METADATA_LOGGER = "autogluon.common.utils.utils"


@contextmanager
def _quiet_load_warnings():
    """Silence benign UserWarnings emitted while loading/predicting.

    * fastai's ``load_learner`` "insecure pickle" notice -- AutoGluon's neural-net
      sub-model is a fastai learner loaded (at load, or lazily during predict)
      via pickle; the bundled model is trusted.
    * setuptools' ``pkg_resources is deprecated`` notice -- raised while AutoGluon
      collects package versions during load.

    Only these specific messages are hidden; every other warning is left intact.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message=r".*load_learner.*", category=UserWarning
        )
        warnings.filterwarnings(
            "ignore", message=r".*insecure pickle.*", category=UserWarning
        )
        warnings.filterwarnings(
            "ignore", message=r".*pkg_resources is deprecated.*", category=UserWarning
        )
        yield


@contextmanager
def _quiet_metadata_mismatch():
    """Hide AutoGluon's load-time Python-micro-version / OS mismatch notices.

    They are logged at WARNING level by the ``autogluon.common.utils.utils``
    logger and are harmless for inference, so we raise that one logger's
    threshold for the duration of the load and restore it afterwards.
    """
    lg = logging.getLogger(_METADATA_LOGGER)
    prev = lg.level
    lg.setLevel(logging.ERROR)
    try:
        yield
    finally:
        lg.setLevel(prev)


def load_predictor(model_path: Union[str, Path]):
    """Load an AutoGluon ``TabularPredictor`` from ``model_path``.

    The path is passed as a plain string, never through a shell, so a literal
    ``*`` in a directory name is safe.
    """
    from autogluon.tabular import TabularPredictor

    model_path = Path(model_path)
    if not model_path.is_dir():
        raise FileNotFoundError(f"Model directory does not exist: {model_path}")
    with _quiet_load_warnings(), _quiet_metadata_mismatch():
        return TabularPredictor.load(str(model_path))


def choose_model(predictor, preferred: str) -> str:
    """Return ``preferred`` if the predictor has it, else its best model."""
    names = predictor.model_names()
    return preferred if preferred in names else predictor.model_best


def predict_incidence(predictor, X: pd.DataFrame, model: str) -> pd.Series:
    """Run prediction with the chosen model, returning a pandas Series."""
    with _quiet_load_warnings():
        return predictor.predict(X, as_pandas=True, model=model)


def clamp_predictions(preds: pd.Series, low: float, high: float):
    """Clamp ``preds`` into ``[low, high]``.

    Incidence is a percentage, so predictions must stay within a valid range;
    the regression model can occasionally emit values just outside it. Returns
    ``(clamped, n_below, n_above)`` where the counts are how many values were
    raised to ``low`` and lowered to ``high`` respectively (NaNs are ignored).
    """
    n_below = int((preds < low).sum())
    n_above = int((preds > high).sum())
    return preds.clip(lower=low, upper=high), n_below, n_above
