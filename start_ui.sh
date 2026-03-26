#!/bin/bash
# Start the Streamlit frontend dashboard

echo "📊 Starting 3D Printer Production Simulator Dashboard..."
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

# Ensure backend is running
echo "Checking if API is available at http://localhost:8000..."
if command -v curl &> /dev/null; then
    if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "⚠️  Warning: Backend API not responding!"
        echo "   Please start the API first: ./start_api.sh"
        echo ""
    fi
fi

echo ""
echo "Starting Streamlit dashboard on http://localhost:8501"
echo ""
streamlit run app/ui.py --server.port 8501 --server.address 0.0.0.0
