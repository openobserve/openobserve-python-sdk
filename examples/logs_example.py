"""
Logs Example: Using OpenObserve SDK to send OpenTelemetry logs

Before running, set these environment variables:
    export OPENOBSERVE_URL="http://localhost:5080"
    export OPENOBSERVE_ORG="default"
    export OPENOBSERVE_AUTH_TOKEN="Basic cm9vdEBleGFtcGxlLmNvbTpDb21wbGV4cGFzczEyMz=="
"""

import logging
import time

from dotenv import load_dotenv
from opentelemetry.sdk._logs import LoggingHandler

from openobserve import openobserve_init

load_dotenv()

# Option 1: Initialize only logs
# openobserve_init_logs()

# Option 2: Initialize all signals (logs, metrics, traces)
openobserve_init()

# Bridge Python logging to OpenTelemetry
handler = LoggingHandler(level=logging.NOTSET)
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.INFO)

logger = logging.getLogger("my-app")

# Send logs at different levels
logger.info("Application started", extra={"user_id": "user-123", "version": "1.0.0"})
logger.warning("Cache miss for key", extra={"cache_key": "product:456"})
logger.error("Failed to connect to database", extra={"host": "db.example.com", "retry": 3})

# Simulate some work with structured logging
for i in range(3):
    logger.info(f"Processing item {i}", extra={"item_id": i, "batch": "batch-001"})
    time.sleep(0.1)

logger.info("All items processed successfully")

print("Logs sent to OpenObserve!")
