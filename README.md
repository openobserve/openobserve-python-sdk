# OpenObserve Python SDK

A simple and lightweight Python SDK for exporting OpenTelemetry traces to [OpenObserve](https://openobserve.ai/).

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
uv pip install openai opentelemetry-instrumentation-openai
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
| `OPENOBSERVE_URL` | No | OpenObserve base URL (default: "http://localhost:5080") |
| `OPENOBSERVE_ORG` | No | Organization name (default: "default") |
| `OPENOBSERVE_AUTH_TOKEN` | ✅ | Authorization token (Format: "Basic <base64>") |
| `OPENOBSERVE_TIMEOUT` | No | Request timeout in seconds (default: 30) |
| `OPENOBSERVE_ENABLED` | No | Enable/disable tracing (default: "true") |
| `OPENOBSERVE_PROTOCOL` | No | Protocol: "grpc" or "http/protobuf" (default: "http/protobuf") |
| `OPENOBSERVE_TRACES_STREAM_NAME` | No | Stream name for traces (default: "default") |

### Protocol Configuration Notes

**HTTP/Protobuf (default)**
- Uses HTTP with Protocol Buffers encoding
- Works with both HTTP and HTTPS endpoints
- Organization is specified in the URL path: `/api/{org}/v1/traces`
- Automatically adds `stream-name` header from `OPENOBSERVE_TRACES_STREAM_NAME`
- Standard HTTP header handling (preserves case)

**gRPC**
- Uses gRPC protocol with automatic configuration:
  - Organization is passed as a header (not in URL)
  - Automatically adds required headers:
    - `organization`: Set to the value of `OPENOBSERVE_ORG`
    - `stream-name`: Set to the value of `OPENOBSERVE_TRACES_STREAM_NAME` (default: "default")
  - Headers are normalized to lowercase per gRPC specification
  - TLS is automatically configured based on URL scheme:
    - `http://` URLs use insecure (non-TLS) connections
    - `https://` URLs use secure (TLS) connections

## Installation

```bash
# Install the SDK (includes both HTTP/Protobuf and gRPC support)
uv pip install -e .

# Or using requirements.txt
uv pip install -r requirements.txt
```

## Examples

See [examples/](examples/) directory for complete examples.

You can run it:

```
uv run examples/openai_example.py
```

## License

MIT
