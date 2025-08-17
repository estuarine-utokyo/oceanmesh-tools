install:
	python -m pip install -e .

test:
	pytest -q

lint:
	ruff check .

