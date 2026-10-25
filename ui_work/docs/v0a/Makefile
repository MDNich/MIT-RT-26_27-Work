LATEXMK ?= latexmk
PYTHON ?= python3
REPORT := Rocket_GNC_Monitor_v0a
.PHONY: all clean reference
all:
	$(LATEXMK) -pdf -interaction=nonstopmode -halt-on-error -file-line-error -outdir=build -jobname=$(REPORT) main.tex
	cp build/$(REPORT).pdf $(REPORT).pdf
reference:
	$(PYTHON) build_reference.py --app "$(APP)"
clean:
	rm -rf build
