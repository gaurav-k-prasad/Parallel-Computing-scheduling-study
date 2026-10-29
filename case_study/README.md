# Case Study: IEEE Paper on OpenMP Loop Scheduling

## Files

- `main.tex` — Complete IEEE-format LaTeX manuscript
- `references.bib` — BibTeX bibliography (10 verified references)
- `figures/` — Copy of project figures for inclusion (if needed)
- `main.pdf` — Compiled PDF output

## Compilation

```bash
cd case_study/
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

Or with TinyTeX:
```bash
~/.TinyTeX/bin/x86_64-linux/pdflatex main.tex
~/.TinyTeX/bin/x86_64-linux/bibtex main
~/.TinyTeX/bin/x86_64-linux/pdflatex main.tex
~/.TinyTeX/bin/x86_64-linux/pdflatex main.tex
```

