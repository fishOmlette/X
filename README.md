# Validity and Timing in Multi-Robot Runtime Assurance

This repository contains two related research papers, with their LaTeX sources and, for the second paper, the simulators, tests, and result records behind its evidence.

The work began with on-board prediction: running inference on the robot, close to the controller that uses it, rather than only on centralized infrastructure. Deciding where a prediction should run raised two more general questions about how information moves through a multi-robot system. The first paper asks what must accompany a result across component and robot interfaces for the receiver to decide whether it is still valid. The second asks when acting on a prediction of failure, rather than reacting to the current margin, improves the outcome of the robot's decision cycle.

| Directory | Paper | Central question |
| --- | --- | --- |
| [`contracts-across-the-stack/`](contracts-across-the-stack/) | [*Contracts Across the Multi-Robot Execution Stack: A Cross-Layer Review and Reference Framework*](contracts-across-the-stack/contracts-across-the-stack.pdf) (PDF) | Which obligations are lost when one component's guarantee becomes another's assumption, and what must an interface carry to keep them checkable? |
| [`predictive-vs-reactive-rta/`](predictive-vs-reactive-rta/) | [*When Does Predicting Failure Help? A Boundary Analysis of Predictive versus Reactive Runtime Assurance for Multi-Robot Coordination*](predictive-vs-reactive-rta/predictive-vs-reactive-rta.pdf) (PDF) | When does a predictive runtime-assurance trigger outperform a tuned fixed-margin reactive trigger? |

The papers meet at timing. The first derives an admission margin in which the age of peer state, clock error, and estimation error consume a safety margin, which quantifies when on-board inference is preferable to a more accurate remote estimate. The second shows that observation age consumes the lead that prediction buys one for one. Both papers are manuscripts in preparation.

## Layout

```text
.
├── contracts-across-the-stack/    Paper 1: review, gap analysis, and interface-contract framework
├── predictive-vs-reactive-rta/    Paper 2: analysis, simulators, tests, and results
├── tools/paper.py                 Build either paper or package its arXiv source bundle
└── CITATION.cff                   Citation metadata
```

Both papers use the same IEEEtran two-column format, preamble, bibliography style, and directory structure: `main.tex`, `references.bib`, `sections/`, `tables/`, and `figures/`.

## Build

Requirements: a TeX distribution with `pdflatex`, `bibtex`, and the IEEEtran class (MiKTeX and TeX Live include it), and Python 3.

```powershell
python tools/paper.py build contracts-across-the-stack
python tools/paper.py build predictive-vs-reactive-rta
```

Each command runs `pdflatex`, `bibtex`, and two further `pdflatex` passes in the paper directory and reports undefined references or overfull lines. `python tools/paper.py package <paper>` additionally writes `dist/<paper>-arxiv-source.zip` with exactly the files the manuscript uses, including `main.bbl`, and verifies that the bundle compiles on its own. Experiment reproduction for the second paper is described in [its README](predictive-vs-reactive-rta/README.md).

## License and citation

The software in `predictive-vs-reactive-rta/code/` and `predictive-vs-reactive-rta/tests/` is released under the [MIT License](predictive-vs-reactive-rta/LICENSE). The manuscripts, their figures, and their tables are not covered by that license. Citation metadata is in [CITATION.cff](CITATION.cff).
