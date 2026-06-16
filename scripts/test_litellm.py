"""
LiteLLM gateway connectivity & feature test suite.

Run from repo root:
    python scripts/test_litellm.py
"""

import sys

import httpx
from norma import settings  # noqa: F401 — triggers load_dotenv

BASE = settings.LITELLM_BASE_URL
KEY = settings.LITELLM_MASTER_KEY

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
SKIP = "\033[33mSKIP\033[0m"

_auth = {"Authorization": f"Bearer {KEY}"}


def check(label: str, fn):
    try:
        result = fn()
        print(f"  {PASS}  {label}" + (f" — {result}" if result else ""))
        return True
    except Exception as exc:
        print(f"  {FAIL}  {label} — {exc}")
        return False


# ── 1. Unauthenticated health ──────────────────────────────────────────────────
print("\n[1] Unauthenticated endpoints")
check(
    "GET /health/liveliness → 200",
    lambda: (
        r := httpx.get(f"{BASE}/health/liveliness", timeout=5),
        r.raise_for_status(),
        r.text.strip()[:60],
    )[-1],
)

# ── 2. Authenticated endpoints ─────────────────────────────────────────────────
print("\n[2] Authenticated endpoints")
key_ok = check(
    "GET /health → healthy_endpoints listed",
    lambda: (
        r := httpx.get(f"{BASE}/health", headers=_auth, timeout=60),
        r.raise_for_status(),
        f"{len(r.json().get('healthy_endpoints', []))} healthy, "
        f"{len(r.json().get('unhealthy_endpoints', []))} unhealthy",
    )[-1],
)

if not key_ok:
    print(f"\n  {SKIP}  Auth failed — check LITELLM_MASTER_KEY in .env")
    sys.exit(1)

models_ok = check(
    "GET /v1/models → model list",
    lambda: (
        r := httpx.get(f"{BASE}/v1/models", headers=_auth, timeout=5),
        r.raise_for_status(),
        [m["id"] for m in r.json()["data"]],
    )[-1],
)

# Collect available model IDs for downstream tests
_models_resp = httpx.get(f"{BASE}/v1/models", headers=_auth, timeout=5)
available_models: list[str] = (
    [m["id"] for m in _models_resp.json().get("data", [])] if _models_resp.is_success else []
)

# ── 3. Chat completions ────────────────────────────────────────────────────────
print("\n[3] Chat completions")

# Find a local model to test with (avoids spending cloud credits)
local_models = [m for m in available_models if m.startswith("local/")]
test_model = local_models[0] if local_models else (available_models[0] if available_models else None)

if not test_model:
    print(f"  {SKIP}  No models available — skipping completion tests")
