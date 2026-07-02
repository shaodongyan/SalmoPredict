# Example inputs

Three ready-to-run files that cover the two input types and the metadata attach.
Feature values are built the way the model was trained:

```
feature = gene_frequency(serotype, gene)  ×  log10(CFU dose)
```

so the same serotype at a higher CFU has larger feature values and a higher
predicted incidence. All files share the same 10 samples — two serotypes
(Enteritidis, Typhimurium) each at CFU = 500 / 1 000 / 2 000 / 10 000 / 100 000.
Gene column names keep the original biological form (`mig-5`, `spiC/ssaB`, …);
salmopredict normalises them to the model's names (`mig-5` → `mig.5`).

| File | Rows × cols | Type | Output when run |
|------|-------------|------|-----------------|
| `example_features.csv` | 10 × 123 | **Type 1** — features only, **no `Sample`** column (just the 123 genes the model uses) | `Incidence(%)` |
| `example_with_sample.csv` | 10 × 348 | **Type 2** — a `Sample` column + all 347 genes (the ~224 extra genes are ignored) | `Sample`, `Incidence(%)` |
| `example_meta.csv` | 10 × 5 | Metadata to **attach** — `Sample` + `serotype`, `dose_cfu`, `source`, `region` | joined onto a Type-2 run by the `Sample` key |

## Run them

```bash
# Type 1: features only -> a single Incidence(%) column
salmopredict run -i examples/example_features.csv -o results/

# Type 2: a Sample column -> Sample, Incidence(%)
salmopredict run -i examples/example_with_sample.csv -o results/

# Type 2 + attach: metadata joined on Sample -> Sample, Incidence(%), + meta columns
salmopredict run -i examples/example_with_sample.csv -o results/ \
  --attach examples/example_meta.csv
```

The attached run shows the dose–response, since `example_meta.csv` carries the
`dose_cfu` alongside each `Sample`:

```
Sample,Incidence(%),serotype,dose_cfu,source,region
S001,12.39,Enteritidis,500,retail chicken,North
S002,14.15,Enteritidis,1000,retail pork,East
...
S005,37.43,Enteritidis,100000,retail pork,West
```

Rules for attaching metadata:

* the **input** must have a `Sample` column (Type 2), and so must the
  **metadata** file — the two are joined on `Sample`;
* the metadata's `Sample` values should be unique (duplicates are rejected);
* every metadata column except `Sample` is appended to the output.

In the GUI (`salmopredict gui`), the **Attach metadata** box only appears once
the chosen input is detected to have a `Sample` column.

## Rebuilding these files

The values come from the per-serotype gene-frequency table used to train the
model (`results/02_gene_frequencies.csv` in the assembly project) multiplied by
`log10(dose)`, reproducing `multiply_CFU_geneFreq.R`. To change the serotypes or
CFU values, edit that grid and recompute `gene_frequency × log10(CFU)` for every
gene column — do not edit a dose value alone, or the features and the dose will
disagree.
