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
	$(PYTHON) -m py_compile pipeline.py pipeline_v2.py scripts/export_for_sch_review.py scripts/validate_exports.py test_regression.py test_pin_extraction.py test_drc_hints_v2.py

check: compile validate regression pytest
