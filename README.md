# Validity and Timing in Multi-Robot Runtime Assurance

I started by asking where a robot should run its predictions: on board, close to the controller, or on a remote machine with access to more data. That led me to two questions. What does a robot need to know before it can use a result from another component? And when does predicting a problem help more than reacting to the current safety margin? These notes explore those questions.

| Directory | Research note | Central question |
| --- | --- | --- |
| [`contracts-across-the-stack/`](contracts-across-the-stack/) | *Contracts Across the Multi-Robot Execution Stack: A Cross-Layer Review and Reference Framework* | What needs to travel with a result so the next component can check whether it is still valid? |
| [`predictive-vs-reactive-rta/`](predictive-vs-reactive-rta/) | *When Does Predicting Failure Help? A Boundary Analysis of Predictive versus Reactive Runtime Assurance for Multi-Robot Coordination* | When does prediction help more than a well-tuned fixed threshold? |

Timing connects the two notes. In the first, I work out how old data, clock error, and estimation error use up the available safety margin. This gives a way to compare a fresh on-board estimate with a more accurate but older remote one. In the second, I find that observation delay uses up predictive lead one for one, and test when adapting the trigger reduces unnecessary waiting.

## Layout

```text
.
├── contracts-across-the-stack/    Note 1: review, interface gaps, and a proposed framework
├── predictive-vs-reactive-rta/    Note 2: timing analysis, simulators, tests, and results
├── tools/paper.py                 Build either note or package its arXiv source bundle
└── CITATION.cff                   Citation metadata
```

## Build

Requirements: a TeX distribution with `pdflatex`, `bibtex`, and the standard article class and IEEEtran bibliography style (MiKTeX and TeX Live include it), and Python 3.

```powershell
python tools/paper.py build contracts-across-the-stack
python tools/paper.py build predictive-vs-reactive-rta
```

## License and citation

The software in `predictive-vs-reactive-rta/code/` and `predictive-vs-reactive-rta/tests/` is released under the [MIT License](predictive-vs-reactive-rta/LICENSE). The manuscripts, their figures, and their tables are not covered by that license. Citation metadata is in [CITATION.cff](CITATION.cff).
