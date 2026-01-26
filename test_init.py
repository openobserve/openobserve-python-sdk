#!/usr/bin/env python3
"""
Quick test script to verify openobserve_init() works with environment variables.

Before running:
    export OPENOBSERVE_URL="http://localhost:5080"
    export OPENOBSERVE_ORG="default"
    export OPENOBSERVE_AUTH_TOKEN="Basic cm9vdEBleGFtcGxlLmNvbTpDb21wbGV4cGFzczEyMz=="

To generate the auth token:
    echo -n "root@example.com:Complexpass#123" | base64

Then run:
    python test_init.py
"""

import os
import time
from openobserve_sdk import openobserve_init, openobserve_shutdown, is_initialized
from opentelemetry import trace


def main():
    print("=" * 60)
    print("OpenObserve SDK Test - Environment Variables Configuration")
    print("=" * 60)

    # Check if required environment variables are set
    required_vars = [
        "OPENOBSERVE_URL",
        "OPENOBSERVE_ORG",
        "OPENOBSERVE_AUTH_TOKEN"
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print("\n❌ ERROR: Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease set these variables before running this script.")
        print("\nTo generate OPENOBSERVE_AUTH_TOKEN:")
        print('  echo -n "user@example.com:password" | base64')
        return 1

    print("\n✓ All required environment variables are set:")
    print(f"  OPENOBSERVE_URL: {os.getenv('OPENOBSERVE_URL')}")
    print(f"  OPENOBSERVE_ORG: {os.getenv('OPENOBSERVE_ORG')}")
    print(f"  OPENOBSERVE_AUTH_TOKEN: {os.getenv('OPENOBSERVE_AUTH_TOKEN')[:20]}...")

    # Initialize SDK with no parameters - all from env
    print("\n" + "=" * 60)
    print("Initializing SDK from environment variables...")
    print("=" * 60)

    try:
        openobserve_init()
        print("\n✓ SDK initialized successfully!")
    except Exception as e:
        print(f"\n❌ Failed to initialize SDK: {e}")
        return 1

    # Verify initialization
    if not is_initialized():
        print("❌ SDK is not initialized!")
        return 1

    print("✓ SDK initialization verified")

    # Create some test traces
    print("\n" + "=" * 60)
    print("Creating test traces...")
    print("=" * 60)

    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span("test-operation") as span:
        span.set_attribute("test.type", "sdk-verification")
        span.set_attribute("test.timestamp", time.time())
        print("\n✓ Created test span: test-operation")

        time.sleep(0.1)

        with tracer.start_as_current_span("nested-operation") as nested:
            nested.set_attribute("nested.level", 1)
            print("✓ Created nested span: nested-operation")
            time.sleep(0.05)

    # Shutdown and flush
    # Note: This is optional - SDK will automatically shutdown on exit
    # We call it explicitly here for immediate verification in tests
    print("\n" + "=" * 60)
    print("Shutting down SDK...")
    print("=" * 60)

    openobserve_shutdown()

    print("\n" + "=" * 60)
    print("✓ Test completed successfully!")
    print("=" * 60)
    print("\nCheck your OpenObserve dashboard to see the traces:")
    print(f"  URL: {os.getenv('OPENOBSERVE_URL')}")
    print("\n")

    return 0


if __name__ == "__main__":
    exit(main())
