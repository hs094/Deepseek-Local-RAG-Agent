import os
import bs4
import tempfile
# Start the server in a separate process
import subprocess
import threading
import time
import sys
from dotenv import load_dotenv
from datetime import datetime
from typing import List
import streamlit as st
from agno.agent import Agent
from agno.models.groq import Groq
from langchain_community.document_loaders import PyPDFLoader, WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
from langchain_core.embeddings import Embeddings
from agno.tools.exa import ExaTools
from agno.embedder.ollama import OllamaEmbedder

# Add the MCP module to the path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'drive_mcp'))

# Import the MCP module
try:
    from drive_mcp.gdrive import GoogleDriveClient
    from drive_mcp.pinecone_indexer import PineconeIndexer
except ImportError as e:
    # If the module is not found, we'll handle this gracefully
    print(f"Import error: {e}")
    GoogleDriveClient = None
    PineconeIndexer = None

load_dotenv()

# Constants
COLLECTION_NAME = "deepseek_rag"

class OllamaEmbedderr(Embeddings):
    def __init__(self, model_name="snowflake-arctic-embed"):
        """
        Initialize the OllamaEmbedderr with a specific model.

        Args:
            model_name (str): The name of the model to use for embedding.
        """
        self.embedder = OllamaEmbedder(id=model_name, dimensions=1024)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> List[float]:
        return self.embedder.get_embedding(text)


# Constants
COLLECTION_NAME = "test-deepseek-r1"

# Streamlit App Initialization
st.title("🐋 Deepseek RAG Reasoning Agent")

# Initialize the Google Drive client if available
@st.cache_resource
def get_gdrive_client():
    """Get or create a Google Drive client."""
    try:
        # Create the credentials directory if it doesn't exist
        os.makedirs('credentials', exist_ok=True)

        # Use custom paths for credentials and token files
        credentials_path = os.path.join('credentials', 'credentials.json')
        token_path = os.path.join('credentials', 'token.pickle')

        return GoogleDriveClient(
            credentials_file=credentials_path,
            token_pickle_file=token_path
        )
    except Exception as e:
        st.sidebar.error(f"Failed to initialize Google Drive client: {str(e)}")
        return None

# Session State Initialization
if 'google_api_key' not in st.session_state:
    st.session_state.google_api_key = os.getenv("GEMINI_API_KEY")
if 'pinecone_api_key' not in st.session_state:
    st.session_state.pinecone_api_key = os.getenv('PINECONE_API_KEY')
if 'pinecone_index_name' not in st.session_state:
    st.session_state.pinecone_index_name = os.getenv('PINECONE_INDEX_NAME', 'deepseek-rag')
if 'pinecone_manager' not in st.session_state:
    st.session_state.pinecone_manager = None
if 'use_model_based_index' not in st.session_state:
    st.session_state.use_model_based_index = False
if 'model_version' not in st.session_state:
    st.session_state.model_version = "deepseek-r1:1.5b"  # Default to lighter model
if 'vector_store' not in st.session_state:
    st.session_state.vector_store = None
if 'processed_documents' not in st.session_state:
    st.session_state.processed_documents = []
if 'history' not in st.session_state:
    st.session_state.history = []
if 'exa_api_key' not in st.session_state:
    st.session_state.exa_api_key = ""
if 'use_web_search' not in st.session_state:
    st.session_state.use_web_search = False
if 'force_web_search' not in st.session_state:
    st.session_state.force_web_search = False
if 'similarity_threshold' not in st.session_state:
    st.session_state.similarity_threshold = 0.7
if 'rag_enabled' not in st.session_state:
    st.session_state.rag_enabled = True  # RAG is enabled by default
if 'user_agent' not in st.session_state:
    st.session_state.user_agent = os.getenv('USER_AGENT', 'DeepseekLocalRAGAgent/0.1.0')
if 'exa_api_key' not in st.session_state:
    st.session_state.exa_api_key = os.getenv('EXA_API_KEY')
if 'use_groq' not in st.session_state:
    st.session_state.use_groq = True  # Always use Groq API
if 'groq_api_key' not in st.session_state:
    st.session_state.groq_api_key = os.getenv("GROQ_API_KEY", "")
if 'groq_model' not in st.session_state:
    st.session_state.groq_model = "deepseek-r1-distill-llama-70b"  # Default to specified Deepseek model
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False


# Document Processing Functions
def process_pdf(file, file_name=None) -> List:
    """Process PDF file and add source metadata.

    Args:
        file: Either a file object from st.file_uploader or a NamedTemporaryFile
        file_name: Optional file name to use (for Google Drive files)
    """
    try:
        # Handle different file types
        if hasattr(file, 'getvalue'):  # File from st.file_uploader
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(file.getvalue())
                file_path = tmp_file.name
                name = file.name
        elif hasattr(file, 'name'):  # NamedTemporaryFile
            file_path = file.name
            name = file_name or os.path.basename(file_path)
        else:
            st.error(f"📄 Unsupported file type: {type(file)}")
            return []
        # Load and process the PDF
        loader = PyPDFLoader(file_path)
        documents = loader.load()
        # Add source metadata
        for doc in documents:
            doc.metadata.update({
                "source_type": "pdf",
                "file_name": name,
                "timestamp": datetime.now().isoformat()
            })
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        return text_splitter.split_documents(documents)
    except Exception as e:
        st.error(f"📄 PDF processing error: {str(e)}")
        return []

