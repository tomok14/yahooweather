PYFILES := $(shell printf '%s\n' *.py | grep -vE '^[a-zA-Z]\.py$$')

lint:
	pylint $(PYFILES) | tee lintlog
	ruff check $(PYFILES) | tee rufflog
