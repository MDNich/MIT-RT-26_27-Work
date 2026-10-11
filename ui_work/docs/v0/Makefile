LATEXMK ?= latexmk
MAIN := Rocket_GNC_Monitor_v0
.PHONY: all clean
all:
	$(LATEXMK) -pdf -interaction=nonstopmode -halt-on-error -file-line-error $(MAIN).tex
clean:
	$(LATEXMK) -c $(MAIN).tex