def process_web(url: str) -> List:
    """Process web URL and add source metadata."""
    try:
        loader = WebBaseLoader(
            web_paths=(url,),
            bs_kwargs=dict(
                parse_only=bs4.SoupStrainer(
                    class_=("post-content", "post-title", "post-header", "content", "main")
                )
            )
        )
        documents = loader.load()
        # Add source metadata
        for doc in documents:
            doc.metadata.update({
                "source_type": "url",
                "url": url,
                "timestamp": datetime.now().isoformat()
            })
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        return text_splitter.split_documents(documents)
    except Exception as e:
        st.error(f"🌐 Web processing error: {str(e)}")
        return []

# Vector Store Management
def create_vector_store(texts):
    """Create and initialize vector store with documents."""
    try:
        # Make sure we have a Pinecone client
        if not st.session_state.pinecone_client:
            st.error("🔴 Pinecone client not initialized. Please initialize Pinecone first.")
            return None

        # Get the index from the Pinecone client
        index = st.session_state.pinecone_client.Index(st.session_state.pinecone_index_name)

        # Initialize vector store with the Pinecone index
        vector_store = PineconeVectorStore(
            index=index,
            embedding=OllamaEmbedderr()
        )

        # Add documents
        with st.spinner('📤 Uploading documents to Pinecone...'):
            vector_store.add_documents(texts)
            st.success("✅ Documents stored successfully!")
            return vector_store
    except Exception as e:
        st.error(f"🔴 Vector store error: {str(e)}")
        return None

def get_web_search_agent() -> Agent:
    """Initialize a web search agent using Groq API only."""
    # Always use Groq API with deepseek-r1-distill-llama-70b
    if not st.session_state.groq_api_key:
        st.error("⚠️ Groq API key is required. Please enter it in the sidebar.")
        return None

    model = Groq(
        api_key=st.session_state.groq_api_key,
        id="deepseek-r1-distill-llama-70b"  # Always use this specific model
    )
    return Agent(
        name="Web Search Agent",
        model=model,
        tools=[ExaTools(
            api_key=st.session_state.exa_api_key,
            include_domains=search_domains,
            num_results=5,
            user_agent=st.session_state.user_agent
        )],
        instructions="""You are a web search expert. Your task is to:
        1. Search the web for relevant information about the query
        2. Compile and summarize the most relevant information
        3. Include sources in your response

        IMPORTANT: When you need to think through a problem or analyze information, wrap your thinking process in <think></think> tags.
        This thinking will be shown to the user in a collapsible section. For example:

        <think>
        Let me analyze this question...
        The search results mention X, Y, and Z...
        Based on this information, I can conclude...
        </think>

        Then provide your final answer without the think tags. This will be shown directly to the user.
        """,
        show_tool_calls=True,
        markdown=True,
        stream=True,
    )

def get_rag_agent() -> Agent:
    """Initialize a RAG agent with Groq API only."""
    # Always use Groq API with deepseek-r1-distill-llama-70b
    if not st.session_state.groq_api_key:
        st.error("⚠️ Groq API key is required. Please enter it in the sidebar.")
        return None

    model = Groq(
        api_key=st.session_state.groq_api_key,
        id="deepseek-r1-distill-llama-70b"  # Always use this specific model
    )
    model_info = "Groq (deepseek-r1-distill-llama-70b)"
    # Create and return the agent
    st.info(f"🤖 Using {model_info} for reasoning")
    return Agent(
        name="RAG Reasoning Agent",
        model=model,
        instructions="""You are a helpful AI assistant with access to documents and web search.
        When answering questions:
        1. Use the provided context when available
        2. Cite sources when referencing specific information
        3. If the context doesn't contain relevant information, say so
        4. Use your general knowledge for common questions

        IMPORTANT: When you need to think through a problem or analyze information, wrap your thinking process in <think></think> tags.
        This thinking will be shown to the user in a collapsible section. For example:

        <think>
        Let me analyze this question...
        The context mentions X, Y, and Z...
        Based on this information, I can conclude...
        </think>

        Then provide your final answer without the think tags. This will be shown directly to the user.
        """,
        show_tool_calls=False,
        markdown=True,
        stream=True,
    )

def check_document_relevance(query: str, vector_store, threshold: float = 0.7) -> tuple[bool, List]:
    if not vector_store:
        return False, []
    retriever = vector_store.as_retriever(
        search_type="similarity_score_threshold",
        search_kwargs={"k": 5, "score_threshold": threshold}
    )
    docs = retriever.invoke(query)
    return bool(docs), docs

# Sidebar Configuration
st.sidebar.header("🤖 Agent Configuration")

# Google Drive Login
st.sidebar.header("🔐 Google Drive Access")

# Try to get the Google Drive client
try:
    gdrive_client = get_gdrive_client()
except Exception as e:
    st.sidebar.error(f"Error initializing Google Drive client: {str(e)}")
    gdrive_client = None

# Only show Google Drive login if the client is available
if gdrive_client:
    try:
        # Allow user to upload credentials.json if it doesn't exist
        if not gdrive_client.credentials_exist():
            st.sidebar.info("Please upload your Google API credentials file (credentials.json)")
            st.sidebar.caption("You can get this from the Google Cloud Console")
            uploaded_file = st.sidebar.file_uploader("Upload credentials.json", type="json", key="credentials_uploader")

            if uploaded_file is not None:
                try:
                    # Save the uploaded file
                    gdrive_client.save_credentials_file(uploaded_file.getbuffer())
                    st.sidebar.success("Credentials file uploaded successfully!")
                    # Force a rerun to update the UI
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Error saving credentials: {str(e)}")

        # Login button in sidebar
        if gdrive_client.credentials_exist() and not st.session_state.authenticated:
            st.sidebar.subheader("Authentication")
            st.sidebar.write("Click the button below to authenticate with Google Drive.")

            if st.sidebar.button("Login to Google Drive", use_container_width=True, key="gdrive_login"):
                with st.spinner("Authenticating..."):
                    try:
                        authenticated = gdrive_client.authenticate()
                        if authenticated:
                            st.session_state.authenticated = True
                            st.rerun()
                        else:
                            st.sidebar.error("Authentication failed. Please check your credentials.")
                    except Exception as e:
                        st.sidebar.error(f"Authentication error: {str(e)}")

        # Show authentication status
        if st.session_state.authenticated:
            st.sidebar.success("✅ Connected to Google Drive")
    except Exception as e:
        st.sidebar.error(f"Error with Google Drive integration: {str(e)}")
