# Contracts Across the Multi-Robot Execution Stack

My notes on what robot components need to pass along with their results:

> M. A. Farukh, "Contracts Across the Multi-Robot Execution Stack: A Cross-Layer Review and Reference Framework".

## The question and approach

**Question.** A planner, predictor, and controller each work with different assumptions. When one passes a result to another, how can the receiver check that it is still valid?

**Approach.** I read work on contracts and runtime assurance and grouped it by what it protects: mission goals, component behavior, interacting dynamics, shared state, control authority, and physical execution.

**What I found and built on.**

- I grouped 36 sources into twelve kinds of approaches (Table 1).
- Five gaps kept appearing at interfaces: meaning and physical validity; timing; uncertainty and evidence; software compatibility and lifecycle; and who handles recovery (Table 2). I use public Nav2 failure reports to make the compatibility and lifecycle gap concrete.
- I propose a record of the assumptions, checks, evidence, and recovery action for each interface. A check can pass, fail, or remain unknown. For peer state, I work out how age, clock error, and estimation error affect the safety margin, including when a fresh on-board estimate beats a more accurate remote one.
- I trace a command through the stack and separate where a fault starts, where it is noticed, what it affects, and who responds (Tables 4 and 5).

## Layout

```text
contracts-across-the-stack/
├── main.tex          LaTeX entry point (article, single-column)
├── references.bib    Bibliography
├── sections/         Manuscript sections
├── tables/           Tables 1-5
└── figures/          TikZ sources for Figures 1-2
```

## Build the note

From the repository root:

```powershell
python tools/paper.py build contracts-across-the-stack
python tools/paper.py package contracts-across-the-stack
```
