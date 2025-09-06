#!/bin/bash
set -e

echo "Python version: $(python --version)"
echo "Upgrading pip..."
pip install --upgrade pip

echo "Installing dependencies with binary wheels only..."
pip install --only-binary=all -r requirements.txt
