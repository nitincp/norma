# Norma Stack Setup

## 1. docker/langfuse-compose.yml

```yaml
version: '3.8'

networks:
  norma-net:
    name: norma-net
    driver: bridge

volumes:
  postgres_data:
  clickhouse_data:
  redis_data:
  minio_data:

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
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 5

  langfuse-clickhouse:
    image: clickhouse/clickhouse-server:24.3
    container_name: langfuse-clickhouse
    networks:
      - norma-net
    environment:
      CLICKHOUSE_DB: ${CLICKHOUSE_DB}
      CLICKHOUSE_USER: ${CLICKHOUSE_USER}
      CLICKHOUSE_PASSWORD: ${CLICKHOUSE_PASSWORD}
    volumes:
      - clickhouse_data:/var/lib/clickhouse
      - ./clickhouse-config.xml:/etc/clickhouse-server/config.d/norma.xml:ro
    healthcheck:
      test: ["CMD-SHELL", "clickhouse-client --query 'SELECT 1'"]
      interval: 5s
      timeout: 5s
      retries: 5

  langfuse-redis:
    image: redis:7-alpine
    container_name: langfuse-redis
    networks:
      - norma-net
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  langfuse-minio:
    image: minio/minio:RELEASE.2024-03-07T00-43-48Z
    container_name: langfuse-minio
    networks:
      - norma-net
    ports:
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes:
      - minio_data:/data
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 5s
      timeout: 5s
      retries: 5

  minio-init:
    image: minio/mc:RELEASE.2024-03-05T23-01-38Z
    container_name: minio-init
    networks:
      - norma-net
    depends_on:
      langfuse-minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
      mc alias set local http://langfuse-minio:9000 ${MINIO_ROOT_USER} ${MINIO_ROOT_PASSWORD};
      mc mb --ignore-existing local/${MINIO_BUCKET_NAME};
      exit 0;
      "

  langfuse-worker:
    image: langfuse/langfuse-worker:3
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
        condition: service_completed_successfully
    environment:
      NODE_ENV: production
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@langfuse-postgres:5432/${POSTGRES_DB}
      CLICKHOUSE_MIGRATION_URL: clickhouse://${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}@langfuse-clickhouse:9000/${CLICKHOUSE_DB}
      CLICKHOUSE_URL: http://${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}@langfuse-clickhouse:8123/${CLICKHOUSE_DB}
      CLICKHOUSE_CLUSTER_ENABLED: "false"
      REDIS_HOST: langfuse-redis
      REDIS_PORT: 6379
      LANGFUSE_S3_BATCH_EXPORT_ENABLED: "false"
      LANGFUSE_S3_MEDIA_UPLOAD_BUCKET: ${MINIO_BUCKET_NAME}
      LANGFUSE_S3_MEDIA_UPLOAD_PREFIX: media/
      LANGFUSE_S3_MEDIA_UPLOAD_SECRET_KEY: ${MINIO_ROOT_PASSWORD}
      LANGFUSE_S3_MEDIA_UPLOAD_ACCESS_KEY_ID: ${MINIO_ROOT_USER}
      LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT: http://langfuse-minio:9000
      LANGFUSE_S3_MEDIA_UPLOAD_FORCE_PATH_STYLE: "true"
      LANGFUSE_S3_MEDIA_UPLOAD_REGION: us-east-1
      SALT: ${SALT}
      TELEMETRY_ENABLED: "false"

  langfuse-web:
    image: langfuse/langfuse:3
    container_name: langfuse-web
    networks:
      - norma-net
    ports:
      - "3000:3000"
    depends_on:
      langfuse-postgres:
        condition: service_healthy
      langfuse-clickhouse:
        condition: service_healthy
      langfuse-redis:
        condition: service_healthy
      minio-init:
        condition: service_completed_successfully
    environment:
      NODE_ENV: production
      NEXTAUTH_URL: http://localhost:3000
      NEXTAUTH_SECRET: ${NEXTAUTH_SECRET}
      SALT: ${SALT}
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@langfuse-postgres:5432/${POSTGRES_DB}
      CLICKHOUSE_MIGRATION_URL: clickhouse://${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}@langfuse-clickhouse:9000/${CLICKHOUSE_DB}
      CLICKHOUSE_URL: http://${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}@langfuse-clickhouse:8123/${CLICKHOUSE_DB}
      CLICKHOUSE_CLUSTER_ENABLED: "false"
      REDIS_HOST: langfuse-redis
      REDIS_PORT: 6379
      LANGFUSE_S3_BATCH_EXPORT_ENABLED: "false"
      LANGFUSE_S3_MEDIA_UPLOAD_BUCKET: ${MINIO_BUCKET_NAME}
      LANGFUSE_S3_MEDIA_UPLOAD_PREFIX: media/
      LANGFUSE_S3_MEDIA_UPLOAD_SECRET_KEY: ${MINIO_ROOT_PASSWORD}
      LANGFUSE_S3_MEDIA_UPLOAD_ACCESS_KEY_ID: ${MINIO_ROOT_USER}
      LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT: http://langfuse-minio:9000
      LANGFUSE_S3_MEDIA_UPLOAD_FORCE_PATH_STYLE: "true"
      LANGFUSE_S3_MEDIA_UPLOAD_REGION: us-east-1
      TELEMETRY_ENABLED: "false"
      LANGFUSE_INIT_ORG_ID: ${LANGFUSE_INIT_ORG_ID}
      LANGFUSE_INIT_ORG_NAME: ${LANGFUSE_INIT_ORG_NAME}
      LANGFUSE_INIT_PROJECT_ID: ${LANGFUSE_INIT_PROJECT_ID}
      LANGFUSE_INIT_PROJECT_NAME: ${LANGFUSE_INIT_PROJECT_NAME}
      LANGFUSE_INIT_PROJECT_PUBLIC_KEY: ${LANGFUSE_PUBLIC_KEY}
      LANGFUSE_INIT_PROJECT_SECRET_KEY: ${LANGFUSE_SECRET_KEY}
      LANGFUSE_INIT_USER_EMAIL: ${LANGFUSE_INIT_USER_EMAIL}
      LANGFUSE_INIT_USER_PASSWORD: ${LANGFUSE_INIT_USER_PASSWORD}
    healthcheck:
      test: ["CMD-SHELL", "wget --no-verbose --tries=1 --spider http://localhost:3000/api/health || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5

  litellm-gateway:
    image: ghcr.io/berriai/litellm:main-stable
    container_name: litellm-gateway
    networks:
      - norma-net
    ports:
      - "4000:4000"
    extra_hosts:
      - "host-gateway:host-gateway"
    volumes:
      - ./litellm-config.yaml:/app/config.yaml:ro
    environment:
      LANGFUSE_PUBLIC_KEY: ${LANGFUSE_PUBLIC_KEY}
      LANGFUSE_SECRET_KEY: ${LANGFUSE_SECRET_KEY}
      LANGFUSE_HOST: http://langfuse-web:3000
    command: ["--config", "/app/config.yaml", "--port", "4000"]
    healthcheck:
      test: ["CMD-SHELL", "wget --no-verbose --tries=1 --spider http://localhost:4000/health/liveliness || exit 1"]
      interval: 5s
      timeout: 5s
      retries: 5

```

