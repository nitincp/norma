"""
Langfuse connectivity & feature test suite.

Run from repo root:
    python scripts/test_langfuse.py
"""

import sys
import time
import uuid

import httpx
from norma import settings  # noqa: F401 — triggers load_dotenv

from langfuse import Langfuse

HOST = settings.LANGFUSE_HOST
PK = settings.LANGFUSE_PUBLIC_KEY
SK = settings.LANGFUSE_SECRET_KEY

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
SKIP = "\033[33mSKIP\033[0m"


def check(label: str, fn):
    try:
        result = fn()
        print(f"  {PASS}  {label}" + (f" — {result}" if result else ""))
        return True
    except Exception as exc:
        print(f"  {FAIL}  {label} — {exc}")
        return False


# ── 1. HTTP health ─────────────────────────────────────────────────────────────
print("\n[1] HTTP health")
check(
    "GET /api/public/health → status OK",
    lambda: (
        r := httpx.get(f"{HOST}/api/public/health", timeout=5),
        r.raise_for_status(),
        r.json()["status"],
    )[-1],
)
check(
    "Langfuse version visible",
    lambda: (
        r := httpx.get(f"{HOST}/api/public/health", timeout=5),
        r.json().get("version", "unknown"),
    )[-1],
)

# ── 2. Authentication ──────────────────────────────────────────────────────────
print("\n[2] Authentication")
lf = Langfuse(public_key=PK, secret_key=SK, host=HOST)

auth_ok = check("SDK auth_check() → True", lambda: (lf.auth_check() or (_ for _ in ()).throw(AssertionError("auth failed"))))

check(
    "REST GET /api/public/projects → project listed",
    lambda: (
        r := httpx.get(f"{HOST}/api/public/projects", auth=(PK, SK), timeout=5),
        r.raise_for_status(),
        f"{len(r.json()['data'])} project(s): {[p['name'] for p in r.json()['data']]}",
    )[-1],
)

if not auth_ok:
    print(f"\n  {SKIP}  Auth failed — skipping all remaining tests")
    sys.exit(1)

# ── 3. Trace & span ingestion ──────────────────────────────────────────────────
print("\n[3] Trace & span ingestion")
trace_id = lf.create_trace_id()

check(
    "create_trace_id() returns UUID-like string",
    lambda: trace_id if len(trace_id) == 32 or "-" in trace_id else (_ for _ in ()).throw(ValueError(trace_id)),
)


def _ingest_trace():
    with lf.start_as_current_observation(name="test-trace") as span:
        span.update(
            input={"prompt": "connectivity check"},
            output={"answer": "ok"},
            metadata={"source": "test_langfuse.py"},
        )
    lf.flush()
    return "flushed"


check("start_as_current_observation + flush()", _ingest_trace)


def _ingest_nested():
    with lf.start_as_current_observation(name="parent-span") as parent:
        parent.update(input={"level": "parent"})
        with lf.start_as_current_observation(name="child-span") as child:
            child.update(input={"level": "child"}, output={"result": "nested ok"})
    lf.flush()
    return "nested flushed"


check("nested spans (parent → child)", _ingest_nested)

# ── 4. Score ingestion ────────────────────────────────────────────────────────
print("\n[4] Score ingestion")

def _score_trace():
    tid = lf.create_trace_id()
    with lf.start_as_current_observation(name="scored-trace"):
        pass
    lf.score_current_trace(name="quality", value=0.9, comment="automated test")
    lf.flush()
    return f"trace {tid[:8]}… scored"


check("score_current_trace()", _score_trace)

# ── 5. Dataset operations ─────────────────────────────────────────────────────
print("\n[5] Dataset operations")
dataset_name = f"test-dataset-{uuid.uuid4().hex[:6]}"


def _create_dataset():
    lf.create_dataset(name=dataset_name, description="connectivity test dataset")
    return dataset_name


check("create_dataset()", _create_dataset)


def _create_dataset_item():
    lf.create_dataset_item(
        dataset_name=dataset_name,
        input={"question": "what is 2+2?"},
        expected_output={"answer": "4"},
        metadata={"tag": "arithmetic"},
    )
    return "item created"


check("create_dataset_item()", _create_dataset_item)


def _read_dataset():
    ds = lf.get_dataset(dataset_name)
    return f"{len(ds.items)} item(s)"


check("get_dataset() → items visible", _read_dataset)

# ── 6. Prompt management ──────────────────────────────────────────────────────
print("\n[6] Prompt management")
prompt_name = f"test-prompt-{uuid.uuid4().hex[:6]}"


def _create_prompt():
    lf.create_prompt(
        name=prompt_name,
        prompt="You are a helpful assistant. Answer: {{question}}",
        labels=["production"],  # get_prompt() fetches label=production by default
        config={"temperature": 0.7},
    )
    return prompt_name


check("create_prompt()", _create_prompt)


def _get_prompt():
    p = lf.get_prompt(prompt_name)
    return f"version={p.version}"


check("get_prompt() → version visible", _get_prompt)

# ── 7. REST ingestion endpoint ────────────────────────────────────────────────
print("\n[7] REST ingestion (batch)")


def _rest_batch_ingest():
    event_id = uuid.uuid4().hex
    payload = {
        "batch": [
            {
                "id": event_id,
                "type": "trace-create",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "body": {
                    "id": event_id,
                    "name": "rest-batch-test",
                    "input": {"raw": True},
                },
            }
        ]
    }
    r = httpx.post(
        f"{HOST}/api/public/ingestion",
        json=payload,
        auth=(PK, SK),
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    successes = len(data.get("successes", []))
    errors = data.get("errors", [])
    if errors:
        raise AssertionError(f"batch errors: {errors}")
    return f"{successes} event(s) accepted"


check("POST /api/public/ingestion batch", _rest_batch_ingest)

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\nLangfuse host: {HOST}")
print(f"Project: {PK}\n")
