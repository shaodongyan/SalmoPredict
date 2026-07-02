"""Input reading and output-table assembly.

Output contract (see :class:`~salmopredict.config.PredictConfig`):

* If the input has **no** ``Sample`` column, the output is a single
  ``Incidence(%)`` column -- features only, no metadata.
* If the input **has** a ``Sample`` column, the output is
  ``Sample`` + ``Incidence(%)``. When a metadata CSV is attached (it must also
  have a ``Sample`` column), its remaining columns are joined on ``Sample`` and
  appended: ``Sample`` + ``Incidence(%)`` + metadata columns.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from ..config import PREDICTION_COLUMN, SAMPLE_COLUMN, PredictConfig


def read_features(path: Path) -> pd.DataFrame:
    """Read a feature CSV (UTF-8, header row of feature names)."""
    return pd.read_csv(path)


def find_sample_column(df: pd.DataFrame) -> Optional[str]:
    """Return the input's ``Sample`` column name (case-insensitive), or None."""
    for col in df.columns:
        if str(col).strip().lower() == SAMPLE_COLUMN.lower():
            return col
    return None


def build_output(
    df: pd.DataFrame,
    preds: pd.Series,
    config: PredictConfig,
) -> pd.DataFrame:
    """Assemble the output table according to the two-type contract above."""
    sample_col = find_sample_column(df)

    out = pd.DataFrame(index=df.index)
    if sample_col is not None:
        out[SAMPLE_COLUMN] = df[sample_col].to_numpy()
    out[PREDICTION_COLUMN] = preds.to_numpy()

    if config.attach_metadata is not None:
        if sample_col is None:
            raise ValueError(
                "Attaching metadata requires a 'Sample' column in the input; "
                "this input has none."
            )
        meta = pd.read_csv(config.attach_metadata)
        meta_sample = find_sample_column(meta)
        if meta_sample is None:
            raise ValueError(
                "The metadata file must have a 'Sample' column to join on."
            )
        if meta[meta_sample].duplicated().any():
            raise ValueError(
                "The metadata file has duplicate 'Sample' values; cannot join "
                "unambiguously."
            )
        # Normalise both keys to SAMPLE_COLUMN, then left-join so every input row
        # is kept in order; unmatched samples get blank metadata.
        meta = meta.rename(columns={meta_sample: SAMPLE_COLUMN})
        out = out.merge(meta, on=SAMPLE_COLUMN, how="left")

    return out


def write_output(out_df: pd.DataFrame, path: Path) -> None:
    """Write the output table as UTF-8 CSV without the row index."""
    out_df.to_csv(path, index=False, encoding="utf-8")
