"""Align an input feature table to an AutoGluon model's expected features.

The bundled model was trained on USA data whose column names were normalised
R-``make.names``-style (``/`` and ``-`` become ``.``), and the input feature
tables carry many extra gene columns the model does not use plus a couple of
genes the model expects but the panel lacks. This module reproduces the exact
alignment used by the original ``predict_autogluon.py``:

* normalise column names with :func:`san` (mimicking ``make.names``),
* build ``X`` column-by-column in the model's feature order,
* fill features the model expects but the input lacks with ``fill_value`` (a
  missing gene means frequency 0, i.e. a weighted feature of 0),
* ignore extra input columns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

import pandas as pd

# Non-[0-9A-Za-z_] -> '.', matching R make.names and predict_autogluon.py's san().
_SAN_RE = re.compile(r"[^0-9A-Za-z_]")


def san(name: str) -> str:
    """Normalise a column name the way R ``make.names`` does for our data."""
    return _SAN_RE.sub(".", name)


@dataclass
class AlignmentResult:
    """Outcome of aligning one input table to the model features."""

    X: pd.DataFrame              # columns == model features, in model order
    model_features: List[str]
    imputed: List[str]          # model features absent from input -> filled
    extra_ignored: List[str]    # input columns not used by any feature
    collisions: List[str] = field(default_factory=list)  # san() name clashes
    n_rows: int = 0

    @property
    def missing_fraction(self) -> float:
        if not self.model_features:
            return 0.0
        return len(self.imputed) / len(self.model_features)


def align_features(df: pd.DataFrame, predictor, *, fill_value: float = 0.0) -> AlignmentResult:
    """Build the model input ``X`` from an arbitrary feature table.

    Args:
        df: Input feature table (rows = samples, columns = gene features).
        predictor: A loaded AutoGluon ``TabularPredictor``.
        fill_value: Value for features the model expects but the input lacks.

    Returns:
        An :class:`AlignmentResult`. Exact column-name matches take precedence
        over ``san``-normalised matches; anything still unmatched is imputed.
    """
    feats = list(predictor.feature_metadata_in.get_features())
    feat_san = {san(f) for f in feats}

    exact = set(df.columns)
    san_map: dict[str, str] = {}   # normalised input name -> original input name
    collisions: List[str] = []
    for col in df.columns:
        s = san(col)
        if s in san_map and s in feat_san:
            # Two input columns normalise to the same model-relevant name.
            collisions.append(s)
        san_map[s] = col

    # Build every column first, then construct X in one shot: assigning column
    # by column into a growing DataFrame fragments it and is slow for 100+ cols.
    data: dict = {}
    imputed: List[str] = []
    used_original: set = set()
    for f in feats:
        if f in exact:
            data[f] = df[f].to_numpy()
            used_original.add(f)
        elif f in san_map:
            src = san_map[f]
            data[f] = df[src].to_numpy()
            used_original.add(src)
        else:
            data[f] = fill_value  # scalar broadcasts across the index below
            imputed.append(f)

    X = pd.DataFrame(data, index=df.index, columns=feats)

    extra_ignored = [c for c in df.columns if c not in used_original]

    return AlignmentResult(
        X=X,
        model_features=feats,
        imputed=imputed,
        extra_ignored=extra_ignored,
        collisions=sorted(set(collisions)),
        n_rows=len(df),
    )