else:
    st.sidebar.warning("Google Drive integration not available. Make sure the MCP module is properly installed.")

# Utility Functions
def init_pinecone():
    """Initialize Pinecone client."""
    try:
        # Check if we have the required credentials
        if not st.session_state.pinecone_api_key:
            st.error("🔴 Pinecone API key is missing. Please add it to your .env file.")
            return None

        # Initialize Pinecone with the new API
        pc = Pinecone(
            api_key=st.session_state.pinecone_api_key
        )

        # Store the Pinecone client in session state for later use
        st.session_state.pinecone_client = pc

        # Check if the index exists, create it if it doesn't
        index_name = st.session_state.pinecone_index_name
        if index_name not in [idx.name for idx in pc.list_indexes()]:
            st.info(f"📚 Creating new Pinecone index: {index_name}")

            # Create the index with ServerlessSpec
            pc.create_index(
                name=index_name,
                dimension=1024,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region="us-east-1"
                )
            )
            st.success(f"✅ Created Pinecone index: {index_name}")

        return True
    except Exception as e:
        st.error(f"🔴 Pinecone initialization failed: {str(e)}")
        return None

# File/URL Upload Section - Moved here to be just below Google Drive Login
if st.session_state.rag_enabled:
    pinecone_initialized = init_pinecone()

    st.sidebar.header("📁 Data Upload")
    upload_tab, gdrive_tab = st.sidebar.tabs(["Local Upload", "Google Drive"])

    with upload_tab:
        uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])
        web_url = st.text_input("Or enter URL")

    with gdrive_tab:
        if not gdrive_client:
            st.warning("Google Drive integration is not available. Please check the error messages above.")
        elif not st.session_state.authenticated:
            st.info("Please authenticate with Google Drive using the login section above.")
        else:
            # Get the OAuth token from the Google Drive client
            oauth_token = None
            try:
                # Use the method to get the access token
                oauth_token = gdrive_client.get_access_token()
                if not oauth_token:
                    st.warning("Failed to get OAuth token from credentials")
                    # Try to re-authenticate
                    with st.spinner("Attempting to re-authenticate..."):
                        try:
                            if gdrive_client.authenticate():
                                oauth_token = gdrive_client.get_access_token()
                                if oauth_token:
                                    st.success("OAuth token obtained after re-authentication")
                                else:
                                    st.error("Still unable to get OAuth token after re-authentication")
                            else:
                                st.error("Re-authentication failed")
                        except Exception as e:
                            st.error(f"Re-authentication error: {str(e)}")
            except Exception as e:
                st.error(f"Error getting OAuth token: {str(e)}")
                st.info("Try logging out and logging back in to refresh your authentication.")

            # Create the Google Drive Picker popup
            if oauth_token:
                # These should be set to your actual values from Google Cloud Console
                api_key = os.getenv('GOOGLE_API_KEY', '')
                app_id = os.getenv('GOOGLE_APP_ID', '')
                if not api_key or not app_id:
                    st.error("Missing Google API key or App ID. Please set GOOGLE_API_KEY and GOOGLE_APP_ID in your .env file.")
                else:
                    # Display instructions with more detailed guidance
                    st.info("Click the button below to open Google Drive Picker in a popup window. Only PDF files will be processed.")

                    # Add a note about authentication status
                    st.success("✅ Authentication successful! You can now select files from Google Drive.")

                # Create a button to open the popup
                if st.button("Open Google Drive Picker", key="open_gdrive_picker"):

                    # Kill any existing server processes (if psutil is available)
                    try:
                        # Try to import psutil, but don't fail if it's not available
                        try:
                            import psutil
                            has_psutil = True
                        except ImportError:
                            has_psutil = False
                            print("psutil not installed, skipping process cleanup")
                            print("To install psutil, run: pip install psutil")
                            st.info("For better process management, install psutil: `pip install psutil`")

                        if has_psutil:
                            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                                if proc.info['name'] == 'python' and 'serve_picker.py' in ' '.join(proc.info['cmdline'] or []):
                                    print(f"Killing existing server process: {proc.info['pid']}")
                                    psutil.Process(proc.info['pid']).terminate()
                    except Exception as e:
                        print(f"Error cleaning up processes: {e}")
                        st.warning(f"Error cleaning up processes: {e}")

                    # Start the server process
                    server_process = subprocess.Popen(
                        ["python", "serve_picker.py", "--token", oauth_token, "--api-key", api_key, "--app-id", app_id],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=1
                    )

                    # Function to monitor the server output
                    def monitor_server_output():
                        while True:
                            line = server_process.stdout.readline()
                            if not line and server_process.poll() is not None:
                                break
                            if line:
                                print(f"Server: {line.strip()}")

                        # Check for errors
                        for line in server_process.stderr:
                            print(f"Server error: {line.strip()}")

                    # Start the monitoring in a separate thread
                    thread = threading.Thread(target=monitor_server_output)
                    thread.daemon = True  # Make the thread exit when the main program exits
                    thread.start()

                    # Wait a moment for the server to start
                    time.sleep(1)

                    # Show a message to the user
                    st.info("Opening Google Drive Picker in a new window. Please allow popups if prompted.")

                    # Add JavaScript to handle messages from the popup
                    js_code = """
                    <script>
                    // Function to handle messages from the popup
                    function handleMessage(event) {
                        if (event.data && event.data.type === 'google-drive-files') {
                            const files = event.data.files;
                            console.log('Selected files:', files);

                            // Store the selected files in a hidden element
                            const hiddenElement = document.createElement('div');
                            hiddenElement.id = 'selected-gdrive-files';
                            hiddenElement.style.display = 'none';
                            hiddenElement.setAttribute('data-files', JSON.stringify(files));
                            document.body.appendChild(hiddenElement);

                            // Trigger a custom event that Streamlit can listen for
                            const customEvent = new CustomEvent('gdrive-files-selected', { detail: files });
                            document.dispatchEvent(customEvent);

                            // Reload the page to process the files
                            setTimeout(() => {
                                window.location.reload();
                            }, 1000);
                        }
                    }

                    // Add event listener for messages from the popup
                    window.addEventListener('message', handleMessage);
                    </script>
                    """
                    st.components.v1.html(js_code, height=0)

                    # Display a notification that files have been selected
                    import glob
                    import json

                    # Find the most recent JSON file in the temp directory
                    temp_dir = tempfile.gettempdir()
                    json_files = glob.glob(os.path.join(temp_dir, '*.json'))

                    if json_files:
                        # Sort by modification time (newest first)
                        json_files.sort(key=os.path.getmtime, reverse=True)

                        # Try to load each file until we find one with valid Google Drive files
                        selected_files = None
                        for json_file in json_files:
                            try:
                                with open(json_file, 'r') as f:
                                    data = json.load(f)
                                    # Check if this looks like Google Drive files
                                    if isinstance(data, list) and len(data) > 0 and 'id' in data[0] and 'mimeType' in data[0]:
                                        # Check if this file was processed recently (within the last 5 seconds)
                                        file_mod_time = os.path.getmtime(json_file)
                                        if time.time() - file_mod_time < 5:  # 5 seconds threshold
                                            selected_files = data
                                            st.success(f"Found {len(selected_files)} file(s) selected from Google Drive")
                                            st.info("Click the 'Index Selected Files in Pinecone' button below to process and index these files.")
                                            break
                            except Exception as e:
                                print(f"Error loading {json_file}: {str(e)}")

                # Add a button to manually initiate indexing
                if st.button("Index Selected Files in Pinecone", key="manual_index_button"):
                    # Look for selected files in temporary files
                    import glob
                    import json

                    # Find the most recent JSON file in the temp directory
                    temp_dir = tempfile.gettempdir()
                    json_files = glob.glob(os.path.join(temp_dir, '*.json'))

                    if json_files:
                        # Sort by modification time (newest first)
                        json_files.sort(key=os.path.getmtime, reverse=True)

                        # Try to load each file until we find one with valid Google Drive files
                        selected_files = None
                        for json_file in json_files:
                            try:
                                with open(json_file, 'r') as f:
                                    data = json.load(f)
                                    # Check if this looks like Google Drive files
                                    if isinstance(data, list) and len(data) > 0 and 'id' in data[0] and 'mimeType' in data[0]:
                                        selected_files = data
                                        st.success(f"Found {len(selected_files)} file(s) selected from Google Drive")
                                        break
                            except Exception as e:
                                print(f"Error loading {json_file}: {str(e)}")

                        if selected_files and pinecone_initialized:
                            with st.spinner("Indexing selected files in Pinecone..."):
                                try:
                                    # Check if PineconeIndexer is available
                                    if PineconeIndexer is None:
                                        st.error("PineconeIndexer module is not available. Please check your installation.")
                                        st.info("Falling back to manual processing...")

                                        # Process each file (PDF or text) manually
                                        processed_count = 0
                                        for file in selected_files:
                                            mime_type = file.get('mimeType', '')
                                            print(mime_type)
                                            is_pdf = mime_type == 'application/pdf'
                                            is_text = mime_type == 'text/plain' or 'text' in mime_type
                                            is_doc = 'document' in mime_type or 'officedocument' in mime_type

                                            if is_pdf or is_text or is_doc:
                                                try:
                                                    with st.spinner(f"Processing {file['name']}..."):
                                                        # Get the file content using the Google Drive client
                                                        file_id = file['id']
                                                        file_content = gdrive_client.get_file_content(file_id)

                                                        # Determine file type and process accordingly
                                                        if is_pdf:
                                                            # Process as PDF
                                                            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                                                                tmp_file.write(file_content.getvalue())
                                                                texts = process_pdf(tmp_file, file_name=file['name'])
                                                        elif is_text:
                                                            # Process as text file
                                                            with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as tmp_file:
                                                                tmp_file.write(file_content.getvalue())
                                                                # Use the existing process_web function to handle text
                                                                # This is a workaround since we don't have a dedicated text processor
                                                                texts = []
                                                                try:
                                                                    from langchain_community.document_loaders import TextLoader
                                                                    loader = TextLoader(tmp_file.name)
                                                                    documents = loader.load()
                                                                    # Add metadata
                                                                    for doc in documents:
                                                                        doc.metadata.update({
                                                                            "source_type": "text",
                                                                            "file_name": file['name'],
                                                                            "timestamp": datetime.now().isoformat()
                                                                        })
                                                                    # Split text
                                                                    text_splitter = RecursiveCharacterTextSplitter(
                                                                        chunk_size=1000,
                                                                        chunk_overlap=200
                                                                    )
                                                                    texts = text_splitter.split_documents(documents)
                                                                except Exception as text_error:
                                                                    st.error(f"Error processing text file: {str(text_error)}")
                                                        elif is_doc:
                                                            # Try to process as text for document files
                                                            st.info(f"Attempting to process document file: {file['name']} as text")
                                                            with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as tmp_file:
                                                                tmp_file.write(file_content.getvalue())
                                                                # Try to extract text from the document
                                                                try:
                                                                    from langchain_community.document_loaders import TextLoader
                                                                    loader = TextLoader(tmp_file.name)
                                                                    documents = loader.load()
                                                                    # Add metadata
                                                                    for doc in documents:
                                                                        doc.metadata.update({
                                                                            "source_type": "document",
                                                                            "file_name": file['name'],
                                                                            "timestamp": datetime.now().isoformat()
                                                                        })
                                                                    # Split text
                                                                    text_splitter = RecursiveCharacterTextSplitter(
                                                                        chunk_size=1000,
                                                                        chunk_overlap=200
                                                                    )
                                                                    texts = text_splitter.split_documents(documents)
                                                                except Exception as doc_error:
                                                                    st.warning(f"Could not process document as text: {str(doc_error)}")
                                                                    texts = []

                                                        # Add to vector store if we have texts
                                                        if texts and pinecone_initialized:
                                                            if st.session_state.vector_store:
                                                                st.session_state.vector_store.add_documents(texts)
                                                            else:
                                                                st.session_state.vector_store = create_vector_store(texts)
                                                            st.session_state.processed_documents.append(file['name'])
                                                            st.success(f"✅ Added file: {file['name']}")
                                                            processed_count += 1
                                                except Exception as e:
                                                    st.error(f"Error processing file from Google Drive: {str(e)}")
                                                    import traceback
                                                    st.error(f"Traceback: {traceback.format_exc()}")
                                            else:
                                                st.warning(f"Skipped unsupported file type: {mime_type} - {file['name']}")

                                        # Add a visual indicator after all files are processed
                                        if processed_count > 0:
                                            st.markdown("""
                                            <div style="background-color: #d4edda; color: #155724; padding: 15px; border-radius: 5px; margin-top: 10px; text-align: center;">
                                                <h3 style="margin: 0;">✅ Pinecone Index Updated</h3>
                                                <p style="margin: 10px 0 0 0;">Your files have been successfully indexed and are ready for RAG chat.</p>
                                            </div>
                                            """, unsafe_allow_html=True)
                                    else:
                                        # Initialize the Pinecone indexer with local embeddings
                                        indexer = PineconeIndexer(
                                            pinecone_client=st.session_state.pinecone_client,
                                            index_name=st.session_state.pinecone_index_name,
                                            namespace="rag-namespace",
                                            chunk_size=500,
                                            chunk_overlap=50,
                                            embedding_model="snowflake-arctic-embed"  # Use local embedding model
                                        )

                                        # Index the files
                                        results = indexer.index_files(selected_files, gdrive_client)

                                        # Update the processed documents list
                                        for file_name in results["processed_files_list"]:
                                            if file_name not in st.session_state.processed_documents:
                                                st.session_state.processed_documents.append(file_name)

                                        # Show results
                                        st.success(f"✅ Indexed {results['processed_files']} files with {results['total_chunks']} chunks in Pinecone")
                                        if results["skipped_files"] > 0:
                                            st.info(f"ℹ️ Skipped {results['skipped_files']} unsupported files")

                                        # Initialize vector store if needed
                                        if not st.session_state.vector_store:
                                            index = st.session_state.pinecone_client.Index(st.session_state.pinecone_index_name)
                                            st.session_state.vector_store = PineconeVectorStore(
                                                index=index,
                                                embedding=OllamaEmbedderr()
                                            )

                                        # Notification that files are ready for search
                                        st.success("🔍 Files are now indexed and ready for search!")

                                        # Add a visual indicator
                                        st.markdown("""
                                        <div style="background-color: #d4edda; color: #155724; padding: 15px; border-radius: 5px; margin-top: 10px; text-align: center;">
                                            <h3 style="margin: 0;">✅ Pinecone Index Updated</h3>
                                            <p style="margin: 10px 0 0 0;">Your files have been successfully indexed and are ready for RAG chat.</p>
                                        </div>
                                        """, unsafe_allow_html=True)

                                except Exception as e:
                                    st.error(f"Error indexing files: {str(e)}")
                                    import traceback
                                    st.error(f"Traceback: {traceback.format_exc()}")
                        else:
                            if not selected_files:
                                st.warning("No selected files found. Please select files from Google Drive first.")
                            elif not pinecone_initialized:
                                st.error("Pinecone is not initialized. Please initialize Pinecone first.")
                    else:
                        st.warning("No selected files found. Please select files from Google Drive first.")

                # Add instructions for using the Google Drive Picker
                st.info("""
                **Instructions:**
                1. Click the "Open Google Drive Picker" button to select files from Google Drive
                2. Select PDF or text files in the popup window
                3. Click "Confirm Selection" in the popup
                4. Click the "Index Selected Files in Pinecone" button to process and index your files
                5. Once indexed, the files will be ready for RAG chat
                """)

                # Add instructions for troubleshooting
                with st.expander("Troubleshooting Tips"):
                    st.markdown("""
                    1. If the popup is blocked, please allow popups for this site
                    2. Make sure you've set the correct API key and App ID in your .env file
                    3. Ensure your Google Cloud project has the Google Drive API and Picker API enabled
                    4. If the popup doesn't open, try running the server manually: `python serve_picker.py --serve-only`
                    5. If you still have issues, check the browser console for error messages (F12 or right-click > Inspect > Console)
                    """)
                # else:
                    # st.warning("OAuth token not available. Please re-authenticate with Google Drive.")
            else:
                st.info("Please login to Google Drive to select files.")

