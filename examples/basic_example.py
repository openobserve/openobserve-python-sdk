"""
Basic Example: Using OpenObserve SDK

This example demonstrates the basic usage of the OpenObserve SDK
to export OpenTelemetry traces to OpenObserve.

Before running, set these environment variables:
    export OPENOBSERVE_URL="http://localhost:5080"
    export OPENOBSERVE_ORG="default"
    export OPENOBSERVE_AUTH_TOKEN="Basic cm9vdEBleGFtcGxlLmNvbTpDb21wbGV4cGFzczEyMz=="

To generate the auth token:
    echo -n "root@example.com:Complexpass#123" | base64
"""

import time
from openobserve_sdk import openobserve_init
from opentelemetry import trace


def main():
    # Initialize OpenObserve SDK from environment variables
    openobserve_init()

    # Get a tracer
    tracer = trace.get_tracer(__name__)

    # Example 1: Simple span
    print("\n--- Example 1: Simple Span ---")
    with tracer.start_as_current_span("simple-operation") as span:
        span.set_attribute("operation.type", "demo")
        span.set_attribute("user.id", "user-123")
        print("Executing simple operation...")
        time.sleep(0.1)
        print("✓ Simple operation completed")

    # Example 2: Nested spans
    print("\n--- Example 2: Nested Spans ---")
    with tracer.start_as_current_span("parent-operation") as parent:
        parent.set_attribute("operation.level", "parent")
        print("Parent operation started...")

        with tracer.start_as_current_span("child-operation-1") as child1:
            child1.set_attribute("operation.level", "child")
            child1.set_attribute("child.id", 1)
            print("  Child operation 1 started...")
            time.sleep(0.05)
            print("  ✓ Child operation 1 completed")

        with tracer.start_as_current_span("child-operation-2") as child2:
            child2.set_attribute("operation.level", "child")
            child2.set_attribute("child.id", 2)
            print("  Child operation 2 started...")
            time.sleep(0.05)
            print("  ✓ Child operation 2 completed")

        print("✓ Parent operation completed")

    # Example 3: Span with events
    print("\n--- Example 3: Span with Events ---")
    with tracer.start_as_current_span("operation-with-events") as span:
        span.add_event("processing_started", {"item_count": 10})
        print("Processing started...")

        # Simulate processing
        for i in range(3):
            time.sleep(0.03)
            span.add_event(f"item_processed", {"item_id": i})
            print(f"  Item {i} processed")

        span.add_event("processing_completed", {"total_items": 3})
        print("✓ Processing completed")

    # Example 4: Span with error handling
    print("\n--- Example 4: Error Handling ---")
    with tracer.start_as_current_span("operation-with-error") as span:
        try:
            print("Attempting risky operation...")
            # Simulate an error
            raise ValueError("Simulated error for demo")
        except Exception as e:
            span.set_attribute("error", True)
            span.set_attribute("error.type", type(e).__name__)
            span.set_attribute("error.message", str(e))
            span.add_event("exception", {"exception.type": type(e).__name__, "exception.message": str(e)})
            print(f"✗ Error occurred: {e}")

    print("\n✓ All examples completed!")
    print("  Check OpenObserve dashboard for traces")
    print("  Navigate to: Traces -> Select 'basic-demo-service'")
    print("\n  Note: Spans will be automatically flushed on program exit")


if __name__ == "__main__":
    main()
