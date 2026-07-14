#!/bin/bash
# ============================================================
# One-click run for macOS/Linux.
# Run: ./run.sh (after running setup.sh once).
# ============================================================

cd "$(dirname "$0")"

if [ ! -f ".venv/bin/python" ]; then
    echo ""
    echo "It looks like setup hasn't been run yet."
    echo "Please run: bash setup.sh"
    echo ""
    exit 1
fi

echo "Starting Installer Certification Registry..."
echo "Once you see \"Running on http://127.0.0.1:5000\", open that link in your browser."
echo "Press Ctrl+C to stop the server."
echo ""

.venv/bin/python app.py
