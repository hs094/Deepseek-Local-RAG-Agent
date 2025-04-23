"""
Google Drive MCP (Model Context Protocol) Module

This module provides a clean interface for Google Drive authentication and file operations.
It handles authentication, token caching, and file search operations.
"""

import os
import pickle
import io
from datetime import datetime
from typing import List, Dict, Optional, Any, Union, Tuple

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# Constants
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
DEFAULT_CREDENTIALS_PICKLE = 'token.pickle'
DEFAULT_CLIENT_SECRETS_FILE = 'credentials.json'

class GoogleDriveClient:
    """
    Client for interacting with Google Drive API.
    Handles authentication, token management, and file operations.
    """

    def __init__(
        self,
        credentials_file: str = DEFAULT_CLIENT_SECRETS_FILE,
        token_pickle_file: str = DEFAULT_CREDENTIALS_PICKLE,
        scopes: List[str] = None
    ):
        """
        Initialize the Google Drive client.

        Args:
            credentials_file: Path to the credentials.json file
            token_pickle_file: Path to save/load the authentication token
            scopes: OAuth scopes to request
        """
        self.credentials_file = credentials_file
        self.token_pickle_file = token_pickle_file
        self.scopes = scopes or SCOPES
        self.credentials = None
        self.service = None

    def credentials_exist(self) -> bool:
        """Check if the credentials file exists."""
        return os.path.exists(self.credentials_file)

    def save_credentials_file(self, content: bytes) -> None:
        """
        Save the credentials file from uploaded content.

        Args:
            content: The binary content of the credentials file
        """
        with open(self.credentials_file, 'wb') as f:
            f.write(content)

    def authenticate(self) -> bool:
        """
        Authenticate with Google Drive.

        Returns:
            bool: True if authentication was successful, False otherwise
        """
        # Check if token.pickle exists
        if os.path.exists(self.token_pickle_file):
            with open(self.token_pickle_file, 'rb') as token:
                self.credentials = pickle.load(token)

        # If credentials don't exist or are invalid, get new ones
        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                self.credentials.refresh(Request())
            else:
                if not os.path.exists(self.credentials_file):
                    return False

                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, self.scopes
                )
                self.credentials = flow.run_local_server(port=0)

            # Save the credentials for the next run
            with open(self.token_pickle_file, 'wb') as token:
                pickle.dump(self.credentials, token)

        # Create the Drive API service
        self.service = build('drive', 'v3', credentials=self.credentials)
        return True

    def search_files(
        self,
        query: str,
        folder_id: Optional[str] = None,
        page_size: int = 100,
        order_by: str = 'folder,name'
    ) -> List[Dict[str, Any]]:
        """
        Search for files in Google Drive.

        Args:
            query: Search query string
            folder_id: Optional folder ID to search within
            page_size: Number of results to return
            order_by: Field to sort results by

        Returns:
            List of file metadata dictionaries
        """
        if not self.service:
            if not self.authenticate():
                return []

        # Build the query
        drive_query = f"name contains '{query}' and trashed=false"
        if folder_id:
            drive_query = f"'{folder_id}' in parents and {drive_query}"

        # Execute the search
        results = self.service.files().list(
            q=drive_query,
            spaces='drive',
            fields='files(id, name, mimeType, webViewLink, iconLink, modifiedTime, size, parents)',
            pageSize=page_size,
            orderBy=order_by
        ).execute()

        return results.get('files', [])

    def get_file_content(self, file_id: str) -> io.BytesIO:
        """
        Get the content of a file from Google Drive.

        Args:
            file_id: The ID of the file to download

        Returns:
            BytesIO object containing the file content
        """
        if not self.service:
            if not self.authenticate():
                return None

        request = self.service.files().get_media(fileId=file_id)
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        file_content.seek(0)
        return file_content

    def get_access_token(self) -> str:
        """
        Get the current access token for API calls.

        Returns:
            str: The access token or None if not authenticated
        """
        if not self.credentials:
            if not self.authenticate():
                return None

        # Ensure the token is fresh
        if self.credentials.expired and self.credentials.refresh_token:
            self.credentials.refresh(Request())
            # Save the refreshed credentials
            with open(self.token_pickle_file, 'wb') as token:
                pickle.dump(self.credentials, token)

        # Try different ways to get the token
        if hasattr(self.credentials, 'token'):
            return self.credentials.token
        elif hasattr(self.credentials, 'access_token'):
            return self.credentials.access_token

        return None


# Utility functions for formatting file information
def format_file_size(size: Optional[Union[int, str]]) -> str:
    """
    Format file size in bytes to human-readable format.

    Args:
        size: File size in bytes

    Returns:
        Formatted size string
    """
    if size is None:
        return "--"

    size = int(size)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024 or unit == 'GB':
            return f"{size:.1f} {unit}"
        size /= 1024

def format_date(date_string: Optional[str]) -> str:
    """
    Format date string to a more readable format.

    Args:
        date_string: ISO format date string

    Returns:
        Formatted date string
    """
    if not date_string:
        return "--"

    date_obj = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
    return date_obj.strftime("%b %d, %Y")

def get_file_icon(mime_type: str) -> str:
    """
    Get an appropriate icon for a file based on its MIME type.

    Args:
        mime_type: The MIME type of the file

    Returns:
        Emoji icon representing the file type
    """
    if 'folder' in mime_type:
        return "📁"
    elif 'image' in mime_type:
        return "🖼️"
    elif 'pdf' in mime_type:
        return "📑"
    elif 'spreadsheet' in mime_type:
        return "📊"
    elif 'document' in mime_type:
        return "📝"
    elif 'presentation' in mime_type:
        return "📽️"
    else:
        return "📄"
