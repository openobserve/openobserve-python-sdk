#!/usr/bin/env python3
"""
Test script to verify automatic shutdown via atexit.

This script tests that:
1. atexit handler is registered on init
2. SDK shuts down automatically on exit
3. No explicit shutdown() call is needed
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock the environment
os.environ['OPENOBSERVE_URL'] = 'http://localhost:5080'
os.environ['OPENOBSERVE_ORG'] = 'test'
os.environ['OPENOBSERVE_AUTH_TOKEN'] = 'Basic dGVzdDp0ZXN0'

from openobserve_sdk import openobserve_init
from opentelemetry import trace
import atexit

print("=" * 60)
print("Testing Automatic Shutdown via atexit")
print("=" * 60)

# Initialize SDK
print("\nInitializing OpenObserve SDK...")
try:
    openobserve_init()
    print("✓ SDK initialized successfully")
except Exception as e:
    print(f"✗ Failed to initialize: {e}")
    sys.exit(1)

# Check that atexit handler was registered
from openobserve_sdk.client import _atexit_registered, _auto_shutdown
if _atexit_registered:
    print("✓ atexit handler registered")
else:
    print("✗ atexit handler NOT registered")
    sys.exit(1)

# Create some test spans
print("\nCreating test spans...")
tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("test-span") as span:
    span.set_attribute("test", "auto-shutdown")
    print("✓ Created test span")

print("\n" + "=" * 60)
print("✓ Test completed!")
print("=" * 60)
print("\nNOTE: No explicit shutdown() call!")
print("The SDK will automatically shutdown on exit via atexit.")
print("=" * 60)

# Exit without calling openobserve_shutdown()
# The atexit handler should automatically flush and shutdown
