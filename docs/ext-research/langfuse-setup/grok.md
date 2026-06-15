```markdown
# Norma Stack Setup

## 1. docker/langfuse-compose.yml

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    container_name: langfuse-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - norma-net

  clickhouse:
    image: clickhouse/clickhouse-server:24.3
    container_name: langfuse-clickhouse
    restart: unless-stopped
    volumes:
      - clickhouse_data:/var/lib/clickhouse
      - ./clickhouse-config.xml:/etc/clickhouse-server/config.d/norma.xml:ro
    healthcheck:
      test: ["CMD", "clickhouse-client", "--query", "SELECT 1"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - norma-net

  redis:
    image: redis:7-alpine
    container_name: langfuse-redis
    restart: unless-stopped
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - norma-net

  minio:
    image: minio/minio:latest
    container_name: langfuse-minio
    restart: unless-stopped
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes:
      - minio_data:/data
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - norma-net

  minio-init:
    image: minio/mc:latest
    container_name: langfuse-minio-init
    restart: on-failure
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
        mc alias set local http://minio:9000 ${MINIO_ROOT_USER} ${MINIO_ROOT_PASSWORD} &&
        mc mb --ignore-existing local/langfuse
      "
    networks:
      - norma-net

  langfuse-worker:
    image: ghcr.io/langfuse/langfuse-worker:latest
    container_name: langfuse-worker
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      clickhouse:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      CLICKHOUSE_MIGRATION_URL: clickhouse://${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}@langfuse-clickhouse:9000/langfuse
      REDIS_HOST: redis
      REDIS_PORT: 6379
      CLICKHOUSE_CLUSTER_ENABLED: "false"
      LANGFUSE_S3_EVENT_UPLOAD_BUCKET: langfuse
      LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID: ${MINIO_ROOT_USER}
      LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY: ${MINIO_ROOT_PASSWORD}
      LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT: http://minio:9000
      LANGFUSE_S3_BATCH_EXPORT_ENABLED: "false"
    networks:
      - norma-net

  langfuse-web:
    image: ghcr.io/langfuse/langfuse-web:latest
    container_name: langfuse-web
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      clickhouse:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    ports:
      - "${LANGFUSE_PORT:-3000}:3000"
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      CLICKHOUSE_MIGRATION_URL: clickhouse://${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}@langfuse-clickhouse:9000/langfuse
      REDIS_HOST: redis
      REDIS_PORT: 6379
      NEXTAUTH_SECRET: ${NEXTAUTH_SECRET}
      SALT: ${SALT}
      CLICKHOUSE_CLUSTER_ENABLED: "false"
      LANGFUSE_S3_EVENT_UPLOAD_BUCKET: langfuse
      LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID: ${MINIO_ROOT_USER}
      LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY: ${MINIO_ROOT_PASSWORD}
      LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT: http://minio:9000
      LANGFUSE_S3_BATCH_EXPORT_ENABLED: "false"
      LANGFUSE_PUBLIC_KEY: ${LANGFUSE_PUBLIC_KEY}
      LANGFUSE_SECRET_KEY: ${LANGFUSE_SECRET_KEY}
    networks:
      - norma-net

  litellm-gateway:
    image: ghcr.io/berriai/litellm:main-stable
    container_name: litellm-gateway
    restart: unless-stopped
    ports:
      - "${LITELLM_PORT:-4000}:4000"
    extra_hosts:
      - "host-gateway:host-gateway"
    volumes:
      - ./litellm-config.yaml:/app/config.yaml:ro
    environment:
      LITELLM_CONFIG: /app/config.yaml
      LANGFUSE_PUBLIC_KEY: ${LANGFUSE_PUBLIC_KEY}
      LANGFUSE_SECRET_KEY: ${LANGFUSE_SECRET_KEY}
      LANGFUSE_HOST: http://langfuse-web:3000
    depends_on:
      langfuse-web:
        condition: service_started
    networks:
      - norma-net

networks:
  norma-net:
    driver: bridge
    name: norma-net

volumes:
  postgres_data:
  clickhouse_data:
  redis_data:
  minio_data:
```

## 2. docker/clickhouse-config.xml

