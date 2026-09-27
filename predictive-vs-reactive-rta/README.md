# When Does Predicting Failure Help?

This repository contains the manuscript, simulators, tests, result records, and figure pipeline for:

> Mohammed Adil Farooq, “When Does Predicting Failure Help? A Boundary Analysis of Predictive versus Reactive Runtime Assurance for Multi-Robot Coordination.”

Version 1 studies controlled two-dimensional kinematic simulations. ROS 2/Nav2 and hardware experiments are deliberately reserved for v2 and are not part of the present evidence or claims.

## What v1 shows

The paper analyzes when a projected time-to-infeasibility trigger can differ from a fixed current-margin threshold. The simulations illustrate that boundary; they do not establish real-world safety or a universal ranking.

The seed-disjoint single-margin test selected `2.5` for both the reactive pad and predictive horizon. The fixed rule recorded no collision in 6,750 held-out conflict episodes, while the predictive rule recorded two. Completion-time inference is therefore withheld; the observed times remain descriptive only.

The three-robot validation uses genuinely conflicting geometry and an explicit one-shot serialization state machine. It selected a `1.75 s` fixed pad and a `1.50 s` predictive horizon. Both policies completed all 1,620 held-out conflict episodes without a collision, headway violation, timeout, or serialization breach. Prediction finished `2.779 s` sooner on average in this fixed simulator grid, with a replicate-clustered 95% bootstrap interval of `[2.659, 2.902] s`. Exact generated values and their scope are recorded in [results/README.md](results/README.md).

## Repository layout

```text
.
├── paper.tex                  LaTeX entry point
├── sections/                  Manuscript sections
├── references/                BibTeX database
├── figures/                   Publication figures (PDF and PNG)
├── code/                      Simulators and experiment scripts
├── tests/                     Deterministic simulator checks
├── results/                   Machine-readable outputs and provenance
└── LICENSE                    MIT software license
```

Experiment definitions, outcome semantics, parameter grids, and script roles are documented in [code/README.md](code/README.md). Generated-result files are catalogued in [results/README.md](results/README.md).

## Reproduce the experiments

From the repository root on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r code\requirements.txt
.\.venv\Scripts\python -m unittest discover -s tests -v

.\.venv\Scripts\python code\single_margin_experiment.py
.\.venv\Scripts\python code\stress_tests.py
.\.venv\Scripts\python code\heldout_evaluation.py
.\.venv\Scripts\python code\coordination_experiment.py
.\.venv\Scripts\python code\generate_figures.py
```

Run `coordination_experiment.py` before figure generation because the coordination figure reads `results/coordination_validation.json`. The held-out evaluations take several minutes; runtime depends on the machine. All paths are resolved relative to the repository, not the caller’s current directory.

The recorded release environment is:

- Windows 11, build 26200;
- Python 3.13.12;
- NumPy 2.4.4 and Matplotlib 3.10.9;
- MiKTeX 26.5, pdfTeX 4.27, and BibTeX 4.2; and
- 13th Gen Intel Core i7-1360P (12 cores, 16 logical processors).

## Build the paper

With `latexmk` and its Perl dependency:

```powershell
latexmk -pdf -interaction=nonstopmode -halt-on-error paper.tex
```

The direct MiKTeX sequence is:

```powershell
pdflatex -interaction=nonstopmode -halt-on-error paper.tex
bibtex paper
pdflatex -interaction=nonstopmode -halt-on-error paper.tex
pdflatex -interaction=nonstopmode -halt-on-error paper.tex
```

## License

The software under `code/` is released under the [MIT License](LICENSE). The manuscript text and figures are not automatically covered by that software license.