---

## 2. docker/clickhouse-config.xml

```xml
<clickhouse>
    <listen_host>0.0.0.0</listen_host>

    <logger>
        <level>warning</level>
    </logger>

    <max_server_memory_usage_to_ram_ratio>0.50</max_server_memory_usage_to_ram_ratio>

    <background_pool_size>16</background_pool_size>
    <background_merges_mutations_concurrency_ratio>2</background_merges_mutations_concurrency_ratio>

    <number_of_free_entries_in_pool_to_execute_mutation>31</number_of_free_entries_in_pool_to_execute_mutation>

    <mark_cache_size>134217728</mark_cache_size>
    <uncompressed_cache_size>134217728</uncompressed_cache_size>

    <send_crash_reports>
        <enabled>false</enabled>
    </send_crash_reports>

    <interserver_http_port remove="remove"/>

    <query_log remove="remove"/>
    <text_log remove="remove"/>
    <trace_log remove="remove"/>
    <metric_log remove="remove"/>
    <asynchronous_metric_log remove="remove"/>
    <session_log remove="remove"/>
    <part_log remove="remove"/>
</clickhouse>

```

---

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

```

> **Note on LiteLLM Environment Variables:** LiteLLM natively hooks into Langfuse using OpenTelemetry via the `langfuse_otel` callback, which evaluates `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_HOST` dynamically out of its runtime environment variables to direct asynchronous tracking batches.

---

## 4. .env.example

```env
# Generate secrets with: openssl rand -hex 32

# Langfuse Configuration
SALT=placeholder_salt_value_min_32_chars
NEXTAUTH_SECRET=placeholder_nextauth_secret_value
LANGFUSE_INIT_ORG_ID=org_norma_init_id
LANGFUSE_INIT_ORG_NAME="Norma Organization"
LANGFUSE_INIT_PROJECT_ID=proj_norma_init_id
LANGFUSE_INIT_PROJECT_NAME="Norma Core"
LANGFUSE_INIT_USER_EMAIL=admin@norma.local
LANGFUSE_INIT_USER_PASSWORD=ChangeThisSecurePassword123!

# Postgres Configuration
POSTGRES_DB=langfuse
POSTGRES_USER=postgres
POSTGRES_PASSWORD=placeholder_secure_postgres_password

# ClickHouse Configuration
CLICKHOUSE_DB=langfuse
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=placeholder_secure_clickhouse_password

# Redis Configuration
# No authentication variables required for internal container-to-container communication

# MinIO Configuration
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=placeholder_secure_minio_password
MINIO_BUCKET_NAME=langfuse-media

# LiteLLM Configuration
LANGFUSE_PUBLIC_KEY=pk-lf-placeholderkey
LANGFUSE_SECRET_KEY=sk-lf-placeholderkey

# Ollama Configuration
OLLAMA_NUM_PARALLEL=1

```

---

## 5. Startup sequence

1. **Prepare configuration artifacts**: Run `cp .env.example .env` and populate all placeholders with actual generated values.
2. **Create persistent storage layers**: Execute `docker volume create postgres_data && docker volume create clickhouse_data && docker volume create redis_data && docker volume create minio_data` to decouple persistence from execution contexts.
3. **Bring up foundational datastores**: Run `docker compose up -d langfuse-postgres langfuse-clickhouse langfuse-redis langfuse-minio` to start basic infrastructures.
4. **Verify datastore system readineess**: Monitor container signals via `docker compose ps` until all database health checks indicate `healthy`.
5. **Initialize media object-storage engine**: Trigger `docker compose up minio-init` to map and instantiate the mandatory internal Langfuse media bucket.
6. **Deploy analytical tracking engine**: Run `docker compose up -d langfuse-worker langfuse-web` to spin up core background processors and application servers.
7. **Verify tracking service availability**: Confirm `langfuse-web` is operational by ensuring its status reports `healthy` or execution of `curl -I http://localhost:3000/api/health` yields a valid `200 OK` structure.
8. **Initialize upstream gateway router**: Execute `docker compose up -d litellm-gateway` to bind routes onto host port 4000.
9. **Verify total runtime integrity**: Execute `curl -I http://localhost:4000/health/liveliness` to affirm telemetry bindings to Ollama are live and responsive.