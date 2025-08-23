install:
	python -m pip install -e .

test:
	pytest -q

lint:
	ruff check .

clean:
	bash tools/clean_artifacts.sh

clean-purge:
	bash tools/clean_artifacts.sh --purge
