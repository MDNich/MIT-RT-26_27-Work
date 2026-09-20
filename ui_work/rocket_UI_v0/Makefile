# GNU Make entry points. Build each native package on its target operating system.
ifeq ($(OS),Windows_NT)
PYTHON ?= py -3.12
VENV_PY := .venv/Scripts/python.exe
else
PYTHON ?= python3
VENV_PY := .venv/bin/python
endif

.DEFAULT_GOAL := help
.NOTPARALLEL:
.PHONY: help setup run demo test lint runtime bridge package package-macos package-windows smoke verify-package clean

help:
	@$(PYTHON) scripts/build.py help
setup:
	$(PYTHON) scripts/build.py setup
run:
	$(VENV_PY) -m rocket_gnc_monitor
demo:
	$(VENV_PY) -m rocket_gnc_monitor --demo
test:
	$(VENV_PY) -m pytest -q
lint:
	$(VENV_PY) -m ruff check src tests --select F
runtime:
	$(VENV_PY) scripts/build.py runtime
bridge:
	$(VENV_PY) scripts/build.py bridge --engine "$(OPENROCKET_JAR)"
package:
	$(VENV_PY) scripts/build.py package
package-macos:
	$(VENV_PY) scripts/build.py package --platform Darwin
package-windows:
	$(VENV_PY) scripts/build.py package --platform Windows
smoke:
	$(VENV_PY) -m rocket_gnc_monitor --smoke-test --data-dir build/smoke
verify-package:
	$(VENV_PY) scripts/verify_package.py
clean:
	$(PYTHON) scripts/build.py clean
