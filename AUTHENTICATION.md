# Authentication Configuration

## Overview

Beacon Library uses Keycloak for authentication. However, **authentication is disabled by default for development** to make it easier to get started.

## Quick Start (No Authentication)

By default, Beacon Library runs **without authentication**. Both frontend and backend are configured to work without Keycloak:

- **Frontend**: `VITE_ENABLE_AUTH=false` (default)
- **Backend**: `ENABLE_AUTH=false` (default)

This allows you to:
- Access all pages without login
- Upload files to the catalog
- Browse libraries
- Perform all operations without authentication
- A mock admin user is automatically created for development

**No additional configuration needed!** Just run:

```bash
docker-compose up -d
```

And access the application at `http://localhost:8181`

## Enabling Authentication (Production)

To enable Keycloak authentication for production deployments:

### 1. Set Environment Variables

Create a `.env` file in the root directory with:

```bash
# Enable authentication
ENABLE_AUTH=true
VITE_ENABLE_AUTH=true

# Keycloak URLs (frontend - must be accessible from browser)
VITE_KEYCLOAK_URL=https://your-keycloak-domain.com
VITE_KEYCLOAK_REALM=beacon
VITE_KEYCLOAK_CLIENT_ID=beacon-library

# Keycloak URLs (backend - internal)
KEYCLOAK_URL=http://beacon-keycloak:8080
KEYCLOAK_REALM=beacon
KEYCLOAK_CLIENT_ID=beacon-library
KEYCLOAK_CLIENT_SECRET=your-secret-here
```

**Important Notes:**
- `VITE_KEYCLOAK_URL` must be accessible from the **browser** (not just from Docker)
- `KEYCLOAK_URL` is used by the backend and can be an internal Docker hostname
- Both frontend and backend must have `ENABLE_AUTH=true` for authentication to work

### 2. Configure Keycloak

#### Create Realm
1. Access Keycloak admin console
2. Create a realm named `beacon`

#### Create Client
1. Go to Clients → Create
2. Client ID: `beacon-library`
3. Client Protocol: `openid-connect`
4. Access Type: `public`
5. Valid Redirect URIs:
   - `https://your-domain.com/*`
   - `http://localhost:3000/*`
6. Web Origins: `+` (or specify your domains)

#### Create Users
1. Go to Users → Add user
2. Set username, email, etc.
3. Go to Credentials tab
4. Set password (disable temporary)

### 3. Restart Services

After changing environment variables, restart the containers:

```bash
docker-compose down
docker-compose up -d --build
```

## Architecture

### Authentication Flow

When authentication is **enabled** (`ENABLE_AUTH=true`):

1. **Frontend**: Uses Keycloak JS adapter to authenticate users
2. **Backend**: Validates JWT tokens from Keycloak using JWKS
3. **User Context**: Extracts user ID, roles, and permissions from token

When authentication is **disabled** (`ENABLE_AUTH=false`):

1. **Frontend**: Bypasses Keycloak, no login required
2. **Backend**: Creates a mock admin user for all requests
3. **Development Only**: ⚠️ Never use in production!

## Current Configuration

The application checks for the `ENABLE_AUTH` environment variable:
- **false** (default): No authentication required, mock admin user created
- **true**: Keycloak authentication required

## Troubleshooting

### 401 Unauthorized Error

If you see `401 Unauthorized` errors:

1. **Check if auth is properly disabled**: Both `ENABLE_AUTH` and `VITE_ENABLE_AUTH` should be `false`
2. **Verify environment variables are loaded**: Check Docker container logs
3. **Restart containers**: `docker-compose restart backend frontend`

### White Screen Issue

If you see a white screen:

1. **Check Browser Console**: Open Developer Tools (F12) and look for errors
2. **Disable Auth**: Set both `ENABLE_AUTH=false` and `VITE_ENABLE_AUTH=false`
3. **Verify Keycloak URL**: If auth is enabled, ensure `VITE_KEYCLOAK_URL` is accessible from your browser
4. **Check Network Tab**: Look for failed requests to Keycloak
5. **Restart Frontend**: `docker-compose restart frontend`

### Common Issues

#### CORS Errors
- Configure Keycloak Web Origins properly
- Add `*` or specific domains

#### Redirect Loop
- Check Valid Redirect URIs in Keycloak client settings
- Ensure the URIs match your deployment URL

#### Connection Refused
- `VITE_KEYCLOAK_URL` must be accessible from the **browser**, not just from Docker
- For production: Use public domain (e.g., `https://keycloak.yourdomain.com`)
- For development: Use `http://localhost:8080` (if Keycloak is exposed)

## Environment Variables Reference

### Backend Variables

- `ENABLE_AUTH` - Enable/disable authentication (default: `false`)
- `KEYCLOAK_URL` - Keycloak server URL (internal, for backend)
- `KEYCLOAK_REALM` - Keycloak realm name
- `KEYCLOAK_CLIENT_ID` - Keycloak client ID
- `KEYCLOAK_CLIENT_SECRET` - Client secret (for confidential clients)
- `KEYCLOAK_VERIFY_TOKEN` - Verify JWT signature (default: `true`)

### Frontend Variables

- `VITE_ENABLE_AUTH` - Enable/disable authentication UI (default: `false`)
- `VITE_KEYCLOAK_URL` - Keycloak server URL (must be browser-accessible)
- `VITE_KEYCLOAK_REALM` - Keycloak realm name
- `VITE_KEYCLOAK_CLIENT_ID` - Keycloak client ID

## Security Notes

⚠️ **WARNING**: Never use `ENABLE_AUTH=false` in production! This creates a mock admin user with full access and bypasses all security.

For production deployments:
1. Always set `ENABLE_AUTH=true`
2. Use a properly configured Keycloak instance
3. Use strong client secrets
4. Enable token signature verification
5. Configure proper CORS settings
6. Use HTTPS for all Keycloak URLs

## Quick Fix Commands

### Disable Authentication (Development)
```bash
# Add to .env file
echo "ENABLE_AUTH=false" >> .env
echo "VITE_ENABLE_AUTH=false" >> .env

# Restart services
docker-compose restart backend frontend
```

### Enable Authentication (Production)
```bash
# Edit .env file to set:
# ENABLE_AUTH=true
# VITE_ENABLE_AUTH=true
# ... (configure Keycloak URLs)

# Rebuild and restart
docker-compose down
docker-compose up -d --build
```