# RAG Mode Toggle
st.sidebar.header("🔍 RAG Configuration")
st.session_state.rag_enabled = st.sidebar.toggle("Enable RAG Mode", value=st.session_state.rag_enabled)

# Add a button to initiate chunking and pushing to Pinecone
if st.session_state.rag_enabled:
    st.sidebar.header("🔄 Index Management")

    # Initialize a session state variable to track indexing status if it doesn't exist
    if 'indexing_status' not in st.session_state:
        st.session_state.indexing_status = None

    # Display the current indexing status if available
    if st.session_state.indexing_status:
        if st.session_state.indexing_status == "success":
            st.sidebar.success("✅ Documents successfully indexed in Pinecone!")
        elif st.session_state.indexing_status == "error":
            st.sidebar.error("❌ Error occurred during indexing. Please try again.")
        elif st.session_state.indexing_status == "in_progress":
            st.sidebar.info("⏳ Indexing in progress...")

    # Button to initiate chunking and pushing to Pinecone
    if st.sidebar.button("🚀 Process & Index Documents", help="Chunk documents and push to Pinecone index"):
        if not st.session_state.processed_documents:
            st.sidebar.warning("⚠️ No documents to index. Please upload or select documents first.")
        elif not pinecone_initialized:
            st.sidebar.error("❌ Pinecone not initialized. Please check your API key.")
        else:
            try:
                st.session_state.indexing_status = "in_progress"
                st.sidebar.info("⏳ Processing and indexing documents...")
                st.rerun()  # Rerun to show the in-progress status
            except Exception as e:
                st.session_state.indexing_status = "error"
                st.sidebar.error(f"❌ Error: {str(e)}")

