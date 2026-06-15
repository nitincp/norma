# Norma Stack Setup

## 1. docker/langfuse-compose.yml

```yaml
version: '3.8'

networks:
  norma-net:
    driver: bridge

volumes:
  postgres-data:
  clickhouse-data:
  redis-data:
  minio-data:

services:
  langfuse-postgres:
    image: postgres:16-alpine
    container_name: langfuse-postgres
    networks:
      - norma-net
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  langfuse-clickhouse:
    image: clickhouse/clickhouse-server:24.3
    container_name: langfuse-clickhouse
    networks:
      - norma-net
    environment:
      CLICKHOUSE_DB: ${CLICKHOUSE_DB}
      CLICKHOUSE_USER: ${CLICKHOUSE_USER}
      CLICKHOUSE_PASSWORD: ${CLICKHOUSE_PASSWORD}
      CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT: 1
    ports:
      - "9000:9000"
      - "8123:8123"
    volumes:
      - clickhouse-data:/var/lib/clickhouse
      - ./clickhouse-config.xml:/etc/clickhouse-server/config.d/norma.xml:ro
    healthcheck:
      test: ["CMD-SHELL", "clickhouse-client --query 'SELECT 1'"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  langfuse-redis:
    image: redis:7-alpine
    container_name: langfuse-redis
    networks:
      - norma-net
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  minio:
    image: minio/minio:latest
    container_name: langfuse-minio
    networks:
      - norma-net
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio-data:/data
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  minio-init:
    image: minio/mc:latest
    container_name: langfuse-minio-init
    networks:
      - norma-net
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
      /usr/bin/mc config host add myminio http://minio:9000 ${MINIO_ROOT_USER} ${MINIO_ROOT_PASSWORD};
      /usr/bin/mc mb --ignore-existing myminio/langfuse;
      exit 0
      "
    restart: on-failure

  langfuse-worker:
    image: ghcr.io/langfuse/langfuse:latest
    container_name: langfuse-worker
    networks:
      - norma-net
    depends_on:
      langfuse-postgres:
        condition: service_healthy
      langfuse-clickhouse:
        condition: service_healthy
      langfuse-redis:
        condition: service_healthy
      minio-init:
        condition: service_started
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@langfuse-postgres:5432/${POSTGRES_DB}
      CLICKHOUSE_MIGRATION_URL: clickhouse://${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}@langfuse-clickhouse:9000/${CLICKHOUSE_DB}
      CLICKHOUSE_URL: http://${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}@langfuse-clickhouse:8123
      REDIS_URL: redis://langfuse-redis:6379
      CLICKHOUSE_CLUSTER_ENABLED: "false"
      S3_ENDPOINT: http://minio:9000
      S3_ACCESS_KEY_ID: ${MINIO_ROOT_USER}
      S3_SECRET_ACCESS_KEY: ${MINIO_ROOT_PASSWORD}
      S3_BUCKET_NAME: langfuse
      LANGFUSE_S3_BATCH_EXPORT_ENABLED: "false"
      LANGFUSE_DISABLE_TELEMETRY: "true"
    restart: unless-stopped

  langfuse-web:
    image: ghcr.io/langfuse/langfuse:latest
    container_name: langfuse-web
    networks:
      - norma-net
    depends_on:
      langfuse-postgres:
        condition: service_healthy
      langfuse-clickhouse:
        condition: service_healthy
      langfuse-redis:
        condition: service_healthy
    ports:
      - "3000:3000"
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@langfuse-postgres:5432/${POSTGRES_DB}
      CLICKHOUSE_MIGRATION_URL: clickhouse://${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}@langfuse-clickhouse:9000/${CLICKHOUSE_DB}
      CLICKHOUSE_URL: http://${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}@langfuse-clickhouse:8123
      REDIS_URL: redis://langfuse-redis:6379
      CLICKHOUSE_CLUSTER_ENABLED: "false"
      S3_ENDPOINT: http://minio:9000
      S3_ACCESS_KEY_ID: ${MINIO_ROOT_USER}
      S3_SECRET_ACCESS_KEY: ${MINIO_ROOT_PASSWORD}
      S3_BUCKET_NAME: langfuse
      LANGFUSE_S3_BATCH_EXPORT_ENABLED: "false"
      LANGFUSE_DISABLE_TELEMETRY: "true"
      NEXTAUTH_SECRET: ${NEXTAUTH_SECRET}
      NEXTAUTH_URL: http://localhost:3000
    restart: unless-stopped

  litellm-gateway:
    image: ghcr.io/berriai/litellm:main-stable
    container_name: langfuse-litellm
    networks:
      - norma-net
    ports:
      - "4000:4000"
    extra_hosts:
      - "host-gateway:host-gateway"
    volumes:
      - ./litellm-config.yaml:/app/config.yaml:ro
    environment:
      LITELLM_LOG: "DEBUG"
      LITELLM_PROXY_LOG_LEVEL: "INFO"
      LANGFUSE_PUBLIC_KEY: ${LANGFUSE_PUBLIC_KEY}
      LANGFUSE_SECRET_KEY: ${LANGFUSE_SECRET_KEY}
      LANGFUSE_HOST: http://langfuse-web:3000
    command: ["--config", "/app/config.yaml"]
    depends_on:
      langfuse-web:
        condition: service_started
    restart: unless-stopped
```

