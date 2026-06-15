# ClickHouse Config Variants — Test Session Prompt

Use this prompt in a fresh session to systematically test ClickHouse configuration variants
against the working baseline, with the goal of finding the lowest memory/CPU footprint that
stays stable under Langfuse v3 workloads.

---

## System Prompt

> **Context — working baseline (do not change these):**
> - Stack: Langfuse v3 self-hosted, single-node ClickHouse `24.3-alpine`, Docker 29.5.3, kernel 6.8.0
> - Host: CPU-only VM, ~8 GB RAM shared with Ollama and other containers
> - ClickHouse container has **no** `user:` override, **no** `deploy.resources` limits
> - ClickHouse healthcheck: `clickhouse-client --query 'SELECT 1'`
> - Custom config mounted at: `./clickhouse-config.xml:/etc/clickhouse-server/config.d/norma.xml:ro`
> - Compose file: `docker/langfuse-compose.yml`, env file: `.env`
> - Start command: `docker compose -f docker/langfuse-compose.yml --env-file .env up -d`
> - Verify command: `docker compose -f docker/langfuse-compose.yml ps` — ClickHouse must show `(healthy)`
>
> **Goal:** Test the configs below one at a time. For each variant:
> 1. Write the XML to `docker/clickhouse-config.xml`
> 2. Run `docker compose -f docker/langfuse-compose.yml --env-file .env restart langfuse-clickhouse`
> 3. Wait 15s then check: `docker compose -f docker/langfuse-compose.yml ps | grep clickhouse`
> 4. If healthy, send a test trace: `curl -s -X POST http://localhost:4000/v1/chat/completions -H "Content-Type: application/json" -H "Authorization: Bearer $LITELLM_MASTER_KEY" -d '{"model":"local/qwen2.5-0.5b","messages":[{"role":"user","content":"ping"}],"max_tokens":5}'`
> 5. Confirm trace appears in Langfuse UI at `http://localhost:3000`
> 6. Record result: healthy / unhealthy / trace visible
>
> Test each variant in order. Stop at the first one that fails and report the last healthy config.

---

## Variant 0 — Baseline (no custom config, currently working)

Remove `clickhouse-config.xml` mount from compose and restart. Confirms ClickHouse works
with zero customisation. Reference point for memory usage.

```xml
<!-- No file — remove the volume mount line from langfuse-compose.yml for this test -->
```

Check memory: `docker stats docker-langfuse-clickhouse-1 --no-stream`

---

## Variant 1 — Norma original (was failing — retest now that user/limits removed)

The config we built before removing `user:` and `deploy.resources`. Now that those are gone,
test if the config itself was ever the problem or if it's safe to restore.

```xml
<clickhouse>
    <max_server_memory_usage_to_ram_ratio>0.5</max_server_memory_usage_to_ram_ratio>
    <mark_cache_size>268435456</mark_cache_size>
    <index_mark_cache_size>67108864</index_mark_cache_size>
    <uncompressed_cache_size>16777216</uncompressed_cache_size>
    <background_pool_size>2</background_pool_size>
    <background_merges_mutations_concurrency_ratio>2</background_merges_mutations_concurrency_ratio>
    <merge_tree>
        <number_of_free_entries_in_pool_to_execute_mutation>2</number_of_free_entries_in_pool_to_execute_mutation>
        <number_of_free_entries_in_pool_to_lower_max_size_of_merge>2</number_of_free_entries_in_pool_to_lower_max_size_of_merge>
        <number_of_free_entries_in_pool_to_execute_optimize_entire_partition>2</number_of_free_entries_in_pool_to_execute_optimize_entire_partition>
    </merge_tree>
    <max_concurrent_queries>16</max_concurrent_queries>
    <max_thread_pool_size>500</max_thread_pool_size>
    <listen_host>0.0.0.0</listen_host>
    <interserver_http_port remove="1"/>
    <query_log remove="1"/>
    <text_log remove="1"/>
    <trace_log remove="1"/>
    <metric_log remove="1"/>
    <asynchronous_metric_log remove="1"/>
    <session_log remove="1"/>
    <part_log remove="1"/>
    <send_crash_reports><enabled>false</enabled></send_crash_reports>
    <logger><level>warning</level></logger>
</clickhouse>
```

---

## Variant 2 — Claude.ai suggestion (aggressive pool reduction)

From the Claude research response. Uses very low `background_merges_mutations_concurrency_ratio`
(0.25) which is unusual — may cause issues. Worth testing to see if it boots.

```xml
<clickhouse>
    <listen_host>0.0.0.0</listen_host>
    <max_server_memory_usage_to_ram_ratio>0.5</max_server_memory_usage_to_ram_ratio>
    <mark_cache_size>128000000</mark_cache_size>
    <uncompressed_cache_size>268435456</uncompressed_cache_size>
    <background_pool_size>2</background_pool_size>
    <background_merges_mutations_concurrency_ratio>0.25</background_merges_mutations_concurrency_ratio>
    <query_log remove="1"/>
    <text_log remove="1"/>
    <trace_log remove="1"/>
    <metric_log remove="1"/>
    <asynchronous_metric_log remove="1"/>
    <session_log remove="1"/>
    <part_log remove="1"/>
    <send_crash_reports><enabled>0</enabled></send_crash_reports>
    <interserver_http_port/>
    <logger>
        <level>warning</level>
        <log>/var/log/clickhouse-server/clickhouse-server.log</log>
        <errorlog>/var/log/clickhouse-server/clickhouse-server.err.log</errorlog>
    </logger>
</clickhouse>
```

