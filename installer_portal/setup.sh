#!/bin/bash
# ============================================================
# One-click setup for macOS/Linux.
# Run once: bash setup.sh (or double-click if your OS allows it).
# Creates the virtual environment and installs Flask automatically.
# ============================================================

cd "$(dirname "$0")"

if [ ! -f ".venv/bin/python" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    if [ $? -ne 0 ]; then
        echo ""
        echo "ERROR: Could not create the virtual environment."
        echo "Make sure Python 3 is installed, then try again."
        exit 1
    fi
fi

echo "Installing dependencies..."
.venv/bin/python -m pip install --upgrade pip > /dev/null
.venv/bin/python -m pip install -r requirements.txt

echo ""
echo "============================================================"
echo " Setup complete! Run ./run.sh any time to start the app."
echo "============================================================"
