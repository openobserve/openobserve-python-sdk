# Quick Reference Card

## Generate Auth Token

```bash
echo -n "username:password" | base64
# Add "Basic " prefix when using
```

## Environment Variables

```bash
export OPENOBSERVE_URL="http://localhost:5080"
export OPENOBSERVE_ORG="default"
export OPENOBSERVE_AUTH_TOKEN="Basic <base64-token>"
```

## Python Code

```python
from openobserve_sdk import openobserve_init
from opentelemetry import trace

# Initialize
openobserve_init()

# Use
tracer = trace.get_tracer(__name__)
with tracer.start_as_current_span("operation"):
    pass
```

## Test

```bash
python test_init.py
```

## That's it! 🎉
