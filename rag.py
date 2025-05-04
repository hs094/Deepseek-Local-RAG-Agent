import os
import uuid
import streamlit as st
import tempfile
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_groq import ChatGroq
from pinecone import Pinecone, ServerlessSpec

# Set page title and description
st.title("📚 Simple RAG Application")
st.write("Upload documents and ask questions about them!")

# Sidebar for API keys
with st.sidebar:
    st.header("API Keys")
    groq_api_key = st.text_input("Groq API Key (for LLM)", type="password")
    pinecone_api_key = st.text_input("Pinecone API Key", type="password")

    # Index settings
    st.header("Pinecone Settings")
    index_name = st.text_input("Index Name", value="my-rag-index")

    # Initialize button
    initialize_button = st.button("Initialize Pinecone")

# Main content area
uploaded_files = st.file_uploader("Upload documents", accept_multiple_files=True, type=["pdf", "txt"])
query = st.text_input("Ask a question about your documents")
submit_button = st.button("Submit")

# Initialize session state
if 'initialized' not in st.session_state:
    st.session_state.initialized = False
if 'index' not in st.session_state:
    st.session_state.index = None
if 'documents_processed' not in st.session_state:
    st.session_state.documents_processed = False
if 'index_host' not in st.session_state:
    st.session_state.index_host = ""

# Helper function to chunk data for batch processing
def chunker(seq, batch_size):
    return [seq[pos:pos + batch_size] for pos in range(0, len(seq), batch_size)]

# Initialize Pinecone
if initialize_button:
    if not pinecone_api_key or not groq_api_key:
        st.error("Please provide both Groq and Pinecone API keys")
    else:
        try:
            # Set API keys
            os.environ["GROQ_API_KEY"] = groq_api_key
            os.environ["PINECONE_API_KEY"] = pinecone_api_key

            # Initialize Pinecone client
            with st.spinner("Initializing Pinecone..."):
                # Use the REST client for index management
                pc = Pinecone(api_key=pinecone_api_key)

                # Check if index exists, create if not
                existing_indexes = [idx.name for idx in pc.list_indexes()]

                if index_name not in existing_indexes:
                    st.info(f"Creating new index: {index_name}")
                    # Create index with cloud-based embedding
                    pc.create_index_for_model(
                        name=index_name,
                        model="text-embedding-ada-002",  # Using OpenAI's embedding model
                        dimension=1536,  # Dimension for the embedding model
                        metric="cosine",
                        spec=ServerlessSpec(
                            cloud="aws",
                            region="us-east-1"
                        )
                    )
                    st.info("Waiting for index to be ready...")
                    # Wait for the index to be ready
                    while True:
                        index_info = pc.describe_index(index_name)
                        if index_info.status.ready:
                            break
                        import time
                        time.sleep(1)

                # Get the index host
                index_info = pc.describe_index(index_name)
                index_host = index_info.host

                # Store the index host in session state
                st.session_state.index_host = index_host

                # Initialize the gRPC client for data operations
                grpc_client = Pinecone(api_key=pinecone_api_key)
                st.session_state.index = grpc_client.Index(host=index_host)

                # Store the Pinecone client in session state for later use
                st.session_state.pc = pc

                st.session_state.initialized = True
                st.success(f"Pinecone initialized successfully! Index host: {index_host}")
        except Exception as e:
            st.error(f"Error initializing Pinecone: {str(e)}")