# Clear Chat Button
if st.sidebar.button("🗑️ Clear Chat History"):
    st.session_state.history = []
    st.rerun()

# Show API Configuration only if RAG is enabled
if st.session_state.rag_enabled:
    # Search Configuration (only shown in RAG mode)
    st.sidebar.header("🎯 Search Configuration")
    st.session_state.similarity_threshold = st.sidebar.slider(
        "Document Similarity Threshold",
        min_value=0.0,
        max_value=1.0,
        value=0.7,
        help="Lower values will return more documents but might be less relevant. Higher values are more strict."
    )

# Add this in the sidebar configuration section after the RAG toggle
# st.sidebar.header("🧠 Model Configuration")

# Force use_groq to always be True
st.session_state.use_groq = True
# st.sidebar.info("Using Deepseek via Groq API")

# # Groq configuration
# st.session_state.groq_api_key = st.sidebar.text_input(
#     "Groq API Key",
#     type="password",
#     value=st.session_state.groq_api_key
# )
# st.sidebar.caption("Using deepseek-r1-distill-llama-70b via Groq API")
# Set the model to always be deepseek-r1-distill-llama-70b
st.session_state.groq_model = "deepseek-r1-distill-llama-70b"  # Default to specified Deepseek model

st.sidebar.header("🌐 Web Search Configuration")
st.session_state.use_web_search = st.sidebar.checkbox("Enable Web Search Fallback", value=st.session_state.use_web_search)

