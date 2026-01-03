#!/bin/bash
# Deploy both Fraser and Sam's MCP server instances with Tailscale Serve

set -e

REPO_DIR="$HOME/Repos/mealie-mcp-server"
SYSTEMD_DIR="$HOME/.config/systemd/user"

echo "=================================="
echo "Mealie MCP Multi-User Deployment"
echo "=================================="
echo ""

# Stop existing services if running
echo "→ Stopping existing services..."
systemctl --user stop mealie-mcp 2>/dev/null || true
systemctl --user stop mealie-mcp-fraser 2>/dev/null || true
systemctl --user stop mealie-mcp-sam 2>/dev/null || true

# Stop existing Tailscale funnel
echo "→ Removing existing Tailscale funnel..."
sudo tailscale funnel off 2>/dev/null || true

# Install new service files
echo "→ Installing systemd service files..."
mkdir -p "$SYSTEMD_DIR"
cp "$REPO_DIR/scripts/mealie-mcp-fraser.service" "$SYSTEMD_DIR/"
cp "$REPO_DIR/scripts/mealie-mcp-sam.service" "$SYSTEMD_DIR/"

# Reload systemd
echo "→ Reloading systemd..."
systemctl --user daemon-reload

# Start services
echo "→ Starting Fraser's server (port 8080)..."
systemctl --user enable --now mealie-mcp-fraser

echo "→ Starting Sam's server (port 8081)..."
systemctl --user enable --now mealie-mcp-sam

# Wait for servers to start
sleep 3

# Check service status
echo ""
echo "→ Fraser's service status:"
systemctl --user status mealie-mcp-fraser --no-pager -l | head -10

echo ""
echo "→ Sam's service status:"
systemctl --user status mealie-mcp-sam --no-pager -l | head -10

# Configure Tailscale Serve (authenticated access only)
echo ""
echo "→ Configuring Tailscale Serve (replaces Funnel for security)..."
echo "  This requires Tailscale authentication - no public access"

# Serve Fraser's instance at /fraser
sudo tailscale serve --bg --https=443 --set-path=/fraser http://127.0.0.1:8080

# Serve Sam's instance at /sam  
sudo tailscale serve --bg --https=443 --set-path=/sam http://127.0.0.1:8081

echo ""
echo "→ Tailscale Serve status:"
sudo tailscale serve status

echo ""
echo "=================================="
echo "✅ Deployment Complete!"
echo "=================================="
echo ""
echo "Fraser's URL: https://rainworth-server.tailbf31d9.ts.net/fraser/mcp"
echo "Sam's URL:    https://rainworth-server.tailbf31d9.ts.net/sam/mcp"
echo ""
echo "Security: Tailscale Serve (not Funnel) - requires Tailscale authentication"
echo "          Only devices on your Tailscale network can access these servers"
echo ""
echo "Service management:"
echo "  View logs:    journalctl --user -u mealie-mcp-fraser -f"
echo "                journalctl --user -u mealie-mcp-sam -f"
echo "  Restart:      systemctl --user restart mealie-mcp-fraser"
echo "                systemctl --user restart mealie-mcp-sam"
echo "  Stop:         systemctl --user stop mealie-mcp-fraser"
echo "                systemctl --user stop mealie-mcp-sam"
echo ""
