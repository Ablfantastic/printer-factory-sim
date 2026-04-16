#!/bin/bash
# Start the FastAPI backend server (manufacturer application)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$SCRIPT_DIR"

echo "🏭 Starting 3D Printer Production Simulator API..."
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

# Initialize database
echo "Initializing database..."
python -c "from app.seed import init_db, seed_data; init_db(); seed_data()" 2>/dev/null || true

# Start FastAPI server
echo ""
echo "Starting server on http://localhost:8000"
echo "API docs available at http://localhost:8000/docs"
echo ""
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