if st.session_state.use_web_search:
    # Optional domain filtering
    default_domains = ["arxiv.org", "wikipedia.org", "github.com", "medium.com"]
    custom_domains = st.sidebar.text_input(
        "Custom domains (comma-separated)",
        value=",".join(default_domains),
        help="Enter domains to search from, e.g.: arxiv.org,wikipedia.org"
    )
    search_domains = [d.strip() for d in custom_domains.split(",") if d.strip()]

# Search Configuration moved inside RAG mode check

# st.sidebar.header("🗄️ Vector Database Configuration")
# st.sidebar.info("Using Pinecone")
# No need to force any settings here as we're using Pinecone


# Check if RAG is enabled
if st.session_state.rag_enabled:
    # Initialize Pinecone for document processing
    pinecone_initialized = init_pinecone()

    # Process documents
    if uploaded_file:
        file_name = uploaded_file.name
        if file_name not in st.session_state.processed_documents:
            with st.spinner('Processing PDF...'):
                texts = process_pdf(uploaded_file)
                if texts and pinecone_initialized:
                    if st.session_state.vector_store:
                        st.session_state.vector_store.add_documents(texts)
                    else:
                        st.session_state.vector_store = create_vector_store(texts)
                    st.session_state.processed_documents.append(file_name)
                    st.success(f"✅ Added PDF: {file_name}")

    if web_url:
        if web_url not in st.session_state.processed_documents:
            with st.spinner('Processing URL...'):
                texts = process_web(web_url)
                if texts and pinecone_initialized:
                    if st.session_state.vector_store:
                        st.session_state.vector_store.add_documents(texts)
                    else:
                        st.session_state.vector_store = create_vector_store(texts)
                    st.session_state.processed_documents.append(web_url)
                    st.success(f"✅ Added URL: {web_url}")

    # Display sources in sidebar
    if st.session_state.processed_documents:
        st.sidebar.header("📚 Processed Sources")
        for source in st.session_state.processed_documents:
            if source.endswith('.pdf'):
                st.sidebar.text(f"📄 {source}")
            else:
                st.sidebar.text(f"🌐 {source}")

# Place chat input at the bottom of the window
chat_col, toggle_col = st.columns([0.9, 0.1])

with chat_col:
    prompt = st.chat_input("Ask about your documents..." if st.session_state.rag_enabled else "Ask me anything...")

with toggle_col:
    st.session_state.force_web_search = st.toggle('🌐', help="Force web search")