else:
    print(f"  (using model: {test_model})")

    def _basic_completion():
        r = httpx.post(
            f"{BASE}/v1/chat/completions",
            headers=_auth,
            json={
                "model": test_model,
                "messages": [{"role": "user", "content": "Reply with just the word PONG"}],
                "max_tokens": 10,
                "temperature": 0,
            },
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"].strip()
        tokens = data["usage"]["total_tokens"]
        return f"reply={content!r} tokens={tokens}"

    check("POST /v1/chat/completions (non-streaming)", _basic_completion)

    def _streaming_completion():
        chunks = []
        with httpx.stream(
            "POST",
            f"{BASE}/v1/chat/completions",
            headers=_auth,
            json={
                "model": test_model,
                "messages": [{"role": "user", "content": "Count to 3, one number per line"}],
                "max_tokens": 20,
                "stream": True,
            },
            timeout=30,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    import json
                    chunk = json.loads(line[6:])
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if delta:
                        chunks.append(delta)
        return f"{len(chunks)} chunk(s), content={repr(''.join(chunks))[:40]}"

    check("POST /v1/chat/completions (streaming SSE)", _streaming_completion)

    def _system_prompt():
        r = httpx.post(
            f"{BASE}/v1/chat/completions",
            headers=_auth,
            json={
                "model": test_model,
                "messages": [
                    {"role": "system", "content": "You only reply with JSON objects."},
                    {"role": "user", "content": 'Return {"status": "ok"}'},
                ],
                "max_tokens": 20,
                "temperature": 0,
            },
            timeout=30,
        )
        r.raise_for_status()
        return repr(r.json()["choices"][0]["message"]["content"].strip()[:40])

    check("system + user message roles", _system_prompt)

    def _multi_turn():
        r = httpx.post(
            f"{BASE}/v1/chat/completions",
            headers=_auth,
            json={
                "model": test_model,
                "messages": [
                    {"role": "user", "content": "My name is Alice."},
                    {"role": "assistant", "content": "Hello Alice!"},
                    {"role": "user", "content": "What is my name?"},
                ],
                "max_tokens": 20,
            },
            timeout=30,
        )
        r.raise_for_status()
        return repr(r.json()["choices"][0]["message"]["content"].strip()[:40])

    check("multi-turn conversation history", _multi_turn)

# ── 4. Error handling ──────────────────────────────────────────────────────────
print("\n[4] Error handling")


def _bad_model_error():
    r = httpx.post(
        f"{BASE}/v1/chat/completions",
        headers=_auth,
        json={
            "model": "nonexistent/model-xyz",
            "messages": [{"role": "user", "content": "hi"}],
        },
        timeout=10,
    )
    if r.status_code in (400, 404, 422, 500):
        return f"correctly returned HTTP {r.status_code}"
    raise AssertionError(f"expected 4xx/5xx, got {r.status_code}: {r.text[:80]}")


check("unknown model → 4xx/5xx error", _bad_model_error)


def _no_auth_error():
    r = httpx.get(f"{BASE}/v1/models", timeout=5)
    if r.status_code == 401:
        return "correctly returned HTTP 401"
    raise AssertionError(f"expected 401, got {r.status_code}")


check("missing auth header → 401", _no_auth_error)


def _bad_key_error():
    r = httpx.get(
        f"{BASE}/v1/models",
        headers={"Authorization": "Bearer sk-totally-wrong"},
        timeout=5,
    )
    # LiteLLM returns 400 for unrecognised keys (not standard 401)
    if r.status_code in (400, 401, 403):
        return f"correctly returned HTTP {r.status_code}"
    raise AssertionError(f"expected 400/401/403, got {r.status_code}")


check("wrong API key → 401/403", _bad_key_error)

# ── 5. Langfuse trace passthrough (if configured) ─────────────────────────────
print("\n[5] Langfuse trace via LiteLLM metadata")

if test_model:
    def _langfuse_metadata():
        r = httpx.post(
            f"{BASE}/v1/chat/completions",
            headers=_auth,
            json={
                "model": test_model,
                "messages": [{"role": "user", "content": "Say hello"}],
                "max_tokens": 10,
                "metadata": {
                    "trace_name": "litellm-connectivity-test",
                    "tags": ["test", "connectivity"],
                },
            },
            timeout=30,
        )
        r.raise_for_status()
        return f"response_id={r.json().get('id', 'n/a')[:20]}"

    check("completion with Langfuse metadata passthrough", _langfuse_metadata)
else:
    print(f"  {SKIP}  No model available")

# ── 6. Model-level health ──────────────────────────────────────────────────────
print("\n[6] Per-model health")


def _model_health():
    r = httpx.get(f"{BASE}/health", headers=_auth, timeout=60)
    r.raise_for_status()
    data = r.json()
    lines = []
    for ep in data.get("healthy_endpoints", []):
        lines.append(f"  HEALTHY  {ep['model']}")
    for ep in data.get("unhealthy_endpoints", []):
        err = ep.get("error", "")[:60]
        lines.append(f"  UNHEALTHY {ep['model']} — {err}")
    return "\n" + "\n".join(lines)


check("GET /health → per-model status", _model_health)

# ── Summary ────────────────────────────────────────────────────────────────────
print(f"\nLiteLLM gateway: {BASE}")
print(f"Available models: {available_models}\n")
