from build_chain import build_qa_chain
from opentelemetry.instrumentation.langchain import LangchainInstrumentor

from openobserve import openobserve_init

LangchainInstrumentor().instrument()
openobserve_init()

# Build the Q&A chain
qa_chain = build_qa_chain()

# Set up LangFuse handler
# This imports your chain and sets up the LangFuse handler. Now add session tracking for the first conversation:
# Session 1: User asking about security risks
response1 = qa_chain.invoke(
    {"input": "What are the main security risks discussed?"},
    config={"metadata": {"langfuse_session_id": "conversation-001"}},
)
print(f"Q1: {response1['answer']}\n")

response2 = qa_chain.invoke(
    {"input": "How can these risks be mitigated?"},
    config={"metadata": {"langfuse_session_id": "conversation-001"}},
)
print(f"Q2: {response2['answer']}\n")

# Session 2: Different user asking about AI applications
response3 = qa_chain.invoke(
    {"input": "What AI applications are mentioned in the document?"},
    config={"metadata": {"langfuse_session_id": "conversation-002"}},
)
print(f"Q3: {response3['answer']}\n")

response4 = qa_chain.invoke(
    {"input": "What are the benefits of these applications?"},
    config={"metadata": {"langfuse_session_id": "conversation-002"}},
)
print(f"Q4: {response4['answer']}\n")
