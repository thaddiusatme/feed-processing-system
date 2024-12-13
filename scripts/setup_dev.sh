#!/bin/bash

# Exit on error
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo "🚀 Setting up development environment..."

# Check if python3 is installed
if ! command -v python3 &> /dev/null; then
    echo "${RED}Python 3 is not installed. Please install Python 3 first.${NC}"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
else
    echo "Virtual environment already exists."
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
if command -v pre-commit &> /dev/null; then
    echo "Installing pre-commit hooks..."
    pre-commit install
else
    echo "Installing pre-commit..."
    pip install pre-commit
    pre-commit install
fi

# Run initial test to verify setup
echo "Running tests to verify setup..."
python -m pytest tests/unit -v

echo "${GREEN}✅ Development environment setup complete!${NC}"
echo "To activate the virtual environment, run: source venv/bin/activate"
