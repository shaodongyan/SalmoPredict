"""End-to-end salmopredict orchestration.

``run_pipeline`` wires together read -> feature alignment -> prediction ->
output assembly for one input file, and is the single entry point shared by the
CLI and the Streamlit GUI. Progress is reported through an injected callback so
the core stays interface-independent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

import pandas as pd

from .config import PREDICTION_MAX, PREDICTION_MIN, PredictConfig

# progress(stage, done, total, message); total<=0 means "indeterminate".
ProgressFn = Optional[Callable[[str, int, int, str], None]]


@dataclass
class PredictResult:
    """Result of one salmopredict run (one input file, one output file)."""

    input_path: Path
    output_path: Path
    predictions: pd.DataFrame
    label: str = ""
    model_used: str = ""
    model_path: Optional[Path] = None
    n_rows: int = 0
    imputed: List[str] = field(default_factory=list)
    extra_ignored: List[str] = field(default_factory=list)
    collisions: List[str] = field(default_factory=list)
    missing_fraction: float = 0.0
    warned: bool = False
    has_sample: bool = False
    attached: bool = False
    # How many predictions were clamped into the valid Incidence(%) range.
    floored: int = 0
    capped: int = 0


def _emit(progress: ProgressFn, stage: str, done: int, total: int, msg: str) -> None:
    if progress:
        progress(stage, done, total, msg)


def run_pipeline(
    config: PredictConfig,
    progress: ProgressFn = None,
    predictor=None,
) -> PredictResult:
    """Predict Incidence for the single input file described by ``config``.

    ``predictor`` may be supplied pre-loaded (e.g. cached by the GUI); otherwise
    it is loaded here.
    """
    # Imported here so 'check'/'gui' work even if autogluon/pandas are absent.
    from .core import align, io_tables
    from .core import predict as pm

    if config.model_path is None:
        raise ValueError(
            "No model directory available. Pass --model, set $SALMOPREDICT_MODEL, "
            "or place a model under the package 'models/' folder."
        )
    if not config.input_path.is_file():
        raise FileNotFoundError(f"Input file does not exist: {config.input_path}")

    if predictor is None:
        _emit(progress, "load", 0, 0, f"Loading model {Path(config.model_path).name}")
        predictor = pm.load_predictor(config.model_path)

    label = predictor.label
    model_used = pm.choose_model(predictor, config.ensemble_model)

    config.output_dir.mkdir(parents=True, exist_ok=True)

    _emit(progress, "predict", 0, 1, config.input_path.name)
    df = io_tables.read_features(config.input_path)
    al = align.align_features(df, predictor, fill_value=config.fill_value)
    warned = al.missing_fraction > config.missing_warn_fraction
    preds = pm.predict_incidence(predictor, al.X, model_used)
    # Incidence is a percentage: keep every prediction within [0, 100].
    preds, floored, capped = pm.clamp_predictions(preds, PREDICTION_MIN, PREDICTION_MAX)
    out_df = io_tables.build_output(df, preds, config)

    out_path = config.output_dir / f"pred_{config.input_path.stem}.csv"
    io_tables.write_output(out_df, out_path)

    _emit(progress, "done", 1, 1, "Complete")
    return PredictResult(
        input_path=config.input_path,
        output_path=out_path,
        predictions=out_df,
        label=label,
        model_used=model_used,
        model_path=Path(config.model_path),
        n_rows=al.n_rows,
        imputed=al.imputed,
        extra_ignored=al.extra_ignored,
        collisions=al.collisions,
        missing_fraction=al.missing_fraction,
        warned=warned,
        has_sample=io_tables.find_sample_column(df) is not None,
        attached=config.attach_metadata is not None,
        floored=floored,
        capped=capped,
    )
