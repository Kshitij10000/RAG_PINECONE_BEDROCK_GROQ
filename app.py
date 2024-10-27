import warnings
from typing import List
import boto3
import streamlit as st
from PyPDF2 import PdfReader
from dotenv import load_dotenv
from langchain.text_splitter import CharacterTextSplitter
from langchain_aws import BedrockEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain.schema import Document
from langchain.llms.bedrock import Bedrock
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory

# Suppress specific Pydantic warnings
warnings.filterwarnings(
    "ignore",
    message='Field "model_id" in BedrockBase has conflict with protected namespace "model_".',
    category=UserWarning
)
warnings.filterwarnings(
    "ignore",
    message='Field "model_kwargs" in BedrockBase has conflict with protected namespace "model_".',
    category=UserWarning
)

load_dotenv()

def extract_text_from_pdfs(pdf_docs: List[object]) -> str:
    """Extract text from uploaded PDF documents."""
    text = ""
    for pdf in pdf_docs:
        try:
            pdf_reader = PdfReader(pdf)
            num_pages = len(pdf_reader.pages)
            st.write(f"Processing {pdf.name} with {num_pages} pages.")
            for page_num, page in enumerate(pdf_reader.pages, start=1):
                page_text = page.extract_text()
                if page_text:
                    text += page_text
                if page_num % 10 == 0:
                    st.write(f"Processed {page_num} pages of {pdf.name}.")
        except Exception as e:
            st.error(f"Error reading {pdf.name}: {str(e)}")
    return text

def create_text_chunks(text: str) -> List[Document]:
    """Divide raw string data into chunks."""
    text_splitter = CharacterTextSplitter(
        separator="\n",
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    chunks = text_splitter.split_text(text)
    return [Document(page_content=chunk) for chunk in chunks]

def create_vector_store(chunks: List[Document]) -> PineconeVectorStore:
    """Store data into vector database."""
    try:
        embeddings = BedrockEmbeddings()
        index_name = "testfiles"
        return PineconeVectorStore.from_documents(chunks, embeddings, index_name=index_name)
    except Exception as e:
        st.error(f"Error creating vector store: {str(e)}")
        return None

def initialize_llm() -> Bedrock:
    """Initialize the Bedrock LLM."""
    try:
        bedrock_client = boto3.client(
            service_name="bedrock-runtime",
            region_name="us-east-1"  # replace with your preferred region
        )
        return Bedrock(
            model_id="meta.llama2-70b-chat-v1",
            client=bedrock_client,
            model_kwargs={
                "max_gen_len": 512,
                "temperature": 0.5,
                "top_p": 0.9
            }
        )
    except Exception as e:
        st.error(f"Error initializing LLM: {str(e)}")
        return None

def create_conversational_chain(llm: Bedrock, docsearch: PineconeVectorStore) -> ConversationalRetrievalChain:
    """Create a conversational chain with memory."""
    try:
        memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        return ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=docsearch.as_retriever(search_kwargs={"k": 1}),
            memory=memory
        )
    except Exception as e:
        st.error(f"Error creating conversational chain: {str(e)}")
        return None

def main():
    st.set_page_config(page_title="Chat with PDF", page_icon=":books:")
    st.header("📚 Chat with Your Documents")

    # Initialize session state
    if 'docsearch' not in st.session_state:
        st.session_state.docsearch = None
    if 'conversation' not in st.session_state:
        st.session_state.conversation = None
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []

    # Sidebar for document upload and processing
    with st.sidebar:
        st.subheader("🔄 Your Documents")
        pdf_docs = st.file_uploader(
            "Upload your PDF files",
            accept_multiple_files=True,
            type=['pdf']
        )
        
        max_files = 5
        if pdf_docs and len(pdf_docs) > max_files:
            st.warning(f"Please upload no more than {max_files} PDF files.")
            pdf_docs = pdf_docs[:max_files]
        
        if st.button("🛠️ Process Documents"):
            if not pdf_docs:
                st.warning("Please upload at least one PDF file.")
            else:
                with st.spinner("Processing..."):
                    try:
                        raw_text = extract_text_from_pdfs(pdf_docs)
                        if not raw_text.strip():
                            st.warning("No text extracted from the uploaded PDFs.")
                            return
                        docs = create_text_chunks(raw_text)
                        st.session_state.docsearch = create_vector_store(docs)
                        llm = initialize_llm()
                        if llm:
                            st.session_state.conversation = create_conversational_chain(llm, st.session_state.docsearch)
                            st.session_state.chat_history = []
                            st.success("✅ Documents processed successfully!")
                    except Exception as e:
                        st.error(f"An error occurred during processing: {str(e)}")

    st.markdown("---")
    st.subheader("💬 Chat Interface")

    # Display Chat History
    if st.session_state.chat_history:
        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    else:
        st.write("Start the conversation by typing a message below.")

    # User Input
    user_input = st.chat_input("Type your message here...")

    if user_input:
        if st.session_state.conversation:
            # Append user message to history
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)

            # Generate assistant response
            with st.chat_message("assistant"):
                with st.spinner("🤖 Generating response..."):
                    try:
                        response = st.session_state.conversation({"question": user_input})
                        answer = response['answer']
                        st.markdown(answer)
                        # Append assistant response to history
                        st.session_state.chat_history.append({"role": "assistant", "content": answer})
                    except Exception as e:
                        st.error(f"An error occurred while generating the response: {str(e)}")
        else:
            st.warning("⚠️ Please upload and process documents in the sidebar before chatting.")

if __name__ == '__main__':
    main()
