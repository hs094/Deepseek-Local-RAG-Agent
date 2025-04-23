# Deepseek Local RAG Agent

A Streamlit-based application that provides a Retrieval-Augmented Generation (RAG) system using Deepseek models via Groq API, with Google Drive integration for document management.

## Features

- 🤖 RAG-powered AI assistant using Deepseek models via Groq API
- 📁 Google Drive integration for document selection
- 📄 PDF document processing and chunking
- 🌐 Web search capabilities via Exa API
- 🔍 Local vector search using Qdrant
- 💬 Interactive chat interface with streaming responses
- 🧠 Thinking process visualization

## Architecture

The application follows a client-server architecture:

- **MCP (Server)**: Located in the `@mcp/` folder, provides Google Drive authentication and file operations
- **Client**: Main application in `app.py` that provides the user interface and RAG functionality

## Prerequisites

- Python 3.11+
- Docker (for running Qdrant)
- Google Cloud account with Drive API enabled
- Groq API key
- (Optional) Exa API key for web search

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/deepseek_local_rag_agent.git
   cd deepseek_local_rag_agent
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables by creating a `.env` file in the project root:
   ```
   GROQ_API_KEY=your_groq_api_key
   EXA_API_KEY=your_exa_api_key  # Optional, for web search
   GOOGLE_API_KEY=your_google_api_key  # For Google Drive Picker
   GOOGLE_APP_ID=your_google_app_id  # For Google Drive Picker
   ```

5. Start the Qdrant vector database using Docker:
   ```bash
   bash run_qdrant.sh
   ```

## Running the Application

1. Start the Streamlit application:
   ```bash
   streamlit run app.py
   ```

2. Open your browser and navigate to `http://localhost:8501`

## Google Drive Integration Setup

1. Create a Google Cloud project and enable the Google Drive API and Picker API
2. Create OAuth 2.0 credentials (Desktop application)
3. Download the credentials as `credentials.json` and upload it through the application interface
4. Authenticate with Google Drive when prompted

## Usage

### RAG Mode

1. Enable RAG mode in the sidebar
2. Upload PDF documents or connect to Google Drive to select files
3. Ask questions about your documents in the chat interface
4. View the AI's thinking process and final answers

### Web Search

1. Enable Web Search Fallback in the sidebar
2. Toggle the 🌐 button next to the chat input to force web search
3. Ask questions that require up-to-date information

## Running Individual Components

### Google Drive Browser

To run the standalone Google Drive browser:

```bash
python drive.py
```

### Google Drive Picker

To serve the Google Drive Picker component:

```bash
python serve_picker.py --serve-only
```

## Troubleshooting

- If Qdrant connection fails, ensure Docker is running and the Qdrant container is active
- For Google Drive authentication issues, check that your credentials.json is valid and has the correct permissions
- If the application can't find the MCP module, ensure your directory structure is correct

## License

[MIT License](LICENSE)
