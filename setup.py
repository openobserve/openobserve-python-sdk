"""
Setup script for OpenObserve Python SDK
"""

from setuptools import setup, find_packages

# Read the README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="openobserve-sdk",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A simple Python SDK for exporting OpenTelemetry traces to OpenObserve",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/openobserve-python-sdk",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: System :: Monitoring",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.7",
    install_requires=[
        "opentelemetry-api>=1.20.0",
        "opentelemetry-sdk>=1.20.0",
        "opentelemetry-exporter-otlp-proto-http>=1.20.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "isort>=5.10.0",
            "mypy>=0.990",
        ],
        "openai": [
            "openai>=1.0.0",
            "opentelemetry-instrumentation-openai>=0.18.0",
        ],
    },
    keywords="openobserve opentelemetry tracing observability monitoring",
    project_urls={
        "Bug Tracker": "https://github.com/your-org/openobserve-python-sdk/issues",
        "Documentation": "https://github.com/your-org/openobserve-python-sdk#readme",
        "Source Code": "https://github.com/your-org/openobserve-python-sdk",
    },
)
