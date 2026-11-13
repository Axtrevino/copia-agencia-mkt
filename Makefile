.PHONY: install check run deploy

install:
	pip install -e ".[dev]"

check:
	ruff check . && ruff format --check . && pytest

deploy:
	modal deploy app/main.py