if prompt:
    # Add user message to history
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    if st.session_state.rag_enabled:

            # Existing RAG flow remains unchanged
            with st.spinner("🤔Evaluating the Query..."):
                try:
                    rewritten_query = prompt

                    with st.expander("Evaluating the query"):
                        st.write(f"User's Prompt: {prompt}")
                except Exception as e:
                    st.error(f"❌ Error rewriting query: {str(e)}")
                    rewritten_query = prompt

            # Step 2: Choose search strategy based on force_web_search toggle
            context = ""
            docs = []
            if not st.session_state.force_web_search:
                # Try document search first using MCP's PineconeIndexer
                try:
                    # Initialize the Pinecone indexer for retrieval
                    if 'pinecone_indexer' not in st.session_state or st.session_state.pinecone_indexer is None:
                        st.session_state.pinecone_indexer = PineconeIndexer(
                            pinecone_client=st.session_state.pinecone_client,
                            index_name=st.session_state.pinecone_index_name,
                            namespace="rag-namespace",
                            embedding_model="snowflake-arctic-embed"
                        )

                    # Use the indexer to retrieve documents
                    with st.spinner("🔍 Searching documents..."):
                        docs = st.session_state.pinecone_indexer.retrieve_as_langchain_docs(
                            query=rewritten_query,
                            top_k=5,
                            score_threshold=st.session_state.similarity_threshold
                        )

                        if docs:
                            context = "\n\n".join([d.page_content for d in docs])
                            st.info(f"📊 Found {len(docs)} relevant documents (similarity > {st.session_state.similarity_threshold})")
                        elif st.session_state.use_web_search:
                            st.info("🔄 No relevant documents found in database, falling back to web search...")
                except Exception as e:
                    st.error(f"❌ Error retrieving documents: {str(e)}")
                    # Fallback to traditional vector store if available
                    if st.session_state.vector_store:
                        st.info("Falling back to traditional vector store...")
                        retriever = st.session_state.vector_store.as_retriever(
                            search_type="similarity_score_threshold",
                            search_kwargs={
                                "k": 5,
                                "score_threshold": st.session_state.similarity_threshold
                            }
                        )
                        docs = retriever.invoke(rewritten_query)
                        if docs:
                            context = "\n\n".join([d.page_content for d in docs])
                            st.info(f"📊 Found {len(docs)} relevant documents (similarity > {st.session_state.similarity_threshold})")
                        elif st.session_state.use_web_search:
                            st.info("🔄 No relevant documents found in database, falling back to web search...")

            # Step 3: Use web search if:
            # 1. Web search is forced ON via toggle, or
            # 2. No relevant documents found AND web search is enabled in settings
            if (st.session_state.force_web_search or not context) and st.session_state.use_web_search and st.session_state.exa_api_key:
                with st.spinner("🔍 Searching the web..."):
                    try:
                        web_search_agent = get_web_search_agent()
                        # Handle streaming response from web search agent
                        response_generator = web_search_agent.run(rewritten_query)
                        web_results = ""

                        # Check if we got a generator (streaming) or a regular response
                        if hasattr(response_generator, '__iter__') and not hasattr(response_generator, 'content'):
                            # It's a generator - collect chunks
                            for chunk in response_generator:
                                if isinstance(chunk, str):
                                    web_results += chunk
                                elif hasattr(chunk, 'content'):
                                    web_results += chunk.content
                        else:
                            # It's a regular response object
                            if hasattr(response_generator, 'content'):
                                web_results = response_generator.content
                            else:
                                web_results = str(response_generator)
                        if web_results:
                            context = f"Web Search Results:\n{web_results}"
                            if st.session_state.force_web_search:
                                st.info("ℹ️ Using web search as requested via toggle.")
                            else:
                                st.info("ℹ️ Using web search as fallback since no relevant documents were found.")
                    except Exception as e:
                        st.error(f"❌ Web search error: {str(e)}")

            # Step 4: Generate response using the RAG agent
            with st.spinner("🤖 Thinking..."):
                try:
                    rag_agent = get_rag_agent()

                    if context:
                        full_prompt = f"""Context: {context}

Original Question: {prompt}
Please provide a comprehensive answer based on the available information."""
                    else:
                        full_prompt = f"Original Question: {prompt}\n"
                        st.info("ℹ️ No relevant information found in documents or web search.")

                    # Create a placeholder for the streaming response
                    with st.chat_message("assistant"):
                        response_placeholder = st.empty()
                        thinking_placeholder = st.empty()

                        # Collect the full response from the streaming generator
                        full_response = ""
                        response_generator = rag_agent.run(full_prompt)

                        # Check if we got a generator (streaming) or a regular response
                        if hasattr(response_generator, '__iter__') and not hasattr(response_generator, 'content'):
                            # It's a generator - collect chunks
                            for chunk in response_generator:
                                if isinstance(chunk, str):
                                    full_response += chunk
                                elif hasattr(chunk, 'content'):
                                    full_response += chunk.content

                                # Extract thinking and final response on-the-fly
                                import re
                                think_pattern = r'<think>(.*?)</think>'
                                think_match = re.search(think_pattern, full_response, re.DOTALL)

                                if think_match:
                                    thinking_process = think_match.group(1).strip()
                                    current_final_response = re.sub(think_pattern, '', full_response, flags=re.DOTALL).strip()

                                    # Update the thinking expander if there's thinking content
                                    with thinking_placeholder.container():
                                        with st.expander("🤔 See thinking process"):
                                            st.markdown(thinking_process)
                                else:
                                    thinking_process = None
                                    current_final_response = full_response

                                # Update the response in real-time
                                response_placeholder.markdown(current_final_response)
                        else:
                            # It's a regular response object
                            if hasattr(response_generator, 'content'):
                                full_response = response_generator.content
                            else:
                                full_response = str(response_generator)

                            # Process the response
                            think_pattern = r'<think>(.*?)</think>'
                            think_match = re.search(think_pattern, full_response, re.DOTALL)

                            if think_match:
                                thinking_process = think_match.group(1).strip()
                                current_final_response = re.sub(think_pattern, '', full_response, flags=re.DOTALL).strip()

                                # Show thinking in expander
                                with thinking_placeholder.container():
                                    with st.expander("🤔 See thinking process"):
                                        st.markdown(thinking_process)
                            else:
                                thinking_process = None
                                current_final_response = full_response

                            # Display the final response
                            response_placeholder.markdown(current_final_response)

                        # Final extraction of thinking and response after streaming is complete
                        think_match = re.search(think_pattern, full_response, re.DOTALL)
                        if think_match:
                            thinking_process = think_match.group(1).strip()
                            final_response = re.sub(think_pattern, '', full_response, flags=re.DOTALL).strip()
                        else:
                            thinking_process = None
                            final_response = full_response

                        # Add assistant response to history (only the final response)
                        st.session_state.history.append({
                            "role": "assistant",
                            "content": final_response
                        })

                        # Show sources if available
                        if not st.session_state.force_web_search and 'docs' in locals() and docs:
                            with st.expander("🔍 See document sources"):
                                for i, doc in enumerate(docs, 1):
                                    source_type = doc.metadata.get("source_type", "unknown")
                                    source_icon = "📄" if source_type == "pdf" else "🌐"
                                    source_name = doc.metadata.get("file_name" if source_type == "pdf" else "url", "unknown")
                                    st.write(f"{source_icon} Source {i} from {source_name}:")
                                    st.write(f"{doc.page_content[:200]}...")

                except Exception as e:
                    st.error(f"❌ Error generating response: {str(e)}")

    else:
        # Simple mode without RAG
        with st.spinner("🤖 Thinking..."):
            try:
                rag_agent = get_rag_agent()
                web_search_agent = get_web_search_agent() if st.session_state.use_web_search else None

                # Handle web search if forced or enabled
                context = ""
                if st.session_state.force_web_search and web_search_agent:
                    with st.spinner("🔍 Searching the web..."):
                        try:
                            # Handle streaming response from web search agent
                            response_generator = web_search_agent.run(prompt)
                            web_results = ""

                            # Check if we got a generator (streaming) or a regular response
                            if hasattr(response_generator, '__iter__') and not hasattr(response_generator, 'content'):
                                # It's a generator - collect chunks
                                for chunk in response_generator:
                                    if isinstance(chunk, str):
                                        web_results += chunk
                                    elif hasattr(chunk, 'content'):
                                        web_results += chunk.content
                            else:
                                # It's a regular response object
                                if hasattr(response_generator, 'content'):
                                    web_results = response_generator.content
                                else:
                                    web_results = str(response_generator)
                            if web_results:
                                context = f"Web Search Results:\n{web_results}"
                                st.info("ℹ️ Using web search as requested.")
                        except Exception as e:
                            st.error(f"❌ Web search error: {str(e)}")

                # Generate response
                if context:
                    full_prompt = f"""Context: {context}

Question: {prompt}

Please provide a comprehensive answer based on the available information."""
                else:
                    full_prompt = prompt

                # Create a placeholder for the streaming response
                with st.chat_message("assistant"):
                    response_placeholder = st.empty()
                    thinking_placeholder = st.empty()

                    # Collect the full response from the streaming generator
                    full_response = ""
                    response_generator = rag_agent.run(full_prompt)

                    # Check if we got a generator (streaming) or a regular response
                    if hasattr(response_generator, '__iter__') and not hasattr(response_generator, 'content'):
                        # It's a generator - collect chunks
                        for chunk in response_generator:
                            if isinstance(chunk, str):
                                full_response += chunk
                            elif hasattr(chunk, 'content'):
                                full_response += chunk.content

                            # Extract thinking and final response on-the-fly
                            import re
                            think_pattern = r'<think>(.*?)</think>'
                            think_match = re.search(think_pattern, full_response, re.DOTALL)

                            if think_match:
                                thinking_process = think_match.group(1).strip()
                                current_final_response = re.sub(think_pattern, '', full_response, flags=re.DOTALL).strip()

                                # Update the thinking expander if there's thinking content
                                with thinking_placeholder.container():
                                    with st.expander("🤔 See thinking process"):
                                        st.markdown(thinking_process)
                            else:
                                thinking_process = None
                                current_final_response = full_response

                            # Update the response in real-time
                            response_placeholder.markdown(current_final_response)
                    else:
                        # It's a regular response object
                        if hasattr(response_generator, 'content'):
                            full_response = response_generator.content
                        else:
                            full_response = str(response_generator)

                        # Process the response
                        think_pattern = r'<think>(.*?)</think>'
                        think_match = re.search(think_pattern, full_response, re.DOTALL)

                        if think_match:
                            thinking_process = think_match.group(1).strip()
                            current_final_response = re.sub(think_pattern, '', full_response, flags=re.DOTALL).strip()

                            # Show thinking in expander
                            with thinking_placeholder.container():
                                with st.expander("🤔 See thinking process"):
                                    st.markdown(thinking_process)
                        else:
                            thinking_process = None
                            current_final_response = full_response

                        # Display the final response
                        response_placeholder.markdown(current_final_response)

                    # Final extraction of thinking and response after streaming is complete
                    think_match = re.search(think_pattern, full_response, re.DOTALL)
                    if think_match:
                        thinking_process = think_match.group(1).strip()
                        final_response = re.sub(think_pattern, '', full_response, flags=re.DOTALL).strip()
                    else:
                        thinking_process = None
                        final_response = full_response

                    # Add assistant response to history (only the final response)
                    st.session_state.history.append({
                        "role": "assistant",
                        "content": final_response
                    })

            except Exception as e:
                st.error(f"❌ Error generating response: {str(e)}")