# Process uploaded documents
if uploaded_files and st.session_state.initialized:
    with st.spinner("Processing documents..."):
        try:
            # Make sure we have access to the index
            if not st.session_state.index:
                st.error("Pinecone index not initialized. Please initialize Pinecone first.")
                st.stop()

            # Process each uploaded file
            all_chunks = []

            for uploaded_file in uploaded_files:
                # Create a temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as temp_file:
                    temp_file.write(uploaded_file.read())
                    temp_file_path = temp_file.name

                # Load document based on file type
                if uploaded_file.name.endswith('.pdf'):
                    loader = PyPDFLoader(temp_file_path)
                elif uploaded_file.name.endswith('.txt'):
                    loader = TextLoader(temp_file_path)
                else:
                    continue

                documents = loader.load()

                # Split documents
                text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
                split_docs = text_splitter.split_documents(documents)

                # Prepare data for Pinecone
                for doc in split_docs:
                    # Create a unique ID for each chunk
                    doc_id = str(uuid.uuid4())

                    # Add to chunks list - format as dictionary for gRPC client with empty values
                    # When using cloud-based embedding, we need to provide an empty values array
                    all_chunks.append({
                        "id": doc_id,
                        "text": doc.page_content,  # Empty values array, will be filled by Pinecone's cloud embedding
                    })

                # Clean up temp file
                os.unlink(temp_file_path)
            # print(all_chunks)
            if all_chunks:
                # Batch upsert to Pinecone
                batch_size = 100
                batches = chunker(all_chunks, batch_size)
                with st.spinner(f"Upserting {len(all_chunks)} document chunks to Pinecone..."):
                    # Process each batch
                    for i, batch in enumerate(batches):
                        st.write(f"Processing batch {i+1}/{len(batches)}...")
                        # Upsert the batch
                        st.session_state.index.upsert_records(
                            "rag-namespace",
                            batch,
                        )

                    st.write("All batches processed successfully!")

                st.session_state.documents_processed = True
                st.success(f"Processed and uploaded {len(all_chunks)} document chunks!")
            else:
                st.warning("No documents were processed. Please check your files.")

        except Exception as e:
            import traceback
            st.error(f"Error processing documents: {str(e)}")
            st.error(f"Traceback: {traceback.format_exc()}")
            # Debug information
            st.write("Debug information:")
            st.write(f"- Index initialized: {st.session_state.initialized}")
            st.write(f"- Index host: {st.session_state.index_host}")
            if all_chunks and len(all_chunks) > 0:
                st.write(f"- Sample chunk format: {all_chunks[0]}")

# Handle query
if submit_button and query and st.session_state.documents_processed:
    with st.spinner("Generating response..."):
        try:
            # Query Pinecone directly
            query_response = st.session_state.index.search(
                namespace="rag-namespace",
                query={
                    "inputs": {"text": query},
                    "top_k": 5
                },
                fields=["text"]
            )

            # Extract contexts from the query response
            contexts = []
            if 'result' in query_response and 'hits' in query_response['result']:
                for hit in query_response['result']['hits']:
                    if 'fields' in hit and 'text' in hit['fields']:
                        contexts.append(hit['fields']['text'])

            # Join contexts
            context_text = "\n\n".join(contexts)

            # Load LLM - using deepseek-70b from Groq
            llm = ChatGroq(
                model="deepseek-r1-distill-llama-70b",
                temperature=0.7,
                api_key=groq_api_key
            )

            # Create prompt
            prompt = f"""
            You are a helpful assistant that answers questions based on the provided context.
            Use the provided context to answer the question.

            Question: {query}

            Context: {context_text}

            Answer:
            """

            # Generate response
            response = llm.invoke(prompt)

            # Display response
            st.header("Response")
            st.write(response.content)

            # Display retrieved context
            with st.expander("View retrieved context"):
                for i, context in enumerate(contexts):
                    st.markdown(f"**Document {i+1}**")
                    st.write(context)
                    st.write("---")

        except Exception as e:
            import traceback
            st.error(f"Error generating response: {str(e)}")
            st.error(f"Traceback: {traceback.format_exc()}")
            # Debug information
            st.write("Debug information:")
            st.write(f"- Index initialized: {st.session_state.initialized}")
            st.write(f"- Documents processed: {st.session_state.documents_processed}")
            st.write(f"- Index host: {st.session_state.index_host}")
elif submit_button and query:
    if not st.session_state.initialized:
        st.warning("Please initialize Pinecone first.")
    elif not st.session_state.documents_processed:
        st.warning("Please upload and process documents first.")
elif submit_button:
    st.warning("Please enter a query.")
