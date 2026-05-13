PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

.PHONY: install install-dev validate regression pytest compile check

install:
	$(PIP) install -r requirements.txt

install-dev:
	$(PIP) install -r requirements-dev.txt

validate:
	$(PYTHON) scripts/validate_exports.py --summary

regression:
	$(PYTHON) test_regression.py

pytest:
	$(PYTHON) -m pytest -q

compile:
	PYTHON=$(PYTHON) ./scripts/run_checks.sh --compile-only

check:
	PYTHON=$(PYTHON) ./scripts/run_checks.sh
