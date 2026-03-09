# OpenObserve Python SDK

A simple and lightweight Python SDK for exporting OpenTelemetry logs, metrics, and traces to [OpenObserve](https://openobserve.ai/).

## Quick Start

**Generate auth token:**
```bash
echo -n "root@example.com:Complexpass#123" | base64
# Output: cm9vdEBleGFtcGxlLmNvbTpDb21wbGV4cGFzcyMxMjM=
```

**Set environment variables:**
```bash
# Optional (defaults shown below)
export OPENOBSERVE_URL="http://localhost:5080"  # default
export OPENOBSERVE_ORG="default"  # default

# Required
export OPENOBSERVE_AUTH_TOKEN="Basic cm9vdEBleGFtcGxlLmNvbTpDb21wbGV4cGFzcyMxMjM="
export OPENAI_API_KEY="your-api-key"
export ANTHROPIC_API_KEY="your-api-key"
```

**Install dependencies:**
```bash
uv pip install openobserve-sdk openai opentelemetry-instrumentation-openai
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

### Selecting Signals

`openobserve_init()` initializes logs, metrics, and traces when no signal arguments are provided. As soon as you pass any of the `logs`, `metrics`, or `traces` flags, only the explicitly provided signals are enabled.

```python
# All signals (logs + metrics + traces)
openobserve_init()

# Logs only
openobserve_init(logs=True)

# Logs + metrics (no traces)
openobserve_init(logs=True, metrics=True)
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENOBSERVE_URL` | No | OpenObserve base URL (default: "http://localhost:5080") |
| `OPENOBSERVE_ORG` | No | Organization name (default: "default") |
| `OPENOBSERVE_AUTH_TOKEN` | ✅ | Authorization token (Format: "Basic <base64>") |
| `OPENOBSERVE_TIMEOUT` | No | Request timeout in seconds (default: 30) |
| `OPENOBSERVE_ENABLED` | No | Enable/disable tracing (default: "true") |
| `OPENOBSERVE_PROTOCOL` | No | Protocol: "grpc" or "http/protobuf" (default: "http/protobuf") |
| `OPENOBSERVE_TRACES_STREAM_NAME` | No | Stream name for traces (default: "default") |
| `OPENOBSERVE_LOGS_STREAM_NAME` | No | Stream name for logs (default: "default") |

### Protocol Configuration Notes

**HTTP/Protobuf (default)**
- Uses HTTP with Protocol Buffers encoding.
- Works with both HTTP and HTTPS endpoints.
- Organization is specified in the URL path: `/api/{org}/v1/{signal}`, where `{signal}` is `traces`, `logs`, or `metrics`.
- Automatically adds the `stream-name` header from `OPENOBSERVE_TRACES_STREAM_NAME` for traces and `OPENOBSERVE_LOGS_STREAM_NAME` for logs.
- Standard HTTP header handling (preserves case).

**gRPC**
- Uses gRPC protocol with automatic configuration:
  - Organization is passed as a header (not in the URL).
  - Automatically adds required headers:
    - `organization`: Set to `OPENOBSERVE_ORG`.
    - `stream-name`: Set to `OPENOBSERVE_TRACES_STREAM_NAME` for traces and `OPENOBSERVE_LOGS_STREAM_NAME` for logs.
  - Headers are normalized to lowercase per gRPC specification.
  - TLS is automatically configured based on URL scheme:
    - `http://` URLs use insecure (non-TLS) connections.
    - `https://` URLs use secure (TLS) connections.

## Installation

```bash
# Install from PyPI
pip install openobserve-sdk

# Or install from source (includes both HTTP/Protobuf and gRPC support)
pip install -e .

# Or using requirements.txt
pip install -r requirements.txt
```

## Examples

- `examples/openai_example.py` – end-to-end traces example with the OpenAI instrumentation.
- `examples/logs_example.py` – bridges standard Python logging through OpenTelemetry and ships the records to OpenObserve. Run with `uv run examples/logs_example.py`.
- `examples/metrics_example.py` – demonstrates counters, histograms, and up/down counters exported to OpenObserve. Run with `uv run examples/metrics_example.py`.
- `examples/session_demo.py`, `examples/qa_chain.py`, etc. – additional traces-first demos.

## License

MIT
