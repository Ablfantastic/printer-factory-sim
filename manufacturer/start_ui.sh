#!/bin/bash
# Start the Streamlit frontend dashboard (manufacturer application)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$SCRIPT_DIR"

echo "📊 Starting 3D Printer Production Simulator Dashboard..."
echo ""

# Check if virtual environment exists at repo root, if not create it
if [ ! -d "$REPO_ROOT/venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$REPO_ROOT/venv"
fi

# Activate virtual environment
source "$REPO_ROOT/venv/bin/activate"

# Install dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Ensure backend is running
echo "Checking if API is available at http://localhost:8000..."
if command -v curl &> /dev/null; then
    if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "⚠️  Warning: Backend API not responding!"
        echo "   Please start the API first: ./start_api.sh (from repo root) or manufacturer/start_api.sh"
        echo ""
    fi
fi

echo ""
echo "Starting Streamlit dashboard on http://localhost:8501"
echo ""
streamlit run app/ui.py --server.port 8501 --server.address 0.0.0.0
