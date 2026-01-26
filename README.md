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
```

**Use in code:**
```python
from openobserve import openobserve_init
from opentelemetry import trace

# Initialize from environment variables
openobserve_init()

# Use OpenTelemetry
tracer = trace.get_tracer(__name__)
with tracer.start_as_current_span("my-operation"):
    # Your code here
    pass
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
