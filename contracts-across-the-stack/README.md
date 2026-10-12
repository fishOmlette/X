# Contracts Across the Multi-Robot Execution Stack

Manuscript sources for:

> M. A. Farooq, "Contracts Across the Multi-Robot Execution Stack: A Cross-Layer Review and Reference Framework," manuscript in preparation.

**Read the paper:** [contracts-across-the-stack.pdf](contracts-across-the-stack.pdf)

## Summary

**Question.** Planners, learned predictors, middleware, and runtime safety mechanisms each guarantee something under their own assumptions. When one component's guarantee becomes another component's assumption, what must the interface carry for the consumer to decide whether the result is still valid?

**Approach.** A structured review of contract-based and runtime-assurance approaches, organized by the object each one protects: mission intent, component behavior, dynamical interaction, distributed state, runtime authority, and embodied execution.

**Contributions.**

- A cross-layer taxonomy of 36 coded sources in twelve approach classes (Table I).
- A coverage analysis that identifies five interface gaps: semantic and physical validity; temporal validity of distributed state; uncertainty, provenance, and evidence; implementation and lifecycle compatibility; and intervention and recovery authority (Table II). Public failure reports from the ROS 2 navigation stack (Nav2) illustrate the compatibility and lifecycle gap.
- An interface-contract reference framework with three-valued admission and recovery semantics. For peer state, a temporal admission margin makes event time, clock error, and estimation error necessary interface fields and quantifies when an on-board estimate is preferable to a more accurate remote one.
- A failure-attribution taxonomy and a worked command trace (Tables IV and V).

The framework organizes obligations; it is neither a contract calculus nor a validated reliability mechanism.

## Layout

```text
contracts-across-the-stack/
├── main.tex          LaTeX entry point (IEEEtran, two-column)
├── references.bib    Bibliography
├── sections/         Manuscript sections
├── tables/           Tables I-V
└── figures/          TikZ sources for Figures 1-2
```

## Build the paper

From the repository root:

```powershell
python tools/paper.py build contracts-across-the-stack     # main.pdf
python tools/paper.py package contracts-across-the-stack   # dist/contracts-across-the-stack-arxiv-source.zip
```

Or, in this directory: `pdflatex main`, `bibtex main`, `pdflatex main`, `pdflatex main`. The figures are drawn with TikZ, so no external graphics are required.