## 2. docker/clickhouse-config.xml

```xml
<?xml version="1.0"?>
<clickhouse>
  <!-- Accept connections from all interfaces for Docker networking -->
  <listen_host>0.0.0.0</listen_host>
  
  <!-- Cap memory to 50% of host RAM (4GB on 8GB VM) -->
  <max_server_memory_usage_to_ram_ratio>0.5</max_server_memory_usage_to_ram_ratio>
  
  <!-- Mark cache: 512MB default reduced to 128MB for memory-constrained environment -->
  <mark_cache_size>128000000</mark_cache_size>
  
  <!-- Uncompressed cache: 1GB default reduced to 256MB to stay within 512MB headroom -->
  <uncompressed_cache_size>268435456</uncompressed_cache_size>
  
  <!-- Merge thread pool: 8 default, reduced to 2 for CPU-only single-node -->
  <background_pool_size>2</background_pool_size>
  
  <!-- Mutation ratio check: number_of_free_entries must be < (2 * 0.75 = 1.5), set ratio to 0.25 to keep entries low -->
  <background_merges_mutations_concurrency_ratio>0.25</background_merges_mutations_concurrency_ratio>
  
  <!-- Disable query_log to reduce memory and disk I/O in memory-constrained environment -->
  <query_log remove="1"/>
  
  <!-- Disable text_log for debug queries to save memory and I/O -->
  <text_log remove="1"/>
  
  <!-- Disable trace_log to prevent stack trace overhead on CPU-only VM -->
  <trace_log remove="1"/>
  
  <!-- Disable metric_log to eliminate per-second metric collection overhead -->
  <metric_log remove="1"/>
  
  <!-- Disable asynchronous_metric_log to reduce background metric gathering -->
  <asynchronous_metric_log remove="1"/>
  
  <!-- Disable session_log to avoid tracking every client session -->
  <session_log remove="1"/>
  
  <!-- Disable part_log to eliminate per-part event logging overhead -->
  <part_log remove="1"/>
  
  <!-- Disable crash telemetry for self-hosted deployments -->
  <send_crash_reports>
    <enabled>0</enabled>
  </send_crash_reports>
  
  <!-- Disable interserver HTTP replication port (not needed for single-node) -->
  <interserver_http_port/>
  
  <!-- Set logger level to warning to reduce log verbosity on headless VM -->
  <logger>
    <level>warning</level>
    <log>/var/log/clickhouse-server/clickhouse-server.log</log>
    <errorlog>/var/log/clickhouse-server/clickhouse-server.err.log</errorlog>
  </logger>
</clickhouse>
```

## 3. docker/litellm-config.yaml

