<p align="center">
  <img src="https://raw.githubusercontent.com/shaodongyan/SalmoPredict/main/salmopredict/gui/assets/salmopredict_icon.png" alt="salmopredict" width="200">
</p>

# salmopredict

AutoGluon-based **Incidence** predictor for *Salmonella* virulence-factor
gene-frequency features, with a command-line interface and a Streamlit GUI.

Given a feature table (rows = samples, columns = virulence-factor genes),
salmopredict aligns the columns to the features a pre-trained AutoGluon
`TabularPredictor` expects, runs the `WeightedEnsemble_L2` model, and writes a
single prediction file. It reproduces the alignment used by the original
`predict_autogluon.py`: column names are normalised R-`make.names`-style
(`/` and `-` become `.`), genes the model expects but the input lacks are filled
with `0` (a missing gene means frequency 0), and extra input columns are ignored.

**Input/output contract** — one input CSV in, one output CSV out. The output
columns depend on whether the input has a `Sample` column:

| Input | Output columns |
|-------|----------------|
| No `Sample` column (features only) | `Incidence(%)` |
| Has a `Sample` column | `Sample`, `Incidence(%)` |
| Has a `Sample` column **and** `--attach meta.csv` | `Sample`, `Incidence(%)`, + the metadata's other columns |

Metadata is joined on the `Sample` key (the metadata CSV must also have a
`Sample` column), so attaching metadata requires a `Sample` column in the input.

## Install

The model must be loaded with **AutoGluon 1.1.1**. Reproduce the environment
with conda (AutoGluon is installed via pip inside the env — conda-installed
AutoGluon does not resolve cleanly for this project):

```bash
conda env create -f environment.yml
conda activate salmopredict
```

Or install into an existing env that already has a working AutoGluon 1.1.1:

```bash
pip install -e .          # installs the CLI and the Streamlit GUI
```

## The model

The prediction model is **already bundled** in this repository at
`salmopredict/models/model_default` — a 30 MB deployment. salmopredict uses it
automatically, so the tool works out of the box with no extra download or build
step.

Model resolution order is `--model`, then `$SALMOPREDICT_MODEL`, then the single
directory under the package `models/` folder; with nothing specified it uses the
bundled `model_default`. Pass `--model /path/to/other` to run a different
AutoGluon model.

## Usage

Ready-to-run inputs live in [`examples/`](examples/) (see its README):
`example_features.csv` (Type 1, no `Sample`), `example_with_sample.csv`
(Type 2, with `Sample`), and `example_meta.csv` (metadata to attach). Features
are `gene_frequency × log10(CFU dose)`, matching how the model was trained. Try
one immediately:

```bash
salmopredict run -i examples/example_features.csv -o results/
```

```bash
# Features only  -> output has just Incidence(%)
salmopredict run -i features.csv -o results/ --model /path/to/model

# With a Sample column  -> output has Sample, Incidence(%)
salmopredict run -i examples/example_with_sample.csv -o results/

# Attach metadata joined on the Sample key -> Sample, Incidence(%), + meta columns
salmopredict run -i examples/example_with_sample.csv -o results/ \
  --attach examples/example_meta.csv

# Launch the GUI, or check the environment/model
salmopredict gui
salmopredict check --model /path/to/model
```

Each run writes one `pred_<input-stem>.csv` to the output directory; the
prediction column is `Incidence(%)`. Features filled with `0` (genes the model
expects but the input lacks) are always reported, and a prominent warning
appears when more than `--missing-warn-frac` (default 0.3) of the model's
features are missing.

## License

Licensed under the [Apache License, Version 2.0](LICENSE). Developed at the State
Key Laboratory of Veterinary Public Health and Safety, China Agricultural
University, in collaboration with the China National Center for Food Safety Risk
Assessment (CFSA).

<p align="center">
  <img src="https://raw.githubusercontent.com/shaodongyan/SalmoPredict/main/salmopredict/gui/assets/vphs_logo.png" alt="State Key Laboratory of Veterinary Public Health and Safety" width="360">
</p>
