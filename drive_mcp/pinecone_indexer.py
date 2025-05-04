"""
Pinecone Indexer Module for Google Drive Files

This module provides functionality to automatically index files from Google Drive into Pinecone.
It handles file downloading, processing, and upserting to Pinecone.
"""

import os
import uuid
import tempfile
import io
from typing import List, Dict, Any, Optional, Union

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from pinecone import Pinecone
from agno.embedder.ollama import OllamaEmbedder

class PineconeIndexer:
    """
    Class for indexing Google Drive files to Pinecone.
    """

    def __init__(
        self,
        pinecone_client: Pinecone,
        index_name: str,
        namespace: str = "rag-namespace",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        embedding_model: str = "snowflake-arctic-embed"
    ):
        """
        Initialize the Pinecone Indexer.

        Args:
            pinecone_client: Initialized Pinecone client
            index_name: Name of the Pinecone index to use
            namespace: Namespace to use within the index
            chunk_size: Size of text chunks for splitting documents
            chunk_overlap: Overlap between text chunks
            embedding_model: Name of the embedding model to use
        """
        self.pinecone_client = pinecone_client
        self.index_name = index_name
        self.namespace = namespace
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Initialize the embedder
        self.embedder = OllamaEmbedder(id=embedding_model, dimensions=1024)

        # Get the index from the Pinecone client
        index_info = self.pinecone_client.describe_index(self.index_name)
        self.index_host = index_info.host
        self.index = self.pinecone_client.Index(host=self.index_host)

    def process_pdf(self, file_content: io.BytesIO, file_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process a PDF file and prepare it for indexing.

        Args:
            file_content: BytesIO object containing the PDF content
            file_metadata: Metadata about the file from Google Drive

        Returns:
            List of document chunks ready for Pinecone
        """
        all_chunks = []

        # Save the file to a temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(file_content.getvalue())
            temp_file_path = tmp_file.name

        try:
            # Load the PDF
            loader = PyPDFLoader(temp_file_path)
            documents = loader.load()

            # Add metadata to documents
            for doc in documents:
                doc.metadata.update({
                    "source_type": "pdf",
                    "file_name": file_metadata.get('name', 'Unknown'),
                    "file_id": file_metadata.get('id', ''),
                    "mime_type": file_metadata.get('mimeType', ''),
                    "web_view_link": file_metadata.get('webViewLink', ''),
                    "source": "google_drive"
                })

            # Split documents
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap
            )
            split_docs = text_splitter.split_documents(documents)

            # Prepare data for Pinecone
            for doc in split_docs:
                # Create a unique ID for each chunk
                doc_id = str(uuid.uuid4())

                # Add to chunks list
                all_chunks.append({
                    "id": doc_id,
                    "text": doc.page_content,
                    "metadata": doc.metadata
                })

        except Exception as e:
            print(f"Error processing PDF: {str(e)}")
        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

        return all_chunks

    def process_text(self, file_content: io.BytesIO, file_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process a text file and prepare it for indexing.

        Args:
            file_content: BytesIO object containing the text content
            file_metadata: Metadata about the file from Google Drive

        Returns:
            List of document chunks ready for Pinecone
        """
        all_chunks = []

        # Save the file to a temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as tmp_file:
            tmp_file.write(file_content.getvalue())
            temp_file_path = tmp_file.name

        try:
            # Load the text file
            loader = TextLoader(temp_file_path)
            documents = loader.load()

            # Add metadata to documents
            for doc in documents:
                doc.metadata.update({
                    "source_type": "text",
                    "file_name": file_metadata.get('name', 'Unknown'),
                    "file_id": file_metadata.get('id', ''),
                    "mime_type": file_metadata.get('mimeType', ''),
                    "web_view_link": file_metadata.get('webViewLink', ''),
                    "source": "google_drive"
                })

            # Split documents
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap
            )
            split_docs = text_splitter.split_documents(documents)

            # Prepare data for Pinecone
            for doc in split_docs:
                # Create a unique ID for each chunk
                doc_id = str(uuid.uuid4())

                # Add to chunks list
                all_chunks.append({
                    "id": doc_id,
                    "text": doc.page_content,
                    "metadata": doc.metadata
                })

        except Exception as e:
            print(f"Error processing text file: {str(e)}")
        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

        return all_chunks

    def process_file(self, file_content: io.BytesIO, file_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process a file based on its MIME type.

        Args:
            file_content: BytesIO object containing the file content
            file_metadata: Metadata about the file from Google Drive

        Returns:
            List of document chunks ready for Pinecone
        """
        mime_type = file_metadata.get('mimeType', '')

        # Check for different file types
        is_pdf = 'pdf' in mime_type
        is_text = 'text/plain' in mime_type or 'text' in mime_type
        is_doc = 'document' in mime_type or 'officedocument' in mime_type

        if is_pdf:
            return self.process_pdf(file_content, file_metadata)
        elif is_text:
            return self.process_text(file_content, file_metadata)
        elif is_doc:
            # Try to process document files as text
            print(f"Attempting to process document as text: {file_metadata.get('name', 'Unknown')}")
            try:
                return self.process_text(file_content, file_metadata)
            except Exception as e:
                print(f"Error processing document as text: {str(e)}")
                return []
        else:
            print(f"Unsupported file type: {mime_type}")
            return []

    def index_files(self, files: List[Dict[str, Any]], gdrive_client) -> Dict[str, Any]:
        """
        Index multiple files from Google Drive to Pinecone.

        Args:
            files: List of file metadata from Google Drive
            gdrive_client: Authenticated Google Drive client

        Returns:
            Dictionary with indexing results
        """
        results = {
            "total_files": len(files),
            "processed_files": 0,
            "skipped_files": 0,
            "total_chunks": 0,
            "processed_files_list": []
        }

        all_chunks = []

        # Process each file
        for file in files:
            mime_type = file.get('mimeType', '')

            # Skip folders only
            if 'folder' in mime_type:
                results["skipped_files"] += 1
                continue

            try:
                # Get the file content
                file_id = file['id']
                file_content = gdrive_client.get_file_content(file_id)

                # Process the file
                chunks = self.process_file(file_content, file)

                if chunks:
                    all_chunks.extend(chunks)
                    results["processed_files"] += 1
                    results["processed_files_list"].append(file['name'])
                else:
                    results["skipped_files"] += 1
            except Exception as e:
                print(f"Error processing file {file.get('name', 'Unknown')}: {str(e)}")
                results["skipped_files"] += 1

        # Batch upsert to Pinecone if we have chunks
        if all_chunks:
            results["total_chunks"] = len(all_chunks)

            # Prepare records for Pinecone with local embeddings
            records = []
            for chunk in all_chunks:
                # Generate embedding for the text
                try:
                    embedding = self.embedder.get_embedding(chunk["text"])

                    # Create record with embedding
                    records.append({
                        "id": chunk["id"],
                        "values": embedding,  # Use local embedding
                        "metadata": {
                            "text": chunk["text"],  # Store text in metadata
                            **chunk["metadata"]  # Include other metadata
                        }
                    })
                except Exception as e:
                    print(f"Error generating embedding for chunk: {str(e)}")

            # Batch size for upserting
            batch_size = 50  # Smaller batch size for records with embeddings
            batches = [records[i:i + batch_size] for i in range(0, len(records), batch_size)]

            # Upsert each batch
            for i, batch in enumerate(batches):
                print(f"Upserting batch {i+1}/{len(batches)}...")
                self.index.upsert(
                    vectors=batch,
                    namespace=self.namespace
                )

        return results

    def retrieve(self, query: str, top_k: int = 5, score_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        Retrieve relevant documents from Pinecone based on a query.

        Args:
            query: The query string to search for
            top_k: Maximum number of results to return
            score_threshold: Minimum similarity score threshold

        Returns:
            List of document chunks with their metadata and scores
        """
        try:
            # Generate embedding for the query
            query_embedding = self.embedder.get_embedding(query)

            # Query Pinecone
            query_results = self.index.query(
                namespace=self.namespace,
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True
            )

            # Process results
            results = []
            if hasattr(query_results, 'matches'):
                for match in query_results.matches:
                    # Check if score meets threshold
                    if match.score >= score_threshold:
                        # Extract text and metadata
                        text = match.metadata.get('text', '')
                        metadata = {k: v for k, v in match.metadata.items() if k != 'text'}

                        # Create document object similar to langchain Document
                        doc = {
                            'page_content': text,
                            'metadata': metadata,
                            'score': match.score,
                            'id': match.id
                        }
                        results.append(doc)

            return results
        except Exception as e:
            print(f"Error retrieving documents: {str(e)}")
            return []

    def retrieve_as_langchain_docs(self, query: str, top_k: int = 5, score_threshold: float = 0.7) -> List:
        """
        Retrieve relevant documents from Pinecone and return them as LangChain Document objects.

        Args:
            query: The query string to search for
            top_k: Maximum number of results to return
            score_threshold: Minimum similarity score threshold

        Returns:
            List of LangChain Document objects
        """
        from langchain_core.documents import Document

        # Get raw results
        raw_results = self.retrieve(query, top_k, score_threshold)

        # Convert to LangChain Document objects
        documents = []
        for result in raw_results:
            doc = Document(
                page_content=result['page_content'],
                metadata=result['metadata']
            )
            documents.append(doc)

        return documents
