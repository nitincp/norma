---
source: ⚠️ Jupyter Notebook
title: Observability for Anthropic with Langfuse Integration
sidebarTitle: Anthropic (Python)
logo: /images/integrations/anthropic_icon.png
description: Learn how to integrate Langfuse with Anthropic for comprehensive tracing and debugging of your AI conversations.
category: Integrations
---

# Trace Anthropic Models in Langfuse

<a href="https://langfuse.com/integrations/model-providers/anthropic"><img className="inline" alt="Python" src="https://img.shields.io/badge/Python-d4d4d8?style=flat&logo=python&logoColor=white" /></a> <a href="https://langfuse.com/integrations/model-providers/anthropic-js"><img className="inline" alt="JS/TS" src="https://img.shields.io/badge/JS/TS-F7DF1E?style=flat&logo=javascript&logoColor=black" /></a>

Anthropic provides advanced language models like Claude, known for their safety, helpfulness, and strong reasoning capabilities. By combining Anthropic's models with **Langfuse**, you can trace, monitor, and analyze your AI workloads in development and production.

This notebook demonstrates **two** different ways to use Anthropic models with Langfuse:
1. **OpenTelemetry Instrumentation:** Use the [`AnthropicInstrumentor`](https://pypi.org/project/opentelemetry-instrumentation-anthropic/) library to wrap Anthropic SDK calls and send OpenTelemetry spans to Langfuse.
2. **OpenAI SDK:** Use Anthropic's OpenAI-compatible endpoints via [Langfuse's OpenAI SDK wrapper](https://langfuse.com/integrations/model-providers/openai-py).

> **What is Anthropic?**\
Anthropic is an AI safety company that develops Claude, a family of large language models designed to be helpful, harmless, and honest. Claude models excel at complex reasoning, analysis, and creative tasks.

> **What is Langfuse?**\
[Langfuse](https://langfuse.com) is an open source platform for LLM observability and monitoring. It helps you trace and monitor your AI applications by capturing metadata, prompt details, token usage, latency, and more.

<Steps>
## Step 1: Install Dependencies

Before you begin, install the necessary packages in your Python environment:

```python
%pip install anthropic openai langfuse opentelemetry-instrumentation-anthropic
```

## Step 2: Configure Langfuse SDK

Next, set up your Langfuse API keys. You can get these keys by signing up for a free [Langfuse Cloud](https://langfuse.com/cloud) account or by [self-hosting Langfuse](https://langfuse.com/self-hosting). These environment variables are essential for the Langfuse client to authenticate and send data to your Langfuse project.

Also set your Anthropic API ([Anthropic Console](https://console.anthropic.com/)).

```python
import os

# Get keys for your project from the project settings page: https://cloud.langfuse.com
os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-lf-..." 
os.environ["LANGFUSE_SECRET_KEY"] = "sk-lf-..." 
os.environ["LANGFUSE_BASE_URL"] = "https://cloud.langfuse.com" # 🇪🇺 EU region
# Other Langfuse data regions include 🇺🇸 US: https://us.cloud.langfuse.com, 🇯🇵 Japan: https://jp.cloud.langfuse.com and ⚕️ HIPAA: https://hipaa.cloud.langfuse.com

os.environ["ANTHROPIC_API_KEY"] = "sk-ant-..."  # Your Anthropic API key
```

With the environment variables set, we can now initialize the Langfuse client. `get_client()` initializes the Langfuse client using the credentials provided in the environment variables.

```python
from langfuse import get_client

langfuse = get_client()
 
# Verify connection
if langfuse.auth_check():
    print("Langfuse client is authenticated and ready!")
else:
    print("Authentication failed. Please check your credentials and host.")
```

    Langfuse client is authenticated and ready!

## Approach 1: OpenTelemetry Instrumentation

Use the [`AnthropicInstrumentor`](https://pypi.org/project/opentelemetry-instrumentation-anthropic/) library to wrap Anthropic SDK calls and send OpenTelemetry spans to Langfuse.

```python
from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor

AnthropicInstrumentor().instrument()
```

```python
from anthropic import Anthropic

# Initialize the Anthropic client
client = Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY")
)

# Make the API call to Anthropic
message = client.messages.create(
    model="claude-opus-4-20250514",
    max_tokens=1000,
    temperature=1,
    system="You are a world-class poet. Respond only with short poems.",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Why is the ocean salty?"
                }
            ]
        }
    ]
)
print(message.content)
```

## Approach 2: OpenAI SDK Drop-in Replacement

Anthropic provides [OpenAI-compatible endpoints](https://docs.anthropic.com/en/api/openai-sdk) that allow you to use the OpenAI SDK to interact with Claude models. This is particularly useful if you have existing code using the OpenAI SDK that you want to switch to Claude.

```python
# Langfuse OpenAI client
from langfuse.openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("ANTHROPIC_API_KEY"),  # Your Anthropic API key
    base_url="https://api.anthropic.com/v1/"  # Anthropic's API endpoint
)

response = client.chat.completions.create(
    model="claude-opus-4-20250514", # Anthropic model name
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Who are you?"}
    ],
)

print(response.choices[0].message.content)
```

### View Traces in Langfuse

After executing the application, navigate to your Langfuse Trace Table. You will find detailed traces of the application's execution, providing insights into the agent conversations, LLM calls, inputs, outputs, and performance metrics. 

![Langfuse Trace](https://langfuse.com/images/cookbook/integration_anthropic/anthropic-example-trace.png)

You can also view the trace in Langfuse here: 

- [Approach 1: OpenTelemetry Instrumentation](https://cloud.langfuse.com/project/cloramnkj0002jz088vzn1ja4/traces/308aca9bc430ad872d474fc545889ee2?timestamp=2025-07-25T07:35:01.172Z&display=details)
- [Approach 2: OpenAI SDK](https://cloud.langfuse.com/project/cloramnkj0002jz088vzn1ja4/traces/8e8da1b2c15036ed9c25b37c604f2d29?timestamp=2025-07-22T16:05:47.602Z&display=details)

</Steps>

## Interoperability with the Python SDK

You can use this integration together with the Langfuse [SDKs](/docs/observability/sdk/overview) to add additional attributes to the observation.

<Tabs items={["Decorator", "Context Manager"]}>
<Tab>

The [`@observe()` decorator](/docs/observability/sdk/instrumentation#custom-instrumentation) provides a convenient way to automatically wrap your instrumented code and add additional attributes to the observation.

```python
from langfuse import observe, propagate_attributes, get_client

langfuse = get_client()

@observe()
def my_llm_pipeline(input):
    # Add additional attributes (user_id, session_id, metadata, version, tags) to all spans created within this execution scope
    with propagate_attributes(
        user_id="user_123",
        session_id="session_abc",
        tags=["agent", "my-observation"],
        metadata={"email": "user@langfuse.com"},
        version="1.0.0"
    ):

        # YOUR APPLICATION CODE HERE
        result = call_llm(input)

        return result

# Run the function
my_llm_pipeline("Hi")
```

Learn more about using the Decorator in the [Langfuse SDK instrumentation docs](/docs/observability/sdk/instrumentation#custom-instrumentation).

</Tab>
<Tab>

The [Context Manager](/docs/observability/sdk/instrumentation#custom-instrumentation) allows you to wrap your instrumented code using context managers (with `with` statements), which allows you to add additional attributes to the observation.

```python
from langfuse import get_client, propagate_attributes

langfuse = get_client()

with langfuse.start_as_current_observation(
    as_type="span",
    name="my-observation",
    trace_context={"trace_id": "abcdef1234567890abcdef1234567890"},  # Must be 32 hex chars
) as observation:

    # Add additional attributes (user_id, session_id, metadata, version, tags)
    # to all observations created within this execution scope
    with propagate_attributes(
        user_id="user_123",
        session_id="session_abc",
        metadata={"experiment": "variant_a", "env": "prod"},
        version="1.0",
    ):
        # YOUR APPLICATION CODE HERE
        result = call_llm("some input")

# Flush events in short-lived applications
langfuse.flush()
```

Learn more about using the Context Manager in the [Langfuse SDK instrumentation docs](/docs/observability/sdk/instrumentation#custom-instrumentation).

</Tab>
</Tabs>

## Troubleshooting

<details>
<summary>No observations appearing</summary>

First, enable [debug mode](/docs/observability/sdk/advanced-features#logging--debugging) in the Python SDK:

```bash
export LANGFUSE_DEBUG="True"
```

Then run your application and check the debug logs:

- **OTel observations appear in the logs:** Your application is instrumented correctly but observations are not reaching Langfuse. To resolve this:
  1. Call [`langfuse.flush()`](/docs/observability/sdk/instrumentation#client-lifecycle--flushing) at the end of your application to ensure all observations are exported.
  2. Verify that you are using the correct API keys and base URL.
- **No OTel spans in the logs:** Your application is not instrumented correctly. Make sure the instrumentation runs before your application code.

</details>

<details>
<summary>Unwanted observations in Langfuse</summary>

The Langfuse SDK is based on OpenTelemetry. Other libraries in your application may emit OTel spans that are not relevant to you. These still count toward your [billable units](/docs/administration/billable-units), so you should filter them out. See [Unwanted spans in Langfuse](/faq/all/unwanted-http-database-spans) for details.

</details>

<details>
<summary>Missing attributes</summary>

Some attributes may be stored in the metadata object of the observation rather than being mapped to the Langfuse data model. If a mapping or integration does not work as expected, please [raise an issue on GitHub](/issues).

</details>

## Next Steps

Once you have instrumented your code, you can manage, evaluate and debug your application:

<Cards num={2}> 
  <Cards.Card
    title="Manage prompts in Langfuse"
    href="/docs/prompts/get-started"
    icon={}
  />
  <Cards.Card
    title="Add evaluation scores"
    href="/docs/evaluation/features/evaluation-methods/custom-scores"
    icon={}
  />
  <Cards.Card
    title="Run LLM-as-a-judge Evaluators"
    href="/docs/scores/model-based-evals"
    icon={}
  />
  <Cards.Card
    title="Create datasets"
    href="/docs/datasets/overview"
    icon={}
  />
  <Cards.Card
    title="Create custom dashboards"
    href="/docs/analytics/custom-dashboards"
    icon={}
  />
  <Cards.Card
    title="Test queries in the Playground"
    href="/docs/playground"
    icon={}
  />
</Cards>