```yaml
model_list:
  - model_name: "local/qwen2.5-0.5b"
    litellm_params:
      model: "ollama/qwen2.5:0.5b"
      api_base: "http://host-gateway:11434"
      
  - model_name: "local/phi3-mini"
    litellm_params:
      model: "ollama/phi3:mini"
      api_base: "http://host-gateway:11434"

litellm_settings:
  callbacks:
    - "langfuse_otel"
  max_concurrent_requests: 2
  request_timeout: 30
  drop_params: true

router_settings:
  num_retries: 1

# LiteLLM reads these environment variables for Langfuse integration:
# LANGFUSE_PUBLIC_KEY: API key for Langfuse authentication
# LANGFUSE_SECRET_KEY: Secret key for Langfuse authentication
# LANGFUSE_HOST: Base URL of Langfuse instance (e.g., http://langfuse-web:3000)
```

## 4. .env.example

```bash
# Generate secrets with: openssl rand -hex 32

# Postgres
POSTGRES_DB=langfuse
POSTGRES_USER=langfuse
POSTGRES_PASSWORD=your_postgres_password_here

# ClickHouse
CLICKHOUSE_DB=langfuse
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=your_clickhouse_password_here

# Redis
REDIS_URL=redis://langfuse-redis:6379

# MinIO
MINIO_ROOT_USER=your_minio_user_here
MINIO_ROOT_PASSWORD=your_minio_password_here

# Langfuse Web
NEXTAUTH_SECRET=your_nextauth_secret_here

# Langfuse API Keys (generate via Langfuse UI after first startup)
LANGFUSE_PUBLIC_KEY=your_public_key_here
LANGFUSE_SECRET_KEY=your_secret_key_here

# Ollama
OLLAMA_HOST=http://host-gateway:11434
OLLAMA_NUM_PARALLEL=1
```

## 5. Startup Sequence

1. **Create volumes and networks** — Run `docker network create norma-net` and ensure volume directories exist on host.

2. **Populate .env** — Copy `.env.example` to `.env` and replace all placeholder values with actual secrets (use `openssl rand -hex 32` for sensitive fields).

3. **Start Postgres and ClickHouse first** — Run `docker compose -f docker/langfuse-compose.yml up -d langfuse-postgres langfuse-clickhouse` and wait for healthchecks to pass.

4. **Verify ClickHouse health** — Execute `docker exec langfuse-clickhouse clickhouse-client --query 'SELECT version()'` to confirm connectivity.

5. **Start Redis and MinIO** — Run `docker compose -f docker/langfuse-compose.yml up -d langfuse-redis minio`.

6. **Wait for MinIO init** — Run `docker logs langfuse-minio-init` and confirm bucket creation completed before proceeding.

7. **Start Langfuse worker and web** — Run `docker compose -f docker/langfuse-compose.yml up -d langfuse-worker langfuse-web` and poll `/healthz` endpoint.

8. **Verify Langfuse connectivity** — Confirm `curl http://localhost:3000` returns a 200 response and displays the Langfuse login page.

9. **Start LiteLLM gateway** — Run `docker compose -f docker/langfuse-compose.yml up -d litellm-gateway`.

10. **Test LiteLLM proxy** — Execute `curl -X POST http://localhost:4000/v1/chat/completions -H "Content-Type: application/json" -d '{"model": "local/qwen2.5-0.5b", "messages": [{"role": "user", "content": "test"}]}'` to confirm route availability.

11. **Confirm full stack health** — Run `docker compose -f docker/langfuse-compose.yml ps` and verify all services report `healthy` or `running` status.

12. **Access Langfuse UI** — Navigate to `http://<vm-ip>:3000` in a browser, create an initial user account, and generate API keys for LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY.

13. **Update .env with API keys** — Paste generated Langfuse keys into `.env` and restart litellm-gateway with `docker compose -f docker/langfuse-compose.yml restart litellm-gateway`.

14. **Verify end-to-end observability** — Send a request through LiteLLM proxy and confirm trace appears in Langfuse dashboard within 5 seconds.