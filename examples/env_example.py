"""
Environment Variables Example: Using OpenObserve SDK with environment variables

This example demonstrates how to use environment variables for configuration.

Set the following environment variables before running:
    export OPENOBSERVE_URL="http://localhost:5080"
    export OPENOBSERVE_ORG="default"
    export OPENOBSERVE_AUTH_TOKEN="Basic cm9vdEBleGFtcGxlLmNvbTpDb21wbGV4cGFzczEyMz=="
    export OPENOBSERVE_TIMEOUT="30"
    export OPENOBSERVE_ENABLED="true"

To generate the auth token:
    echo -n "root@example.com:Complexpass#123" | base64
"""

from openobserve_sdk import openobserve_init
from opentelemetry import trace
import time


def process_data(data: list):
    """Example function that processes data with tracing."""
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span("process_data") as span:
        span.set_attribute("data.count", len(data))

        results = []
        for i, item in enumerate(data):
            with tracer.start_as_current_span(f"process_item_{i}") as item_span:
                item_span.set_attribute("item.value", item)
                # Simulate processing
                time.sleep(0.05)
                result = item * 2
                item_span.set_attribute("item.result", result)
                results.append(result)

        span.set_attribute("results.sum", sum(results))
        return results


def main():
    # Initialize using environment variables
    # All configuration will be read from environment
    openobserve_init()

    # Example: Process some data
    print("\n--- Processing Data ---")
    data = [1, 2, 3, 4, 5]
    print(f"Input data: {data}")

    results = process_data(data)
    print(f"Results: {results}")

    print("\n✓ Processing completed!")
    print("  Check OpenObserve dashboard for traces")
    print("\n  Note: Spans will be automatically flushed on program exit")


if __name__ == "__main__":
    main()
