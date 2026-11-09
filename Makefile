PYTHON := .venv/bin/python
.PHONY: setup api test baseline reset
setup:
	python3 -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) scripts/check_connection.py
api:
	$(PYTHON) -m uvicorn consumers.api.main:app --host 127.0.0.1 --port 8000
test:
	$(PYTHON) -m pytest -m 'not contract' -q
baseline:
	$(PYTHON) parity/run_baseline.py
reset:
	bash scripts/reset.sh
