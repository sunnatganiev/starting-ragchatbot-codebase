#!/bin/bash
# Auto-fix code quality issues

echo "=== Auto-fixing code quality issues ==="
echo ""

echo "1. Organizing imports with isort..."
uv run isort backend/
echo "✓ Imports organized"
echo ""

echo "2. Formatting code with black..."
uv run black backend/
echo "✓ Code formatted"
echo ""

echo "3. Running flake8 to check remaining issues..."
uv run flake8 backend/ || echo "⚠ Some flake8 issues remain (requires manual fix)"
echo ""

echo "=== Auto-fix complete! ==="
echo "Note: Some issues may require manual intervention."
