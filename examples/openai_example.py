"""
OpenAI Example: Using OpenObserve SDK with OpenAI instrumentation

This example demonstrates how to use the OpenObserve SDK to export
OpenAI API call traces to OpenObserve.

Requirements:
    pip install openai opentelemetry-instrumentation-openai

Before running, set these environment variables:
    export OPENOBSERVE_URL="http://localhost:5080"
    export OPENOBSERVE_ORG="default"
    export OPENOBSERVE_AUTH_TOKEN="Basic cm9vdEBleGFtcGxlLmNvbTpDb21wbGV4cGFzczEyMz=="
    export OPENAI_API_KEY="your-api-key"

To generate the auth token:
    echo -n "root@example.com:Complexpass#123" | base64
"""

from openobserve_sdk import openobserve_init
from opentelemetry import trace
from opentelemetry.instrumentation.openai import OpenAIInstrumentor
OpenAIInstrumentor().instrument()
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
openobserve_init()

def main():
    # Create OpenAI client
    client = OpenAI()

    # Get a tracer for custom spans
    tracer = trace.get_tracer(__name__)

    # Example 1: Simple chat completion
    print("\n--- Example 1: Chat Completion ---")
    with tracer.start_as_current_span("chat-completion-demo") as span:
        span.set_attribute("user.query", "What is OpenTelemetry?")

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is OpenTelemetry in one sentence?"},
            ],
            max_tokens=100,
        )

        answer = response.choices[0].message.content
        span.set_attribute("assistant.response", answer)
        print(f"Response: {answer}")

    # Example 2: Streaming chat completion
    print("\n--- Example 2: Streaming Chat Completion ---")
    with tracer.start_as_current_span("streaming-demo") as span:
        span.set_attribute("user.query", "Count from 1 to 5")

        stream = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": "Count from 1 to 5."},
            ],
            stream=True,
            max_tokens=50,
        )

        print("Response: ", end="")
        chunks = []
        for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                print(content, end="", flush=True)
                chunks.append(content)
        print()

        span.set_attribute("assistant.response", "".join(chunks))

    # Example 3: Embeddings
    print("\n--- Example 3: Embeddings ---")
    with tracer.start_as_current_span("embeddings-demo") as span:
        text = "OpenTelemetry is an observability framework."
        span.set_attribute("input.text", text)

        embedding_response = client.embeddings.create(
            model="text-embedding-ada-002",
            input=text,
        )

        dimension = len(embedding_response.data[0].embedding)
        span.set_attribute("embedding.dimension", dimension)
        print(f"Embedding dimension: {dimension}")

    print("\n✓ All examples completed!")
    print("  Check OpenObserve dashboard for traces")
    print("  Navigate to: Traces -> Select 'openai-demo-service'")
    print("\n  Note: Spans will be automatically flushed on program exit")


if __name__ == "__main__":
    main()
