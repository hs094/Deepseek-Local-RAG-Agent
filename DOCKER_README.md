# Docker Setup for Deepseek Local RAG Agent

This document explains how to run the Deepseek Local RAG Agent using Docker and Docker Compose.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

## Getting Started

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/deepseek_local_rag_agent.git
   cd deepseek_local_rag_agent
   ```

2. Create a `.env` file with your API keys:
   ```bash
   cp .env.example .env
   ```
   
   Then edit the `.env` file to add your actual API keys.

3. Build and start the containers:
   ```bash
   docker-compose up -d
   ```

4. Access the application:
   - Streamlit app: http://localhost:8501
   - Google Drive Picker (for development): http://localhost:3001

## Services

The Docker Compose setup includes the following services:

1. **streamlit**: The main Streamlit application that provides the RAG interface
2. **gdrive-picker**: The Google Drive Picker component for selecting files
3. **qdrant**: The Qdrant vector database for storing document embeddings

## Volumes

- **qdrant_storage**: Persistent storage for the Qdrant vector database

## Environment Variables

The following environment variables are required:

- `GROQ_API_KEY`: Your Groq API key for accessing Deepseek models
- `GOOGLE_API_KEY`: Your Google API key for the Drive Picker
- `GOOGLE_APP_ID`: Your Google App ID for the Drive Picker

Optional:
- `EXA_API_KEY`: Your Exa API key for web search capabilities

## Troubleshooting

- If you encounter issues with the Google Drive integration, make sure your Google Cloud project has the Drive API and Picker API enabled.
- For authentication issues, check that your credentials are correctly mounted in the container.
- If Qdrant connection fails, ensure the Qdrant container is running properly.

## Development

For development purposes, you can mount your local directories as volumes to see changes in real-time:

```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```
