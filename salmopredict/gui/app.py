"""salmopredict Streamlit GUI.

Launch with ``salmopredict gui`` (or ``streamlit run salmopredict/gui/app.py``).

The interface lets the user point at an AutoGluon model directory, upload one
feature CSV, run prediction with live progress, then view and download the
prediction table. The predictor is cached so the (slow) model load happens only
once.

Output follows the two-type contract:
  * input without a ``Sample`` column -> a single ``Incidence(%)`` column;
  * input with a ``Sample`` column     -> ``Sample`` + ``Incidence(%)``, and,
    if a metadata CSV is attached (joined on ``Sample``), its other columns too.
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from salmopredict import DESCRIPTION, __version__
from salmopredict.config import (
    DEFAULT_ENSEMBLE_MODEL,
    PREDICTION_MAX,
    PREDICTION_MIN,
    SAMPLE_COLUMN,
    PredictConfig,
    default_model_path,
)
from salmopredict.pipeline import run_pipeline

# Branding images, shipped inside the package so they show after a plain install.
_ASSETS = Path(__file__).resolve().parent / "assets"
_ICON_PATH = _ASSETS / "salmopredict_icon.png"   # salmopredict app icon (square)
_LOGO_PATH = _ASSETS / "vphs_logo.png"           # VPHS lab logo (banner)
_CFSA_PATH = _ASSETS / "cfsa_logo.png"           # CFSA collaborator logo

_STAGE_LABELS = {
    "load": "Loading model",
    "predict": "Predicting",
    "done": "Complete",
}


@st.cache_resource(show_spinner="Loading model (first time is slow)...")
def get_predictor(model_path: str):
    """Load and cache the predictor, keyed by model directory path."""
    from salmopredict.core.predict import load_predictor

    return load_predictor(model_path)


def _input_columns(uploaded):
    """Peek the header of the uploaded CSV; None if nothing chosen or unreadable."""
    if uploaded is None:
        return None
    try:
        return list(pd.read_csv(io.BytesIO(uploaded.getvalue()), nrows=0).columns)
    except Exception:
        return None


def _has_sample(columns) -> bool:
    return bool(columns) and any(
        str(c).strip().lower() == SAMPLE_COLUMN.lower() for c in columns
    )


st.set_page_config(
    page_title="salmopredict",
    page_icon=str(_ICON_PATH) if _ICON_PATH.exists() else None,
    layout="wide",
)

# Header: salmopredict app icon + title on the left; the VPHS lab logo and the
# CFSA collaborator logo top-right.
_icon_col, _title_col, _vphs_col, _cfsa_col = st.columns(
    [1, 5, 2.2, 1.5], vertical_alignment="center"
)
with _icon_col:
    if _ICON_PATH.exists():
        st.image(str(_ICON_PATH))
with _title_col:
    st.title("salmopredict")
    st.caption(
        f"Salmonella incidence prediction from virulence-factor gene features (v{__version__})"
    )
with _vphs_col:
    if _LOGO_PATH.exists():
        st.image(str(_LOGO_PATH))
with _cfsa_col:
    if _CFSA_PATH.exists():
        st.image(str(_CFSA_PATH))

st.markdown(DESCRIPTION)

# --------------------------------------------------------------------------- #
# Parameters
# --------------------------------------------------------------------------- #
_default_model = default_model_path()
with st.sidebar:
    st.header("Model")
    model_path = st.text_input(
        "AutoGluon model directory",
        value=str(_default_model) if _default_model else "",
        key="model_path",
        help="Directory produced by TabularPredictor.save (or the slim deploy clone).",
    )
    model_name = st.text_input(
        "Ensemble model", value=DEFAULT_ENSEMBLE_MODEL, key="model_name",
        help="Falls back to the model's best if this name is absent.",
    )

    st.header("Input")
    uploaded = st.file_uploader(
        "Feature CSV", type=["csv"], accept_multiple_files=False, key="input",
    )
    output_dir = st.text_input("Output folder", value="", key="output_dir")

    columns = _input_columns(uploaded)
    has_input = uploaded is not None
    input_has_sample = _has_sample(columns)
    if has_input:
        if input_has_sample:
            st.caption(f"Input has a '{SAMPLE_COLUMN}' column, so the output is "
                       f"{SAMPLE_COLUMN} plus Incidence(%).")
        elif columns is not None:
            st.caption("No 'Sample' column, so the output is Incidence(%) only "
                       "(metadata cannot be attached).")

    # Metadata attach is only available when the input carries a Sample column.
    attach_file = None
    if input_has_sample:
        st.header("Attach metadata (needs a Sample column)")
        st.caption(
            "Joined on the 'Sample' key. The metadata CSV must also have a "
            "'Sample' column; its other columns are appended to the output. "
            "Example: examples/example_meta.csv."
        )
        attach_file = st.file_uploader(
            "Metadata CSV (joined on Sample)", type=["csv"], key="attach",
        )

    run_clicked = st.button("Run prediction", type="primary", width="stretch", key="run_btn")


# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #
def _run() -> None:
    if not model_path:
        st.error("Please provide the AutoGluon model directory.")
        return
    if not has_input:
        st.error("Please upload a feature CSV.")
        return
    if not output_dir:
        st.error("Please provide an output folder.")
        return

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    bar = st.progress(0.0, text="Starting...")

    def cb(stage: str, done: int, total: int, message: str) -> None:
        label = _STAGE_LABELS.get(stage, stage)
        if total and total > 0:
            bar.progress(min(1.0, done / total), text=f"{label}: {message}")
        else:
            bar.progress(0.0, text=f"{label}: {message}")

    try:
        # The uploaded file is materialised into a throwaway temp dir (never the
        # output folder), so only pred_<stem>.csv is left behind. The temp dir is
        # removed as soon as the run finishes.
        with tempfile.TemporaryDirectory(prefix="salmopredict_") as tmp:
            tmpd = Path(tmp)
            input_path = tmpd / uploaded.name
            input_path.write_bytes(uploaded.getvalue())

            attach_path = None
            if input_has_sample and attach_file is not None:
                attach_path = tmpd / attach_file.name
                attach_path.write_bytes(attach_file.getvalue())

            config = PredictConfig(
                input_path=input_path,
                output_dir=out,
                model_path=Path(model_path),
                ensemble_model=model_name or DEFAULT_ENSEMBLE_MODEL,
                attach_metadata=attach_path,
                force=True,
            )
            predictor = get_predictor(model_path)
            with st.spinner("Running..."):
                result = run_pipeline(config, progress=cb, predictor=predictor)
    except Exception as exc:  # surface any pipeline error in the UI
        st.error(f"Run failed: {exc}")
        return

    bar.progress(1.0, text="Complete")
    st.session_state["result"] = result
    st.success(
        f"Done. {result.n_rows} rows, label={result.label}, model={result.model_used}."
    )


if run_clicked:
    _run()

# --------------------------------------------------------------------------- #
# Results
# --------------------------------------------------------------------------- #
result = st.session_state.get("result")
if result is not None:
    st.subheader(result.input_path.name)
    if result.warned:
        st.warning(
            f"{result.missing_fraction:.1%} of model features were missing and "
            f"filled with the fill value; check the input matches this model."
        )
    if result.collisions:
        st.warning(
            f"{len(result.collisions)} normalised column-name collision(s): "
            f"{', '.join(result.collisions)}"
        )
    st.dataframe(result.predictions, width="stretch", hide_index=True)
    st.download_button(
        f"Download pred_{result.input_path.stem}.csv",
        result.predictions.to_csv(index=False).encode("utf-8"),
        file_name=f"pred_{result.input_path.stem}.csv",
        mime="text/csv",
        key=f"dl_{result.input_path.stem}",
    )
    with st.expander(f"Imputed features ({len(result.imputed)}), filled with fill value"):
        st.write(", ".join(result.imputed) if result.imputed else "None")
    if result.capped or result.floored:
        st.caption(
            f"Clamped to [{PREDICTION_MIN:g}, {PREDICTION_MAX:g}]: "
            f"{result.capped} capped at {PREDICTION_MAX:g}, "
            f"{result.floored} floored at {PREDICTION_MIN:g}."
        )
    st.caption(f"Output columns: {', '.join(result.predictions.columns)}")
    st.caption(f"Written to: {result.output_path}")
