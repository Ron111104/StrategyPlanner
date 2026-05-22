#!/usr/bin/env bash
set -euo pipefail

echo "=== Strategy Planning Platform ==="
echo "Installing dependencies..."
pip install -r requirements.txt --quiet

echo "Starting server..."
python run.py
