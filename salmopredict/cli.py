"""Command-line interface for salmopredict.

Commands:
    salmopredict run          -- predict Incidence for one or more feature CSVs
    salmopredict gui          -- launch the Streamlit graphical interface
    salmopredict check        -- verify dependencies and the model
    salmopredict build-model  -- clone a full AutoGluon model into a slim deploy copy
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from . import DESCRIPTION, __version__
from .config import (
    DEFAULT_ENSEMBLE_MODEL,
    DEFAULT_MISSING_WARN_FRACTION,
    PREDICTION_MAX,
    PREDICTION_MIN,
    PredictConfig,
    default_model_path,
)

# Colorised --help. rich-argparse handles column alignment, NO_COLOR, and
# non-TTY detection for us; if it is not installed we fall back to plain help so
# the CLI keeps working uncoloured.
try:
    from rich_argparse import RawDescriptionRichHelpFormatter as _HelpFormatter

    # A tasteful, on-theme palette (salmon headings for a Salmonella tool).
    _HelpFormatter.styles["argparse.prog"] = "bold #fa8072"
    _HelpFormatter.styles["argparse.groups"] = "bold #fa8072"
    _HelpFormatter.styles["argparse.args"] = "cyan"
    _HelpFormatter.styles["argparse.metavar"] = "dim cyan"
    _HelpFormatter.styles["argparse.help"] = "default"
except ImportError:  # pragma: no cover - color is a nice-to-have, not required
    from argparse import RawDescriptionHelpFormatter as _HelpFormatter


class _CliProgress:
    """Throttled, single-line progress reporter for the terminal."""

    def __init__(self) -> None:
        self._stage = None

    def __call__(self, stage: str, done: int, total: int, message: str) -> None:
        if stage != self._stage:
            if self._stage is not None:
                sys.stderr.write("\n")
            self._stage = stage
        if total and total > 0:
            pct = 100.0 * done / total
            sys.stderr.write(f"\r[{stage}] {done}/{total} ({pct:5.1f}%) {message:<40.40}")
        else:
            sys.stderr.write(f"\r[{stage}] {message:<60.60}")
        sys.stderr.flush()
        if stage == "done":
            sys.stderr.write("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="salmopredict",
        description=DESCRIPTION,
        formatter_class=_HelpFormatter,
    )
    parser.add_argument("-V", "--version", action="version", version=f"salmopredict {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    default_model = default_model_path()

    run = sub.add_parser("run", help="Predict Incidence for one feature CSV.",
                         formatter_class=_HelpFormatter)
    run.add_argument("-i", "--input", required=True,
                     help="One feature CSV file. If it has a 'Sample' column, the "
                          "output carries Sample + the prediction; otherwise it is "
                          "the prediction column only.")
    run.add_argument("-o", "--output", required=True,
                     help="Output directory (created if missing); the result is "
                          "written there as pred_<input-stem>.csv.")
    run.add_argument("--model", default=str(default_model) if default_model else None,
                     help="AutoGluon model directory. Defaults to $SALMOPREDICT_MODEL "
                          "or the model bundled under the package.")
    run.add_argument("--model-name", default=DEFAULT_ENSEMBLE_MODEL,
                     help=f"Ensemble sub-model to predict with "
                          f"(default {DEFAULT_ENSEMBLE_MODEL}; falls back to the "
                          f"model's best if absent).")
    run.add_argument("--missing-warn-frac", type=float, default=DEFAULT_MISSING_WARN_FRACTION,
                     help=f"Warn if more than this fraction of model features are "
                          f"missing from the input (default {DEFAULT_MISSING_WARN_FRACTION}).")
    run.add_argument("--fill-value", type=float, default=0.0,
                     help="Value for features the model expects but the input lacks "
                          "(default 0.0 = gene absent).")
    run.add_argument("--attach",
                     help="Metadata CSV joined on the 'Sample' key. Requires the "
                          "input to have a 'Sample' column; the metadata file must "
                          "have one too. Its other columns are appended to the output.")
    run.add_argument("-f", "--force", action="store_true",
                     help="Allow writing into a non-empty output directory.")

    gui = sub.add_parser("gui", help="Launch the Streamlit GUI.",
                         formatter_class=_HelpFormatter)
    gui.add_argument("--port", type=int, default=8501, help="Port (default 8501).")

    check = sub.add_parser("check", help="Check dependencies and the model.",
                           formatter_class=_HelpFormatter)
    check.add_argument("--model", default=str(default_model) if default_model else None,
                       help="Model directory to verify (default: bundled/env model).")

    build = sub.add_parser("build-model",
                           help="Clone a full AutoGluon model into a slim deploy copy.",
                           formatter_class=_HelpFormatter)
    build.add_argument("--source", required=True,
                       help="Source AutoGluon model directory (may contain a literal '*').")
    build.add_argument("-o", "--output", required=True,
                       help="Destination directory for the slim clone (must not be "
                            "inside --source).")
    build.add_argument("--model-name", default=DEFAULT_ENSEMBLE_MODEL,
                       help=f"Model to keep in the clone (default {DEFAULT_ENSEMBLE_MODEL}).")
    build.add_argument("-f", "--force", action="store_true",
                       help="Allow writing into an existing destination directory.")

    return parser


def _cmd_run(args: argparse.Namespace) -> int:
    config = PredictConfig(
        input_path=Path(args.input),
        output_dir=Path(args.output),
        model_path=Path(args.model) if args.model else None,
        ensemble_model=args.model_name,
        fill_value=args.fill_value,
        missing_warn_fraction=args.missing_warn_frac,
        attach_metadata=Path(args.attach) if args.attach else None,
        force=args.force,
    )

    # Imported here so 'check'/'gui' work even if autogluon is absent.
    from .pipeline import run_pipeline

    result = run_pipeline(config, progress=_CliProgress())

    cols = ", ".join(result.predictions.columns)
    print(f"\nDone. label={result.label}  model={result.model_used}")
    print(f"  {result.input_path.name}: {result.n_rows} rows -> {result.output_path}")
    print(f"    Sample column: {'yes' if result.has_sample else 'no'}"
          + ("  (metadata attached)" if result.attached else ""))
    print(f"    output columns: {cols}")
    n_imp = len(result.imputed)
    print(f"    imputed (filled {config.fill_value:g}): {n_imp} feature(s)"
          + (f" [{', '.join(result.imputed)}]" if 0 < n_imp <= 12 else ""))
    print(f"    missing fraction: {result.missing_fraction:.1%}")
    if result.floored or result.capped:
        print(f"    clamped to [{PREDICTION_MIN:g}, {PREDICTION_MAX:g}]: "
              f"{result.capped} capped at {PREDICTION_MAX:g}, "
              f"{result.floored} floored at {PREDICTION_MIN:g}")
    if result.collisions:
        print(f"    WARNING: {len(result.collisions)} normalised column name "
              f"collision(s): {', '.join(result.collisions)}")
    if result.warned:
        print(f"    WARNING: {result.missing_fraction:.1%} of model features were "
              f"missing and filled with {config.fill_value:g} -- check that this "
              f"is the right input for this model.")
    return 0


def _silence_streamlit_onboarding() -> None:
    """Skip Streamlit's first-run email prompt and telemetry.

    Streamlit asks for an email on first launch unless a credentials file
    exists; we create an anonymous one (empty email) so users never see that
    prompt. Nothing is sent anywhere.
    """
    creds = Path.home() / ".streamlit" / "credentials.toml"
    if not creds.exists():
        try:
            creds.parent.mkdir(parents=True, exist_ok=True)
            creds.write_text('[general]\nemail = ""\n')
        except OSError:
            pass  # non-fatal; the user can still press Enter at the prompt


def _cmd_gui(args: argparse.Namespace) -> int:
    app = Path(__file__).resolve().parent / "gui" / "app.py"
    _silence_streamlit_onboarding()
    env = os.environ.copy()
    env.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    cmd = [sys.executable, "-m", "streamlit", "run", str(app),
           "--server.port", str(args.port),
           "--browser.gatherUsageStats", "false"]
    try:
        return subprocess.call(cmd, env=env)
    except FileNotFoundError:
        print("streamlit is not installed. Install it with: pip install streamlit",
              file=sys.stderr)
        return 1


def _cmd_check(args: argparse.Namespace) -> int:
    from .core import modelinfo

    ok = True

    ag_version = modelinfo.installed_autogluon_version()
    ag_ok = ag_version == "1.1.1"
    print(f"  autogluon.tabular: {'OK ' + ag_version if ag_version else 'MISSING'}"
          + ("" if ag_ok or not ag_version else "  (WARNING: model was trained with 1.1.1)"))
    ok = ok and bool(ag_version)

    for mod in ("torch", "streamlit", "pandas"):
        try:
            m = __import__(mod)
            print(f"  {mod}: OK {getattr(m, '__version__', '')}")
        except Exception:
            print(f"  {mod}: MISSING")
            if mod != "streamlit":  # streamlit only needed for the GUI
                ok = False

    model_path = Path(args.model) if args.model else None
    if model_path is None:
        print("  model: MISSING (no --model, $SALMOPREDICT_MODEL, or bundled model)")
        ok = False
    else:
        info = modelinfo.read_model_info(model_path)
        if not info.exists:
            print(f"  model: MISSING ({model_path})")
            ok = False
        else:
            print(f"  model: OK ({model_path})")
            print(f"    version.txt: {info.version_txt}  metadata.version: {info.meta_version}"
                  f"  best: {info.model_best}")
            if ag_version and info.version_txt and info.version_txt != ag_version:
                print(f"    WARNING: model autogluon {info.version_txt} != installed "
                      f"{ag_version}; unpickling may fail.")
            rt = modelinfo.runtime_py_version()
            if info.py_version and not rt.startswith(info.py_version.rsplit(".", 1)[0]):
                print(f"    WARNING: model trained on Python {info.py_version}, "
                      f"running {rt}.")
            # Confirm the predictor actually loads.
            try:
                from .core.predict import load_predictor
                p = load_predictor(model_path)
                has_l2 = DEFAULT_ENSEMBLE_MODEL in p.model_names()
                print(f"    load: OK  label={p.label}  {DEFAULT_ENSEMBLE_MODEL}: "
                      f"{'present' if has_l2 else 'absent (will fall back to best)'}")
            except Exception as exc:
                print(f"    load: FAILED -- {exc}")
                ok = False

    return 0 if ok else 1


def _cmd_build_model(args: argparse.Namespace) -> int:
    from .core.predict import load_predictor

    source = Path(args.source)
    dest = Path(args.output)
    if dest.resolve() == source.resolve() or source.resolve() in dest.resolve().parents:
        raise ValueError("--output must not be the source directory or inside it.")

    print(f"Loading source model: {source}")
    predictor = load_predictor(source)
    if args.model_name not in predictor.model_names():
        raise ValueError(
            f"Model '{args.model_name}' not found in source. Available include: "
            f"{', '.join(predictor.model_names()[:10])} ..."
        )

    print(f"Cloning for deployment (keeping {args.model_name}) -> {dest}")
    predictor.clone_for_deployment(
        path=str(dest),
        model=args.model_name,
        dirs_exist_ok=args.force,
    )
    print(f"Done. Slim model written to: {dest}")
    print("Tip: point --model / $SALMOPREDICT_MODEL at this directory, or place it "
          "under the package 'models/' folder.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "run":
            return _cmd_run(args)
        if args.command == "gui":
            return _cmd_gui(args)
        if args.command == "check":
            return _cmd_check(args)
        if args.command == "build-model":
            return _cmd_build_model(args)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
