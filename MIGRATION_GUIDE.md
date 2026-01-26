# Migration Guide

## Changes from v0.1.0 to v0.2.0

The SDK has been simplified to use direct authorization tokens instead of separate user/password fields, and service_name has been removed.

### What Changed

#### Removed Parameters:
- ❌ `user` - Use `auth_token` instead
- ❌ `password` - Use `auth_token` instead
- ❌ `service_name` - Removed (configure via resource_attributes if needed)

#### Added Parameters:
- ✅ `auth_token` - Direct authorization token

#### Environment Variables Changed:
- ❌ `OPENOBSERVE_USER` → ✅ `OPENOBSERVE_AUTH_TOKEN`
- ❌ `OPENOBSERVE_PASSWORD` → ✅ `OPENOBSERVE_AUTH_TOKEN`
- ❌ `OPENOBSERVE_SERVICE_NAME` → Removed

### Before (v0.1.0)

```bash
export OPENOBSERVE_URL="http://localhost:5080"
export OPENOBSERVE_ORG="default"
export OPENOBSERVE_USER="root@example.com"
export OPENOBSERVE_PASSWORD="Complexpass#123"
export OPENOBSERVE_SERVICE_NAME="my-service"
```

```python
from openobserve_sdk import openobserve_init

openobserve_init()
```

### After (v0.2.0)

```bash
# Generate auth token
echo -n "root@example.com:Complexpass#123" | base64
# Output: cm9vdEBleGFtcGxlLmNvbTpDb21wbGV4cGFzczEyMz==

export OPENOBSERVE_URL="http://localhost:5080"
export OPENOBSERVE_ORG="default"
export OPENOBSERVE_AUTH_TOKEN="Basic cm9vdEBleGFtcGxlLmNvbTpDb21wbGV4cGFzczEyMz=="
```

```python
from openobserve_sdk import openobserve_init

openobserve_init()
```

### Migrating Service Name

If you need to set a service name, use resource attributes:

```python
from openobserve_sdk import openobserve_init
from opentelemetry.sdk.resources import SERVICE_NAME

openobserve_init(
    resource_attributes={
        SERVICE_NAME: "my-service"
    }
)
```

### Why This Change?

1. **Simplified Authentication**: Direct token approach is more flexible and secure
2. **Standardization**: Matches common OpenTelemetry patterns
3. **Flexibility**: Resource attributes provide more control over service metadata

### Need Help?

If you encounter issues during migration, please create an issue on GitHub.
