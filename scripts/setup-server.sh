#!/bin/bash
# Setup script for Mealie MCP Server on a dedicated host

set -e

echo "=== Setting up Mealie MCP Server Host ==="

# Detect package manager
if command -v apt &> /dev/null; then
    PKG_MANAGER="apt"
elif command -v dnf &> /dev/null; then
    PKG_MANAGER="dnf"
else
    echo "❌ Unsupported package manager. Please install Python 3.11+ manually."
    exit 1
fi

# Find available Python 3.11+
if command -v python3.12 &> /dev/null; then
    PYTHON_CMD="python3.12"
elif command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
elif command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if [[ $(echo "$PYTHON_VERSION >= 3.11" | bc -l) -eq 1 ]]; then
        PYTHON_CMD="python3"
    else
        echo "❌ Python 3.11+ is required. Found Python $PYTHON_VERSION"
        exit 1
    fi
else
    echo "❌ Python 3.11+ is required but not found."
    exit 1
fi

echo "🐍 Using Python: $PYTHON_CMD ($($PYTHON_CMD --version))"

# Install system dependencies
echo "📦 Installing system dependencies..."
if [ "$PKG_MANAGER" = "apt" ]; then
    sudo apt update
    sudo apt install -y python3-venv python3-pip git
elif [ "$PKG_MANAGER" = "dnf" ]; then
    sudo dnf install -y python3-venv python3-pip git
fi

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "📂 Project directory: $PROJECT_DIR"

# Create Python virtual environment
echo "🐍 Setting up Python virtual environment..."
$PYTHON_CMD -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "⚠️  Please edit .env with your Mealie credentials:"
    echo "    nano $PROJECT_DIR/.env"
    echo ""
fi

# Install systemd service
echo "🔧 Installing systemd user service..."
mkdir -p ~/.config/systemd/user

# Generate service file with correct paths
cat > ~/.config/systemd/user/mealie-mcp.service << EOF
[Unit]
Description=Mealie MCP Server
After=network.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/.venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="MCP_TRANSPORT=sse"
Environment="MCP_HOST=0.0.0.0"
Environment="MCP_PORT=8080"
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/.venv/bin/python -m mealie_mcp.server
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
EOF

# Enable lingering for user services to persist after logout
echo "🔐 Enabling user service lingering..."
sudo loginctl enable-linger $USER

# Reload and enable service
systemctl --user daemon-reload

echo ""
echo "✅ Setup complete!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Next steps:"
echo ""
echo "  1. Edit .env with your Mealie credentials:"
echo "     nano $PROJECT_DIR/.env"
echo ""
echo "  2. Start the service:"
echo "     systemctl --user enable --now mealie-mcp"
echo ""
echo "  3. Check status:"
echo "     systemctl --user status mealie-mcp"
echo ""
echo "  4. Expose via Tailscale Funnel:"
echo "     tailscale funnel 8080"
echo ""
echo "  5. View logs:"
echo "     journalctl --user -u mealie-mcp -f"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
