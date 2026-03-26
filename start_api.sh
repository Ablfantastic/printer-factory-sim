#!/bin/bash
# Start the FastAPI backend server

echo "🏭 Starting 3D Printer Production Simulator API..."
echo ""

# Check if virtual environment exists, if not create it
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

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
