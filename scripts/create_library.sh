#!/bin/bash

# Create Enterprise Architecture Library
# This script creates the initial library via the backend container

set -e

echo "=========================================="
echo "Creating Enterprise Architecture Library"
echo "=========================================="
echo ""

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose not found. Please install docker-compose."
    exit 1
fi

# Check if backend container is running
if ! docker-compose ps backend | grep -q "Up"; then
    echo "❌ Backend container is not running."
    echo "   Please start it with: docker-compose up -d backend"
    exit 1
fi

echo "✅ Backend container is running"
echo ""

# Run the creation script inside the backend container with Poetry
echo "📝 Creating library..."
docker-compose exec backend poetry run python scripts/create_initial_library.py

echo ""
echo "✨ Done! Refresh your browser to see the new library."
