from dotenv import load_dotenv
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()


def build_qa_chain():
    # Load and split PDF
    loader = PyPDFLoader("examples/ai-security-landscape.pdf")
    docs = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(docs)

    # Create vector store
    embeddings = OpenAIEmbeddings()
    vectorstore = InMemoryVectorStore.from_documents(documents=splits, embedding=embeddings)

    # Build QA chain
    llm = ChatOpenAI(model="gpt-4")
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Use the given context to answer the question. If you don't know the answer, say you don't know. Keep the answer concise.\n\n{context}",
            ),
            ("human", "{input}"),
        ]
    )

    question_answer_chain = create_stuff_documents_chain(llm, prompt)
    qa_chain = create_retrieval_chain(vectorstore.as_retriever(), question_answer_chain)

    return qa_chain
