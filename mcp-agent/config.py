"""Configuration for MCP Agent Bridge."""

import os
from dotenv import load_dotenv

load_dotenv()

# LM Studio configuration
LMSTUDIO_URL = os.getenv("LMSTUDIO_URL", "http://192.168.2.35:1234")
LMSTUDIO_MODEL = os.getenv("LMSTUDIO_MODEL", "default")  # LM Studio uses loaded model

# Beacon Library MCP configuration
# Use HTTP directly for local network to avoid SSL issues
BEACON_MCP_URL = os.getenv("BEACON_MCP_URL", "http://localhost:8200/mcp")
AGENT_ID = os.getenv("AGENT_ID", "lmstudio-agent")

# SSL verification - set to False if using self-signed certificates
VERIFY_SSL = os.getenv("VERIFY_SSL", "true").lower() in ("true", "1", "yes")

# Server configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))
