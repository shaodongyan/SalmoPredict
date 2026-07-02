#!/usr/bin/env python
"""Clone a full AutoGluon model directory into a slim, inference-only copy.

This is the standalone equivalent of ``salmopredict build-model``. It keeps only
the requested ensemble model (default WeightedEnsemble_L2) and its dependencies,
turning the ~700 MB training artifact into a ~30 MB deployment model. The source
directory is never modified -- AutoGluon copies it first, then prunes the copy.

Usage:
    python build_deploy_model.py --source '<full model dir>' -o '<slim dir>'
                                 [--model-name WeightedEnsemble_L2] [-f]

The source path may contain a literal '*' (the bundled model directory does);
pass it single-quoted so the shell does not expand it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", required=True, help="Full AutoGluon model directory.")
    parser.add_argument("-o", "--output", required=True, help="Destination slim directory.")
    parser.add_argument("--model-name", default="WeightedEnsemble_L2",
                        help="Model to keep (default WeightedEnsemble_L2).")
    parser.add_argument("-f", "--force", action="store_true",
                        help="Allow writing into an existing destination.")
    args = parser.parse_args(argv)

    from autogluon.tabular import TabularPredictor

    source = Path(args.source)
    dest = Path(args.output)
    if dest.resolve() == source.resolve() or source.resolve() in dest.resolve().parents:
        print("Error: --output must not be the source directory or inside it.",
              file=sys.stderr)
        return 1

    print(f"Loading source model: {source}")
    predictor = TabularPredictor.load(str(source))
    if args.model_name not in predictor.model_names():
        print(f"Error: model '{args.model_name}' not in source.", file=sys.stderr)
        return 1

    print(f"Cloning for deployment (keeping {args.model_name}) -> {dest}")
    predictor.clone_for_deployment(path=str(dest), model=args.model_name,
                                   dirs_exist_ok=args.force)
    print(f"Done. Slim model written to: {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
