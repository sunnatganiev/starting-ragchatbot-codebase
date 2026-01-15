#!/bin/bash
# Run all code quality checks

set -e  # Exit on first error

echo "=== Code Quality Checks ==="
echo ""

echo "1. Running black (code formatting check)..."
uv run black --check backend/
echo "✓ Black check passed"
echo ""

echo "2. Running isort (import order check)..."
uv run isort --check-only backend/
echo "✓ Isort check passed"
echo ""

echo "3. Running flake8 (linting)..."
uv run flake8 backend/
echo "✓ Flake8 check passed"
echo ""

echo "4. Running mypy (type checking)..."
uv run mypy backend/ --exclude 'backend/tests/' || echo "⚠ Mypy found some type issues (non-blocking)"
echo ""

echo "5. Running tests with coverage..."
uv run pytest
echo "✓ Tests passed"
echo ""

echo "=== All quality checks complete! ==="
