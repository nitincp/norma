FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# Install Node.js for Promptfoo CLI
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/*

RUN npm install -g promptfoo backlog.md

WORKDIR /workspace

# Copy project definition first for layer caching
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]" || true

# add host-gateway alias so OLLAMA_BASE_URL resolves on Linux Docker
RUN echo "host-gateway" > /etc/hosts.ollama || true
