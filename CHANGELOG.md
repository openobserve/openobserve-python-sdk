# Changelog

All notable changes to the OpenObserve Python SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-01-26

### Added
- Initial release of OpenObserve Python SDK
- `openobserve_init()` function for one-line SDK initialization
- `OpenObserveConfig` class for configuration management
- `OpenObserveClient` class for TracerProvider management
- Support for environment variables configuration
- Automatic OTLP HTTP exporter setup with Basic authentication
- BatchSpanProcessor for efficient span export
- Global TracerProvider registration
- Thread-safe singleton pattern implementation
- `openobserve_shutdown()` function for graceful shutdown
- `openobserve_flush()` function for forcing span export
- `is_initialized()` helper function
- `get_tracer_provider()` helper function
- Comprehensive README with usage examples
- Quick start guide
- Example scripts:
  - `basic_example.py` - Basic tracing examples
  - `openai_example.py` - OpenAI integration example
  - `env_example.py` - Environment variables configuration example
- Project packaging files (`setup.py`, `pyproject.toml`, `requirements.txt`)
- MIT License
- `.gitignore` for Python projects

### Features
- Compatible with Python 3.7+
- Works with all OpenTelemetry instrumentation libraries
- Configurable timeout for HTTP requests
- Support for additional HTTP headers
- Support for custom resource attributes
- Enable/disable tracing via configuration

### Documentation
- Complete API reference in README
- Architecture documentation
- Comparison with manual setup
- Integration examples with other libraries
- Troubleshooting guide

## [Unreleased]

### Planned Features
- Async support for non-blocking initialization
- Metrics export support
- Logs export support
- Custom sampling strategies
- Retry logic for failed exports
- Connection pooling
- Compression support for OTLP payloads
- More instrumentation examples
- Unit tests and integration tests
- CI/CD pipeline
- PyPI package publication
