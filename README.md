# OpenObserve Python SDK

A simple and lightweight Python SDK for exporting OpenTelemetry traces to [OpenObserve](https://openobserve.ai/).

## Quick Start

**Generate auth token:**
```bash
echo -n "root@example.com:Complexpass#123" | base64
# Output: cm9vdEBleGFtcGxlLmNvbTpDb21wbGV4cGFzczEyMz==
```

**Set environment variables:**
```bash
export OPENOBSERVE_URL="http://localhost:5080"
export OPENOBSERVE_ORG="default"
export OPENOBSERVE_AUTH_TOKEN="Basic cm9vdEBleGFtcGxlLmNvbTpDb21wbGV4cGFzczEyMz=="
export OPENAI_API_KEY="your-api-key"
```

**Install dependencies:**
```bash
pip install openai opentelemetry-instrumentation-openai
```

**Use with OpenAI:**
```python
from opentelemetry.instrumentation.openai import OpenAIInstrumentor
from openobserve import openobserve_init

# Initialize OpenObserve and instrument OpenAI
OpenAIInstrumentor().instrument()
openobserve_init()

from openai import OpenAI

# Use OpenAI as normal - traces are automatically captured
client = OpenAI()
response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENOBSERVE_URL` | ✅ | OpenObserve base URL |
| `OPENOBSERVE_ORG` | ✅ | Organization name (default: "default") |
| `OPENOBSERVE_AUTH_TOKEN` | ✅ | Authorization token (Format: "Basic <base64>") |
| `OPENOBSERVE_TIMEOUT` | No | HTTP timeout in seconds (default: 30) |
| `OPENOBSERVE_ENABLED` | No | Enable/disable tracing (default: "true") |

## Installation

```bash
pip install -e .
# Or
pip install -r requirements.txt
```

## Examples

See [examples/](examples/) directory for complete examples.

## License

MIT
