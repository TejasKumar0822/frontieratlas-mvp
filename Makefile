install:
	pip install -r requirements.txt

smoke:
	python -m src.main --startups 20 --products 20 --papers 20

trial:
	python -m src.main --startups 1000 --products 1000 --papers 1000

test:
	pytest -q
