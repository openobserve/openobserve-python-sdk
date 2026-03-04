from build_chain import build_qa_chain
from opentelemetry.instrumentation.langchain import LangchainInstrumentor

from openobserve import openobserve_init

LangchainInstrumentor().instrument()
openobserve_init()
# Build the Q&A chain
qa_chain = build_qa_chain()

# Simulate a new user asking a question
user_response = qa_chain.invoke(
    {"input": "What security controls are recommended for AI systems?"},
    config={
        "metadata": {"langfuse_session_id": "conversation-003", "langfuse_user_id": "user-12345"}
    },
)
print(f"Response: {user_response['answer']}")
