# GNU Make entry points. Build each native package on its target operating system.
ifeq ($(OS),Windows_NT)
PYTHON ?= py -3.12
VENV_PY := .venv/Scripts/python.exe
else
PYTHON ?= python3
VENV_PY := .venv/bin/python
endif

ENGINE_OPTIONS = --engine "$(OPENROCKET_JAR)" --download "$(OPENROCKET_DOWNLOAD)"
STATION ?= base

.DEFAULT_GOAL := help
.NOTPARALLEL:
.PHONY: help setup run away demo test lint runtime bridge package package-macos package-windows smoke verify-package clean

help:
	@$(PYTHON) scripts/build.py help
setup:
	$(PYTHON) scripts/build.py setup
run:
	$(VENV_PY) -m rocket_gnc_monitor --station $(STATION)
away:
	$(VENV_PY) -m rocket_gnc_monitor --station away
demo:
	$(VENV_PY) -m rocket_gnc_monitor --demo --station $(STATION)
test:
	$(VENV_PY) -m pytest -q
lint:
	$(VENV_PY) -m ruff check src tests --select F
runtime:
	$(VENV_PY) scripts/build.py runtime
bridge:
	$(VENV_PY) scripts/build.py bridge $(ENGINE_OPTIONS)
package:
	$(VENV_PY) scripts/build.py package $(ENGINE_OPTIONS)
package-macos:
	$(VENV_PY) scripts/build.py package --platform Darwin $(ENGINE_OPTIONS)
package-windows:
	$(VENV_PY) scripts/build.py package --platform Windows $(ENGINE_OPTIONS)
smoke:
	$(VENV_PY) -m rocket_gnc_monitor --smoke-test --data-dir build/smoke
verify-package:
	$(VENV_PY) scripts/verify_package.py
clean:
	$(PYTHON) scripts/build.py clean
