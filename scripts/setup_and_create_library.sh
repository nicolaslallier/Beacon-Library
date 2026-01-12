#!/bin/bash

# Initialize Database and Create Enterprise Architecture Library
# This script runs migrations and creates the initial library

set -e

echo "=========================================="
echo "Database Setup & Library Creation"
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

# Run database migrations
echo "🗄️  Running database migrations..."
docker-compose exec backend poetry run alembic upgrade head

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Migration failed. Please check the logs."
    exit 1
fi

echo ""
echo "✅ Database migrations completed"
echo ""

# Create the library
echo "📚 Creating Enterprise Architecture library..."
docker-compose exec backend poetry run python scripts/create_initial_library.py

echo ""
echo "✨ Setup complete! Refresh your browser to see the new library."
