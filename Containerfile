FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for better caching
COPY pyproject.toml .

# Create minimal src structure for pip install
RUN mkdir -p src/mealie_mcp && \
    touch src/mealie_mcp/__init__.py && \
    pip install --no-cache-dir .

# Copy actual source code
COPY src/ src/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MCP_TRANSPORT=sse
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8080

# Expose the MCP server port
EXPOSE 8080

# Run the MCP server
CMD ["python", "-m", "mealie_mcp.server"]
