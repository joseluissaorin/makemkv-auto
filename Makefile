.PHONY: install install-dev clean test lint format check build docs

# Installation
install:
	pip install .

install-dev:
	pip install -e ".[dev]"
	pre-commit install

# Development
clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/ .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

test:
	pytest

test-cov:
	pytest --cov=makemkv_auto --cov-report=html --cov-report=term

# Code quality
lint:
	ruff check src/
	mypy src/

format:
	ruff format src/
	ruff check --fix src/

check: lint test

# Building
build:
	python -m build

# Documentation
docs:
	@echo "Documentation not yet implemented"

# System installation
system-install:
	sudo bash scripts/install.sh

# Maintenance
update-deps:
	pip-compile pyproject.toml
	pip-compile --extra=dev pyproject.toml -o requirements-dev.txt
