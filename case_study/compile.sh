#!/usr/bin/env bash
set -e

# Ensure TinyTeX is in PATH
export PATH="$HOME/.TinyTeX/bin/x86_64-linux:$PATH"

# Move to the case_study directory
cd "$(dirname "$0")"

echo "=== [1/4] Running first pdflatex pass ==="
pdflatex -interaction=nonstopmode main.tex > /dev/null

echo "=== [2/4] Resolving bibliography with bibtex ==="
bibtex main > /dev/null

echo "=== [3/4] Running second pdflatex pass (inserting references) ==="
pdflatex -interaction=nonstopmode main.tex > /dev/null

echo "=== [4/4] Running final pdflatex pass (cross-references & page alignment) ==="
pdflatex -interaction=nonstopmode main.tex | grep "Output written"

echo "Compilation successful! Output: case_study/main.pdf"

