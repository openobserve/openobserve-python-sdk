# Quick Start Guide

This guide will help you get started with the OpenObserve Python SDK in 5 minutes.

## Prerequisites

- Python 3.7 or higher
- OpenObserve instance running (local or cloud)
- pip package manager

## Step 1: Install the SDK

```bash
# Clone or download the SDK
cd /path/to/openobserve-python-sdk

# Install in development mode
pip install -e .

# Or install dependencies directly
pip install -r requirements.txt
```

## Step 2: Set Up Environment Variables

Export the required environment variables:

```bash
export OPENOBSERVE_URL="http://localhost:5080"
export OPENOBSERVE_ORG="default"
export OPENOBSERVE_USER="root@example.com"
export OPENOBSERVE_PASSWORD="Complexpass#123"
export OPENOBSERVE_SERVICE_NAME="my-first-service"
```

## Step 3: Write Your First Traced Application

Create a file `my_app.py`:

```python
from openobserve_sdk import openobserve_init, openobserve_shutdown
from opentelemetry import trace
import time

# Initialize OpenObserve SDK from environment variables
openobserve_init()

# Get a tracer
tracer = trace.get_tracer(__name__)

# Create a traced function
def do_work():
    with tracer.start_as_current_span("do_work") as span:
        span.set_attribute("work.type", "example")
        print("Doing some work...")
        time.sleep(0.5)
        print("Work completed!")

# Run the function
if __name__ == "__main__":
    print("Starting application...")
    do_work()

    # Shutdown to flush spans
    openobserve_shutdown()
    print("Application finished!")
```

## Step 4: Run Your Application

```bash
python my_app.py
```

Expected output:
```
✓ OpenObserve SDK initialized
  Service: my-first-service
  Endpoint: http://localhost:5080/api/default/v1/traces
Starting application...
Doing some work...
Work completed!
✓ OpenObserve SDK shutdown complete
Application finished!
```

## Step 5: View Traces in OpenObserve

1. Open your browser and navigate to OpenObserve UI (e.g., http://localhost:5080)
2. Log in with your credentials
3. Navigate to **Traces** section
4. Select your service name: `my-first-service`
5. You should see the trace with the span `do_work`

## Next Steps

### Try the Examples

Run the provided examples to see more features:

```bash
# Basic tracing example
python examples/basic_example.py

# Environment variables example
python examples/env_example.py

# OpenAI integration example (requires OpenAI API key)
export OPENAI_API_KEY="your-key"
pip install openai opentelemetry-instrumentation-openai
python examples/openai_example.py
```

### Add Nested Spans

```python
from openobserve_sdk import openobserve_init
from opentelemetry import trace

# Initialize from environment variables
openobserve_init()

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("parent-operation") as parent:
    parent.set_attribute("level", "parent")

    # Child span 1
    with tracer.start_as_current_span("child-1") as child1:
        child1.set_attribute("task", "processing")
        # Do work

    # Child span 2
    with tracer.start_as_current_span("child-2") as child2:
        child2.set_attribute("task", "validation")
        # Do work
```

### Add Custom Attributes and Events

```python
with tracer.start_as_current_span("process-order") as span:
    # Add attributes
    span.set_attribute("order.id", "ORD-12345")
    span.set_attribute("customer.id", "CUST-789")
    span.set_attribute("order.amount", 99.99)

    # Add events
    span.add_event("order_received", {
        "timestamp": time.time(),
        "source": "api"
    })

    # Process order...

    span.add_event("order_processed", {
        "status": "success"
    })
```

### Instrument Existing Libraries

The SDK works with all OpenTelemetry auto-instrumentation libraries:

```python
from openobserve_sdk import openobserve_init

# Initialize from environment variables
openobserve_init()

# Then instrument libraries
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.flask import FlaskInstrumentor

RequestsInstrumentor().instrument()
FlaskInstrumentor().instrument_app(app)

# All HTTP requests and Flask routes are now traced!
```

## Troubleshooting

### SDK not initialized error

Make sure you call `openobserve_init()` before using any tracing:

```python
from openobserve_sdk import openobserve_init

# Must be called before any tracing
# Make sure environment variables are set
openobserve_init()
```

### No traces appearing in OpenObserve

1. Check that OpenObserve is running and accessible
2. Verify credentials are correct
3. Check the endpoint URL (should not have trailing slash)
4. Call `openobserve_shutdown()` or `openobserve_flush()` to ensure spans are sent
5. Check OpenObserve logs for any errors

### Connection timeout

Increase the timeout value:

```python
openobserve_init(
    url="http://localhost:5080",
    org="default",
    user="root@example.com",
    password="Complexpass#123",
    timeout=60  # Increase to 60 seconds
)
```

## Additional Resources

- [Full README](README.md) - Complete documentation
- [OpenObserve Documentation](https://openobserve.ai/docs/)
- [OpenTelemetry Python Documentation](https://opentelemetry.io/docs/instrumentation/python/)

## Need Help?

- Create an issue on GitHub
- Check OpenObserve community forums
- Review the example code in the `examples/` directory
