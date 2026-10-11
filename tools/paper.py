"""Build a paper or package its arXiv source bundle.

Usage (from the repository root):
    python tools/paper.py build contracts-across-the-stack
    python tools/paper.py package predictive-vs-reactive-rta
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

REPO = Path(__file__).resolve().parent.parent
DIST = REPO / "dist"
PROBLEMS = re.compile(
    r"^(! .*|LaTeX Warning: (?:Reference|Citation) .* undefined.*"
    r"|LaTeX Warning: There were undefined references.*"
    r"|LaTeX Warning: Label\(s\) may have changed.*|Overfull \\hbox.*)$",
    re.MULTILINE,
)


def run(command: list[str], cwd: Path) -> None:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, errors="replace")
    if result.returncode != 0:
        sys.stdout.write(result.stdout[-3000:])
        raise SystemExit(f"command failed in {cwd}: {' '.join(command)}")


def compile_latex(paper: Path, *, run_bibtex: bool) -> list[str]:
    pdflatex = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"]
    run(pdflatex, paper)
    if run_bibtex:
        run(["bibtex", "main"], paper)
    run(pdflatex, paper)
    run(pdflatex, paper)
    log = (paper / "main.log").read_text(encoding="latin-1")
    return PROBLEMS.findall(log)


def strip_comments(text: str) -> str:
    return re.sub(r"(?<!\\)%.*", "", text)


def source_files(paper: Path) -> list[Path]:
    """Collect main.tex, every \\input file, graphics, the bibliography, and main.bbl."""
    files: list[Path] = []
    graphic_dirs = [paper]
    pending = [paper / "main.tex"]
    while pending:
        current = pending.pop(0)
        if current in files:
            continue
        files.append(current)
        text = strip_comments(current.read_text(encoding="utf-8"))
        for directory in re.findall(r"\\graphicspath\{\{([^}]+)\}\}", text):
            graphic_dirs.append(paper / directory)
        for name in re.findall(r"\\input\{([^}]+)\}", text):
            target = paper / name
            pending.append(target if target.suffix else target.with_suffix(".tex"))
        for name in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", text):
            candidates = [d / name for d in graphic_dirs]
            candidates += [c.with_suffix(".pdf") for c in candidates if not c.suffix]
            found = next((c for c in candidates if c.is_file()), None)
            if found is None:
                raise FileNotFoundError(f"graphic not found: {name}")
            files.append(found)
        for name in re.findall(r"\\bibliography\{([^}]+)\}", text):
            files.append(paper / f"{name}.bib")
    files.append(paper / "main.bbl")
    missing = [f for f in files if not f.is_file()]
    if missing:
        raise FileNotFoundError("missing: " + ", ".join(str(f.relative_to(paper)) for f in missing))
    unique = list(dict.fromkeys(files))
    return unique[:1] + sorted(unique[1:])


def build(paper: Path) -> None:
    problems = compile_latex(paper, run_bibtex=True)
    for line in problems:
        print(f"  {line}")
    print(f"built {paper.name}/main.pdf" + (" with warnings" if problems else ""))


def package(paper: Path) -> None:
    build(paper)
    files = source_files(paper)
    DIST.mkdir(exist_ok=True)
    archive_path = DIST / f"{paper.name}-arxiv-source.zip"
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(paper).as_posix())
    with tempfile.TemporaryDirectory() as scratch:
        with ZipFile(archive_path) as archive:
            archive.extractall(scratch)
        problems = [
            line
            for line in compile_latex(Path(scratch), run_bibtex=False)
            if not line.startswith("Overfull")
        ]
        if problems:
            raise SystemExit("bundle does not compile cleanly:\n  " + "\n  ".join(problems))
    print(f"created {archive_path.relative_to(REPO)} ({len(files)} files, verified)")
    for path in files:
        print(f"  {path.relative_to(paper).as_posix()}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("build", "package"))
    parser.add_argument("paper", help="paper directory, e.g. contracts-across-the-stack")
    args = parser.parse_args()
    paper = (REPO / args.paper).resolve()
    if not (paper / "main.tex").is_file():
        raise SystemExit(f"no main.tex in {paper}")
    for tool in ("pdflatex", "bibtex"):
        if shutil.which(tool) is None:
            raise SystemExit(f"{tool} is not on PATH")
    {"build": build, "package": package}[args.command](paper)


if __name__ == "__main__":
    main()
