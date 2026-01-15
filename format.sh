#!/bin/bash
# Format code using black and isort

echo "Running isort to organize imports..."
uv run isort backend/

echo "Running black to format code..."
uv run black backend/

echo "Code formatting complete!"
