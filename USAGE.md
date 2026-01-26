# OpenObserve SDK Usage Guide

## Environment-First Configuration

The OpenObserve SDK is designed to read all configuration from environment variables by default. This follows security best practices and makes deployment easier.

## Basic Usage

### Step 1: Set Environment Variables

```bash
export OPENOBSERVE_URL="http://localhost:5080"
export OPENOBSERVE_ORG="default"
export OPENOBSERVE_USER="root@example.com"
export OPENOBSERVE_PASSWORD="Complexpass#123"
export OPENOBSERVE_SERVICE_NAME="my-service"
```

### Step 2: Initialize and Use

```python
from openobserve_sdk import openobserve_init
from opentelemetry import trace

# Initialize - all config from environment
openobserve_init()

# Use OpenTelemetry
tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("my-operation"):
    # Your code here
    pass
```

That's it! No credentials in code.

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENOBSERVE_URL` | ✅ Yes | - | OpenObserve base URL |
| `OPENOBSERVE_ORG` | ✅ Yes | `"default"` | Organization name |
| `OPENOBSERVE_USER` | ✅ Yes | - | Username or email |
| `OPENOBSERVE_PASSWORD` | ✅ Yes | - | Password or API token |
| `OPENOBSERVE_SERVICE_NAME` | No | `"openobserve-service"` | Service name in traces |
| `OPENOBSERVE_TIMEOUT` | No | `30` | HTTP timeout (seconds) |
| `OPENOBSERVE_ENABLED` | No | `"true"` | Enable/disable tracing |

## Advanced: Override Specific Settings

If needed, you can override specific settings while keeping others from environment:

```python
# Use env vars for credentials, but override service name
openobserve_init(service_name="custom-service")

# Override multiple settings
openobserve_init(
    service_name="custom-service",
    timeout=60,
    enabled=True
)
```

## Working with .env Files

For development, you can use a `.env` file:

```bash
# Copy the example
cp .env.example .env

# Edit .env with your values
nano .env
```

Then load it in your code:

```python
# Using python-dotenv
from dotenv import load_dotenv
load_dotenv()

# Now initialize
from openobserve_sdk import openobserve_init
openobserve_init()
```

## Docker/Kubernetes

### Docker

```dockerfile
FROM python:3.9

# Install dependencies
RUN pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http

# Copy your app
COPY . /app
WORKDIR /app

# Environment variables will be passed at runtime
CMD ["python", "main.py"]
```

Run with environment variables:

```bash
docker run \
  -e OPENOBSERVE_URL="http://openobserve:5080" \
  -e OPENOBSERVE_ORG="default" \
  -e OPENOBSERVE_USER="root@example.com" \
  -e OPENOBSERVE_PASSWORD="Complexpass#123" \
  -e OPENOBSERVE_SERVICE_NAME="my-service" \
  my-app
```

### Kubernetes

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: openobserve-config
type: Opaque
stringData:
  OPENOBSERVE_URL: "http://openobserve:5080"
  OPENOBSERVE_ORG: "default"
  OPENOBSERVE_USER: "root@example.com"
  OPENOBSERVE_PASSWORD: "Complexpass#123"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
spec:
  template:
    spec:
      containers:
      - name: app
        image: my-app:latest
        envFrom:
        - secretRef:
            name: openobserve-config
        env:
        - name: OPENOBSERVE_SERVICE_NAME
          value: "my-service"
```

## Complete Example

```python
#!/usr/bin/env python3
"""
Complete example using environment variables only.
"""

from openobserve_sdk import openobserve_init, openobserve_shutdown
from opentelemetry import trace
import time


def main():
    # Initialize from environment variables
    openobserve_init()

    # Get tracer
    tracer = trace.get_tracer(__name__)

    # Create traces
    with tracer.start_as_current_span("main-operation") as span:
        span.set_attribute("app.version", "1.0.0")

        # Do some work
        process_data()

        # Add custom events
        span.add_event("operation_completed")

    # Cleanup
    openobserve_shutdown()


def process_data():
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span("process-data"):
        time.sleep(0.1)
        # Process data...


if __name__ == "__main__":
    main()
```

Run it:

```bash
# Set environment variables
export OPENOBSERVE_URL="http://localhost:5080"
export OPENOBSERVE_ORG="default"
export OPENOBSERVE_USER="root@example.com"
export OPENOBSERVE_PASSWORD="Complexpass#123"
export OPENOBSERVE_SERVICE_NAME="my-app"

# Run
python main.py
```

## API Functions

### `openobserve_init()`

Initialize SDK from environment variables.

```python
openobserve_init()  # All from environment
```

### `openobserve_shutdown()`

Flush and shutdown SDK.

```python
openobserve_shutdown()  # Call at application exit
```

### `openobserve_flush()`

Force flush pending spans without shutting down.

```python
openobserve_flush()  # Useful for periodic flushing
```

### `is_initialized()`

Check if SDK is initialized.

```python
if is_initialized():
    print("SDK is ready")
```

## Best Practices

1. **Always use environment variables** - Never hardcode credentials
2. **Call `openobserve_init()` early** - Initialize before any other OpenTelemetry instrumentation
3. **Call `openobserve_shutdown()` on exit** - Ensures all spans are flushed
4. **Use meaningful service names** - Helps identify traces in OpenObserve
5. **Set appropriate timeouts** - Adjust based on your network conditions

## Troubleshooting

### Missing environment variables

Error: `ValueError: OpenObserve URL is required`

Solution: Make sure all required environment variables are set.

### Connection timeout

Error: Connection timeout to OpenObserve

Solution: Increase timeout: `export OPENOBSERVE_TIMEOUT=60`

### No traces in OpenObserve

Checklist:
- ✅ Environment variables are set correctly
- ✅ OpenObserve is running and accessible
- ✅ Credentials are valid
- ✅ Called `openobserve_shutdown()` or `openobserve_flush()`
- ✅ Service name is correct in OpenObserve UI

### Already initialized error

Error: `RuntimeError: OpenObserve SDK already initialized`

Solution: Only call `openobserve_init()` once, or call `openobserve_shutdown()` first.

## Next Steps

- See [QUICKSTART.md](QUICKSTART.md) for a 5-minute tutorial
- See [README.md](README.md) for complete documentation
- Check [examples/](examples/) for more usage examples
