# Variables
SHELL := /bin/bash
VENV := venv
PYTHON := python3
VENV_BIN := $(VENV)/bin

# Ensure all commands run in the same shell
.ONESHELL:

# Setup development environment
.PHONY: setup
setup:
	@echo "🚀 Setting up development environment..."
	$(PYTHON) -m venv $(VENV)
	. $(VENV_BIN)/activate && \
	$(VENV_BIN)/pip install --upgrade pip && \
	$(VENV_BIN)/pip install -r requirements.txt && \
	$(VENV_BIN)/pip install -r requirements-dev.txt && \
	$(VENV_BIN)/pre-commit install
	@echo "✅ Development environment setup complete!"

# Run tests
.PHONY: test
test:
	@echo "🧪 Running tests..."
	. $(VENV_BIN)/activate && \
	$(VENV_BIN)/pytest tests/ -v --cov=feed_processor

# Run linting
.PHONY: lint
lint:
	@echo "🔍 Running linters..."
	. $(VENV_BIN)/activate && \
	$(VENV_BIN)/flake8 feed_processor tests && \
	$(VENV_BIN)/mypy feed_processor tests

# Format code
.PHONY: format
format:
	@echo "✨ Formatting code..."
	. $(VENV_BIN)/activate && \
	$(VENV_BIN)/black feed_processor tests && \
	$(VENV_BIN)/isort feed_processor tests

# Run pre-commit hooks
.PHONY: hooks
hooks:
	@echo "🪝 Running pre-commit hooks..."
	. $(VENV_BIN)/activate && \
	$(VENV_BIN)/pre-commit run --all-files

# Clean up
.PHONY: clean
clean:
	@echo "🧹 Cleaning up..."
	rm -rf $(VENV)
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +

# Build documentation
.PHONY: docs
docs:
	@echo "📚 Building documentation..."
	. $(VENV_BIN)/activate && \
	cd docs && \
	$(VENV_BIN)/sphinx-build -b html source build

# Install development dependencies
.PHONY: dev-deps
dev-deps:
	@echo "📦 Installing development dependencies..."
	. $(VENV_BIN)/activate && \
	$(VENV_BIN)/pip install -r requirements-dev.txt

# Install production dependencies
.PHONY: prod-deps
prod-deps:
	@echo "📦 Installing production dependencies..."
	. $(VENV_BIN)/activate && \
	$(VENV_BIN)/pip install -r requirements.txt

# Run the application
.PHONY: run
run:
	@echo "🚀 Running the application..."
	. $(VENV_BIN)/activate && \
	$(VENV_BIN)/python -m feed_processor

# Help target
.PHONY: help
help:
	@echo "Available targets:"
	@echo "  setup      - Set up development environment"
	@echo "  test       - Run tests with coverage"
	@echo "  lint       - Run linting checks"
	@echo "  format     - Format code with black and isort"
	@echo "  hooks      - Run pre-commit hooks"
	@echo "  clean      - Clean up generated files"
	@echo "  docs       - Build documentation"
	@echo "  dev-deps   - Install development dependencies"
	@echo "  prod-deps  - Install production dependencies"
	@echo "  run        - Run the application"
	@echo "  help       - Show this help message"
