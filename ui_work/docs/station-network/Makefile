LATEXMK ?= latexmk
PYTHON ?= python3
REPORT := Ground_Station_Network_Requirements_Protocol
.PHONY: all check clean
all: check
	$(LATEXMK) -pdf -interaction=nonstopmode -halt-on-error -file-line-error -outdir=build -jobname=$(REPORT) main.tex
	cp build/$(REPORT).pdf $(REPORT).pdf
check:
	$(PYTHON) validate_document.py
clean:
	rm -rf build