```xml
<clickhouse>
  <!-- Cap memory to 50% of host RAM for ~8GB shared environment -->
  <max_server_memory_usage_to_ram_ratio>0.5</max_server_memory_usage_to_ram_ratio>

  <!-- Reduce caches for ~512MB container headroom on single-node setup -->
  <mark_cache_size>536870912</mark_cache_size>
  <uncompressed_cache_size>134217728</uncompressed_cache_size>

  <!-- Disable all internal system logs to reduce I/O and storage overhead -->
  <query_log>
    <database>system</database>
    <table>query_log</table>
    <partition_by>toYYYYMM(event_date)</partition_by>
    <ttl>event_date + INTERVAL 30 DAY DELETE</ttl>
    <enabled>false</enabled>
  </query_log>
  <text_log>
    <enabled>false</enabled>
  </text_log>
  <trace_log>
    <enabled>false</enabled>
  </trace_log>
  <metric_log>
    <enabled>false</enabled>
  </metric_log>
  <asynchronous_metric_log>
    <enabled>false</enabled>
  </asynchronous_metric_log>
  <session_log>
    <enabled>false</enabled>
  </session_log>
  <part_log>
    <enabled>false</enabled>
  </part_log>

  <!-- Disable crash telemetry for self-hosted privacy -->
  <send_crash_reports>false</send_crash_reports>

  <!-- Listen on all interfaces for container networking -->
  <listen_host>0.0.0.0</listen_host>

  <!-- Logger level reduced to minimize noise -->
  <logger>
    <level>warning</level>
  </logger>

  <!-- Disable interserver HTTP (single-node) -->
  <interserver_http_port>0</interserver_http_port>

  <!-- Pass 24.3 sanity check: number_of_free_entries_in_pool_to_execute_mutation < background_pool_size × background_merges_mutations_concurrency_ratio -->
  <background_pool_size>18</background_pool_size>
  <background_merges_mutations_concurrency_ratio>2</background_merges_mutations_concurrency_ratio>
  <number_of_free_entries_in_pool_to_execute_mutation>16</number_of_free_entries_in_pool_to_execute_mutation>
</clickhouse>
```

## 3. docker/litellm-config.yaml

```yaml
model_list:
  - model_name: local/qwen2.5-0.5b
    litellm_params:
      model: ollama/qwen2.5:0.5b
      api_base: http://host-gateway:11434
  - model_name: local/phi3-mini
    litellm_params:
      model: ollama/phi3:mini
      api_base: http://host-gateway:11434

litellm_settings:
  callbacks: ["langfuse_otel"]
  max_concurrent_requests: 2
  request_timeout: 30
  drop_params: true

router_settings:
  num_retries: 1

# LiteLLM reads the following env vars for Langfuse tracing:
# LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST
```

## 4. .env.example

```env
# Generate secrets with: openssl rand -hex 32

# Langfuse
NEXTAUTH_SECRET=your-nextauth-secret-here
SALT=your-salt-here
LANGFUSE_PUBLIC_KEY=pk-your-langfuse-public-key
LANGFUSE_SECRET_KEY=sk-your-langfuse-secret-key
LANGFUSE_PORT=3000

# Postgres
POSTGRES_DB=langfuse
POSTGRES_USER=langfuse
POSTGRES_PASSWORD=your-postgres-password

# ClickHouse
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=your-clickhouse-password

# Redis
# No custom env needed (uses defaults)

# MinIO
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=your-minio-password

# LiteLLM
LITELLM_PORT=4000

# Ollama (host-side, referenced via host-gateway)
# Ensure OLLAMA_NUM_PARALLEL=1 on host
```

## 5. Startup sequence

1. Copy `.env.example` to `.env` and populate all secrets/passwords.  
2. `mkdir -p docker && cp clickhouse-config.xml docker/ && cp litellm-config.yaml docker/`.  
3. `docker compose -f docker/langfuse-compose.yml up -d postgres redis minio clickhouse`.  
4. `docker compose -f docker/langfuse-compose.yml up -d minio-init`.  
5. Verify: `docker compose -f docker/langfuse-compose.yml ps` (all healthy) and check ClickHouse with `docker exec langfuse-clickhouse clickhouse-client --query 'SELECT 1'`.  
6. `docker compose -f docker/langfuse-compose.yml up -d langfuse-worker langfuse-web`.  
7. Verify Langfuse: `curl -I http://localhost:3000` (expect 200) and browse to http://localhost:3000.  
8. `docker compose -f docker/langfuse-compose.yml up -d litellm-gateway`.  
9. Test LiteLLM: `curl http://localhost:4000/health` and confirm models via `/v1/models`.  
10. (Optional) Pull Ollama models on host: `ollama pull qwen2.5:0.5b && ollama pull phi3:mini`.
```