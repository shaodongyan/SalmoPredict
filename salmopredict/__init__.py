"""salmopredict: predict Salmonella Incidence from virulence-factor gene features.

Given a feature table of Salmonella virulence-factor gene presence/frequency,
salmopredict:

1. Aligns the input columns to the features expected by a pre-trained AutoGluon
   TabularPredictor (normalising R-``make.names``-style column names and filling
   genes the model expects but the input lacks with zero).
2. Runs the ``WeightedEnsemble_L2`` model to predict the ``Incidence`` target.
3. Writes one prediction file (``Incidence(%)``, plus a ``Sample`` column and any
   attached metadata when the input carries a ``Sample`` column).

The same core is shared by a command-line interface and a Streamlit GUI.
"""

__version__ = "0.1.0"

# One-paragraph summary shown in both the CLI help and the GUI, so the two
# interfaces describe the tool with identical wording.
DESCRIPTION = (
    "salmopredict predicts Salmonella incidence from virulence-factor "
    "gene-frequency features and provides both command-line and graphical "
    "interfaces. It standardizes the input feature table and outputs per-row "
    "incidence predictions. salmopredict was developed at the State Key "
    "Laboratory of Veterinary Public Health and Safety, China Agricultural "
    "University, in collaboration with the China National Center for Food Safety "
    "Risk Assessment (CFSA)."
)

__all__ = ["__version__", "DESCRIPTION"]
