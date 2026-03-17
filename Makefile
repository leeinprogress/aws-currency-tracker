.PHONY: help install test lint format check validate build clean

help:
	@echo "Available commands:"
	@echo "  make install      - Install all dependencies"
	@echo "  make test         - Run tests"
	@echo "  make lint         - Run linter (ruff)"
	@echo "  make format       - Format code with ruff"
	@echo "  make check        - Run lint + test (same as CI)"
	@echo "  make validate     - Validate SAM template"
	@echo "  make build        - SAM build"
	@echo "  make clean        - Clean cache and build files"

install:
	pip install -r requirements.txt -r requirements-dev.txt

test:
	pytest -v

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

check: lint test

validate:
	sam validate

build:
	sam build

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .aws-sam/
