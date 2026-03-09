"""
Metrics Example: Using OpenObserve SDK to send OpenTelemetry metrics

Before running, set these environment variables:
    export OPENOBSERVE_URL="http://localhost:5080"
    export OPENOBSERVE_ORG="default"
    export OPENOBSERVE_AUTH_TOKEN="Basic cm9vdEBleGFtcGxlLmNvbTpDb21wbGV4cGFzczEyMz=="
"""

import random
import time

from dotenv import load_dotenv
from opentelemetry import metrics

from openobserve import openobserve_init

load_dotenv()

# Option 1: Initialize only metrics
# openobserve_init_metrics()

# Option 2: Initialize all signals (logs, metrics, traces)
openobserve_init()

# Create a meter
meter = metrics.get_meter("my-app")

# Counter - tracks cumulative values (e.g., total requests)
request_counter = meter.create_counter(
    name="http_requests_total",
    description="Total number of HTTP requests",
    unit="1",
)

# Histogram - tracks distributions (e.g., request latency)
latency_histogram = meter.create_histogram(
    name="http_request_duration_seconds",
    description="HTTP request latency in seconds",
    unit="s",
)

# UpDownCounter - tracks values that go up and down (e.g., active connections)
active_connections = meter.create_up_down_counter(
    name="active_connections",
    description="Number of active connections",
    unit="1",
)

# Simulate some traffic
endpoints = ["/api/users", "/api/products", "/api/orders"]
methods = ["GET", "POST"]
status_codes = [200, 200, 200, 201, 400, 500]

for _ in range(20):
    endpoint = random.choice(endpoints)
    method = random.choice(methods)
    status = random.choice(status_codes)

    # Record a request
    request_counter.add(1, {"endpoint": endpoint, "method": method, "status": str(status)})

    # Record latency
    latency = random.uniform(0.01, 0.5)
    latency_histogram.record(latency, {"endpoint": endpoint, "method": method})

    # Simulate connection changes
    if random.random() > 0.5:
        active_connections.add(1, {"server": "web-01"})
    else:
        active_connections.add(-1, {"server": "web-01"})

    time.sleep(0.1)

print("Metrics sent to OpenObserve!")
# Note: PeriodicExportingMetricReader exports on interval (default 60s).
# The SDK auto-flushes on exit, so all metrics will be sent.