---

## Variant 3 — Gemini suggestion (high pool, explicit mutation threshold)

From Gemini research. Uses `background_pool_size=16` with `ratio=2` and explicit
`number_of_free_entries_in_pool_to_execute_mutation=31`. Higher than needed for our workload
but follows ClickHouse defaults more closely.

```xml
<clickhouse>
    <listen_host>0.0.0.0</listen_host>
    <logger><level>warning</level></logger>
    <max_server_memory_usage_to_ram_ratio>0.50</max_server_memory_usage_to_ram_ratio>
    <background_pool_size>16</background_pool_size>
    <background_merges_mutations_concurrency_ratio>2</background_merges_mutations_concurrency_ratio>
    <number_of_free_entries_in_pool_to_execute_mutation>31</number_of_free_entries_in_pool_to_execute_mutation>
    <mark_cache_size>134217728</mark_cache_size>
    <uncompressed_cache_size>134217728</uncompressed_cache_size>
    <send_crash_reports><enabled>false</enabled></send_crash_reports>
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

## Variant 4 — Grok suggestion (balanced, explicit mutation threshold)

From Grok research. `pool_size=18`, `ratio=2`, `mutation_threshold=16`. Satisfies sanity check
with headroom (16 < 36). More conservative than Gemini but still higher than our Variant 1.

```xml
<clickhouse>
    <listen_host>0.0.0.0</listen_host>
    <max_server_memory_usage_to_ram_ratio>0.5</max_server_memory_usage_to_ram_ratio>
    <mark_cache_size>536870912</mark_cache_size>
    <uncompressed_cache_size>134217728</uncompressed_cache_size>
    <logger><level>warning</level></logger>
    <background_pool_size>18</background_pool_size>
    <background_merges_mutations_concurrency_ratio>2</background_merges_mutations_concurrency_ratio>
    <number_of_free_entries_in_pool_to_execute_mutation>16</number_of_free_entries_in_pool_to_execute_mutation>
    <send_crash_reports>false</send_crash_reports>
    <interserver_http_port>0</interserver_http_port>
    <query_log><enabled>false</enabled></query_log>
    <text_log><enabled>false</enabled></text_log>
    <trace_log><enabled>false</enabled></trace_log>
    <metric_log><enabled>false</enabled></metric_log>
    <asynchronous_metric_log><enabled>false</enabled></asynchronous_metric_log>
    <session_log><enabled>false</enabled></session_log>
    <part_log><enabled>false</enabled></part_log>
</clickhouse>
```

---

## Variant 5 — Minimal memory target (goal config)

Target: lowest stable memory footprint for Langfuse v3 dev workload. Aggressively reduced
caches. If this works, it becomes the permanent `norma.xml`.

```xml
<clickhouse>
    <listen_host>0.0.0.0</listen_host>
    <max_server_memory_usage_to_ram_ratio>0.3</max_server_memory_usage_to_ram_ratio>
    <mark_cache_size>67108864</mark_cache_size>
    <index_mark_cache_size>16777216</index_mark_cache_size>
    <uncompressed_cache_size>8388608</uncompressed_cache_size>
    <background_pool_size>2</background_pool_size>
    <background_merges_mutations_concurrency_ratio>2</background_merges_mutations_concurrency_ratio>
    <merge_tree>
        <number_of_free_entries_in_pool_to_execute_mutation>1</number_of_free_entries_in_pool_to_execute_mutation>
        <number_of_free_entries_in_pool_to_lower_max_size_of_merge>1</number_of_free_entries_in_pool_to_lower_max_size_of_merge>
    </merge_tree>
    <max_concurrent_queries>8</max_concurrent_queries>
    <max_thread_pool_size>100</max_thread_pool_size>
    <interserver_http_port remove="1"/>
    <query_log remove="1"/>
    <text_log remove="1"/>
    <trace_log remove="1"/>
    <metric_log remove="1"/>
    <asynchronous_metric_log remove="1"/>
    <session_log remove="1"/>
    <part_log remove="1"/>
    <send_crash_reports><enabled>false</enabled></send_crash_reports>
    <logger><level>warning</level></logger>
</clickhouse>
```

---

## Result table (fill in during testing)

| Variant | Config | Healthy? | Trace visible? | Memory (docker stats) | Notes |
|---------|--------|----------|----------------|----------------------|-------|
| 0 | No config (baseline) | | | | |
| 1 | Norma original | | | | |
| 2 | Claude.ai (ratio=0.25) | | | | |
| 3 | Gemini (pool=16) | | | | |
| 4 | Grok (pool=18) | | | | |
| 5 | Minimal memory target | | | | |

---

## After testing — restore working config

Once the best variant is identified, save it as `docker/clickhouse-config.xml`, restore the
volume mount in `langfuse-compose.yml`, and commit:

```bash
git add docker/clickhouse-config.xml docker/langfuse-compose.yml
git commit -m "chore: tune ClickHouse config to minimum stable footprint"
```
