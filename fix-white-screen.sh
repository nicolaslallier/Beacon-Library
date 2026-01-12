#!/bin/bash

# Quick fix script for Beacon Library white screen issue
# This script disables authentication to allow immediate access

set -e

echo "🔧 Fixing Beacon Library white screen issue..."
echo ""

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Error: docker-compose not found"
    echo "Please install docker-compose first"
    exit 1
fi

# Create or update .env file
ENV_FILE=".env"

echo "📝 Configuring environment..."

# Check if .env exists
if [ -f "$ENV_FILE" ]; then
    echo "   .env file found, updating..."
    # Add or update VITE_ENABLE_AUTH
    if grep -q "VITE_ENABLE_AUTH" "$ENV_FILE"; then
        sed -i.bak 's/VITE_ENABLE_AUTH=.*/VITE_ENABLE_AUTH=false/' "$ENV_FILE"
        rm -f "$ENV_FILE.bak"
    else
        echo "" >> "$ENV_FILE"
        echo "# Disable authentication to fix white screen" >> "$ENV_FILE"
        echo "VITE_ENABLE_AUTH=false" >> "$ENV_FILE"
    fi
else
    echo "   Creating new .env file..."
    cat > "$ENV_FILE" << 'EOF'
# Beacon Library Configuration

# Disable authentication to fix white screen
VITE_ENABLE_AUTH=false

# API Configuration
VITE_API_URL=/api

# Keycloak Configuration (not used when auth is disabled)
VITE_KEYCLOAK_URL=http://localhost:8080
VITE_KEYCLOAK_REALM=beacon
VITE_KEYCLOAK_CLIENT_ID=beacon-library
EOF
fi

echo "✅ Environment configured (VITE_ENABLE_AUTH=false)"
echo ""

# Restart frontend service
echo "🔄 Restarting frontend service..."
docker-compose restart frontend

echo ""
echo "✨ Done! The frontend should now be accessible without authentication."
echo ""
echo "📋 Next steps:"
echo "   1. Wait 10-20 seconds for the frontend to restart"
echo "   2. Open: http://localhost or your domain"
echo "   3. Go to /catalog to upload files"
echo ""
echo "⚠️  Note: Authentication is now disabled. To re-enable it:"
echo "   - Edit .env and set VITE_ENABLE_AUTH=true"
echo "   - Configure Keycloak (see AUTHENTICATION.md)"
echo "   - Restart: docker-compose restart frontend"
echo ""
